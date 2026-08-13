from app.workflow.nodes import reducer_node


def main():

    state = {
        "sections": [
            {
                "task_id": 3,
                "content": """
## Practical Applications

AI automation can be used for customer support,
marketing and repetitive business processes.
"""
            },
            {
                "task_id": 1,
                "content": """
## Introduction

AI automation helps businesses reduce repetitive
manual work and improve productivity.
"""
            },
            {
                "task_id": 2,
                "content": """
## Key Concepts

Important concepts include workflow automation,
AI agents and API integrations.
"""
            },
        ]
    }

    print("\n==============================")
    print("REDUCER TEST")
    print("==============================")

    result = reducer_node(state)

    print("Status:", result["status"])

    print("\nFinal Article:\n")

    print(result["final_content"])

    print("\n==============================")
    print("REDUCER TEST COMPLETE")
    print("==============================")


if __name__ == "__main__":
    main()