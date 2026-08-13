from datetime import date

from app.workflow.graph import workflow


def main():

    initial_state = {
        "job_id": 999,
        "topic": "AI Automation for Small Businesses",
        "as_of": date.today().isoformat(),
        "status": "pending",
        "current_step": "starting",
        "evidence": [],
        "sections": [],
    }

    print("\n==============================")
    print("FULL GRAPH RUN")
    print("==============================")

    result = workflow.invoke(initial_state)

    print("\nMode:", result.get("mode"))
    print("Needs research:", result.get("needs_research"))
    print("Evidence found:", len(result.get("evidence", [])))

    plan = result.get("plan")
    print("\nPlan title:", plan.blog_title if plan else None)
    print("Planned tasks:", len(plan.tasks) if plan else 0)

    sections = result.get("sections", [])
    print("\nSections returned by workers:", len(sections))
    print("Section task_ids (pre-reduce order):",
          [s["task_id"] for s in sections])

    print("\nStatus:", result.get("status"))

    print("\n==============================")
    print("FINAL CONTENT")
    print("==============================\n")

    print(result.get("final_content"))

    print("\n==============================")
    print("GRAPH TEST COMPLETE")
    print("==============================")


if __name__ == "__main__":
    main()
