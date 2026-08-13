from datetime import date

from app.workflow.nodes import (
    router_node,
    research_node,
    orchestrator_node,
)


def main():

    # Initial workflow state
    state = {
        "job_id": 100,
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

    result = router_node(state)

    state.update(result)

    print("Mode:", state.get("mode"))
    print("Needs research:", state.get("needs_research"))
    print("Queries:", state.get("queries"))

    print("\n==============================")
    print("2. RESEARCH")
    print("==============================")

    if state.get("needs_research"):

        result = research_node(state)

        state.update(result)

        print(
            "Evidence found:",
            len(state.get("evidence", []))
        )

        for item in state.get("evidence", [])[:3]:
            print("-", item.title)
            print(" ", item.url)

    else:
        print("Research was not required.")

    print("\n==============================")
    print("3. ORCHESTRATOR")
    print("==============================")

    result = orchestrator_node(state)

    state.update(result)

    plan = state.get("plan")

    print("Title:", plan.blog_title)
    print("Audience:", plan.audience)
    print("Tone:", plan.tone)

    print("\nSections:")

    for task in plan.tasks:
        print(
            f"{task.id}. {task.title} "
            f"({task.target_words} words)"
        )

    print("\n==============================")
    print("WORKFLOW TEST SUCCESSFUL")
    print("==============================")


if __name__ == "__main__":
    main()