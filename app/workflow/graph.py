from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from app.workflow.state import AutomationState
from app.workflow.nodes import (
    router_node,
    research_node,
    orchestrator_node,
    worker_node,
    reducer_node,
)


# ============================================================
# Fan-out routing
# ============================================================

def assign_workers(state: AutomationState):
    """
    Conditional edge from "orchestrator".

    Reads the content plan and dispatches one parallel "worker"
    invocation per task using LangGraph's Send API. Each Send
    payload is the full current state plus that one task, so the
    worker has everything content_worker_node() needs (topic,
    evidence, etc.) without task being a permanent part of the
    shared graph state.

    LangGraph runs all dispatched "worker" invocations concurrently,
    then merges each one's returned "sections" list into the shared
    state via the operator.add reducer on AutomationState.sections.
    Once every worker has finished, execution proceeds along the
    "worker" -> "reducer" edge exactly once.
    """

    plan = state.get("plan")

    if not plan or not plan.tasks:
        # Nothing to generate - skip straight to the reducer,
        # which already handles an empty "sections" list safely.
        return "reducer"

    return [
        Send("worker", {**state, "task": task})
        for task in plan.tasks
    ]


# ============================================================
# Main Workflow
# ============================================================

def build_workflow():
    """
    Build the AI content automation workflow.

    Flow:

    START
      |
    Router
      |
    Research
      |
    Orchestrator
      |
    Worker Manager (parallel fan-out, one per planned task)
      |
    Reducer  (fan-in: merges + orders sections)
      |
    END
    """

    workflow = StateGraph(
        AutomationState
    )

    # Register nodes
    workflow.add_node(
        "router",
        router_node
    )

    workflow.add_node(
        "research",
        research_node
    )

    workflow.add_node(
        "orchestrator",
        orchestrator_node
    )

    workflow.add_node(
        "worker",
        worker_node
    )

    workflow.add_node(
        "reducer",
        reducer_node
    )

    # Connect nodes
    workflow.add_edge(
        START,
        "router"
    )

    workflow.add_edge(
        "router",
        "research"
    )

    workflow.add_edge(
        "research",
        "orchestrator"
    )

    # Fan-out: orchestrator dispatches N parallel worker runs
    # (or skips straight to "reducer" if there are no tasks).
    workflow.add_conditional_edges(
        "orchestrator",
        assign_workers,
        ["worker", "reducer"],
    )

    # Fan-in: every worker converges back on the reducer.
    workflow.add_edge(
        "worker",
        "reducer"
    )

    workflow.add_edge(
        "reducer",
        END
    )

    return workflow.compile()


# Create compiled workflow
workflow = build_workflow()
