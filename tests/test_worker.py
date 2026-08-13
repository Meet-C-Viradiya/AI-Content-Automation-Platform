from datetime import date

from app.workflow.nodes import (
    router_node,
    research_node,
    orchestrator_node,
    content_worker_node,
)


def main():

    state = {
        "job_id": 101,
        "topic": "AI Automation for Small Businesses",
        "as_of": date.today().isoformat(),
        "status": "pending",
        "current_step": "starting",
        "evidence": [],
        "sections": [],
    }

    print("\n==============================")
    print("1. ROUTER")
    print("==============================")

    state.update(
        router_node(state)
    )

    print(
        "Mode:",
        state.get("mode")
    )

    print(
        "Queries:",
        state.get("queries")
    )

    print("\n==============================")
    print("2. RESEARCH")
    print("==============================")

    state.update(
        research_node(state)
    )

    print(
        "Evidence:",
        len(state.get("evidence", []))
    )

    print("\n==============================")
    print("3. ORCHESTRATOR")
    print("==============================")

    state.update(
        orchestrator_node(state)
    )

    plan = state["plan"]

    print(
        "Plan:",
        plan.blog_title
    )

    print(
        "Tasks:",
        len(plan.tasks)
    )

    print("\n==============================")
    print("4. CONTENT WORKER")
    print("==============================")

    task = plan.tasks[0]

    task_id, content = content_worker_node(
        state,
        task
    )

    print(
        "Task ID:",
        task_id
    )

    print("\nGenerated content:\n")

    print(content)

    print("\n==============================")
    print("WORKER TEST COMPLETE")
    print("==============================")


if __name__ == "__main__":
    main()