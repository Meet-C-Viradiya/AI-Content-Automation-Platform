from __future__ import annotations
from app.services.tavily_service import search_web

import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, List

from dotenv import load_dotenv

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.workflow.state import (
    AutomationState,
    Task,
    Plan,
    EvidenceItem,
    RouterDecision,
    EvidencePack,
    GlobalImagePlan,
    Section,
)

load_dotenv()


# ============================================================
# LLM Configuration
# ============================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash"
)


# ============================================================
# Router
# ============================================================

ROUTER_SYSTEM = """
You are an AI content automation routing module.

Analyze the requested topic and decide whether web research
is required before generating the content.

Modes:

1. closed_book
   Use for stable, evergreen knowledge.

2. hybrid
   Use when the topic is mostly stable but current examples,
   tools, models, or technologies may be useful.

3. open_book
   Use for latest news, weekly updates, current pricing,
   policies, releases, or other rapidly changing information.

If research is required, generate 3-10 focused search queries.
"""


def router_node(state: AutomationState) -> dict:
    """
    Decide whether the topic requires web research.

    If the OpenAI API is unavailable, the workflow does not crash.
    It falls back to a research-first mode so the job can be
    handled gracefully.
    """

    decider = llm.with_structured_output(
        RouterDecision
    )

    try:
        decision = decider.invoke(
            [
                SystemMessage(
                    content=ROUTER_SYSTEM
                ),
                HumanMessage(
                    content=(
                        f"Topic: {state['topic']}\n"
                        f"As-of date: {state['as_of']}"
                    )
                ),
            ]
        )

        if decision.mode == "open_book":
            recency_days = 7

        elif decision.mode == "hybrid":
            recency_days = 45

        else:
            recency_days = 3650

        return {
            "needs_research": decision.needs_research,
            "mode": decision.mode,
            "queries": decision.queries,
            "recency_days": recency_days,
            "current_step": "routing",
            "status": "processing",
        }

    except Exception as e:

        print(
            f"OpenAI router unavailable: {e}"
        )

        # Safe fallback
        return {
            "needs_research": True,
            "mode": "hybrid",
            "queries": [
                state["topic"]
            ],
            "recency_days": 45,
            "current_step": "routing",
            "status": "processing",
            "error": "AI router unavailable; using fallback routing.",
        }

def research_node(state: AutomationState) -> dict:
    """
    Research the topic using Tavily and store
    normalized evidence in the workflow state.
    """

    queries = state.get("queries", [])

    if not queries:
        return {
            "evidence": [],
            "current_step": "research",
        }

    results = search_web(
        queries=queries,
        max_results=5
    )

    evidence = []

    for result in results:
        if not isinstance(result, dict):
            continue

        # Tavily's client sometimes returns {"error": ...} instead
        # of raising when a query fails (bad key, rate limit, network
        # issue). Treat that as "no evidence from this query" rather
        # than fabricating an "Untitled" evidence item.
        if "error" in result:
            print(f"Tavily query failed: {result['error']}")
            continue

        evidence.append(
            EvidenceItem(
                title=result.get("title", "Untitled"),
                url=result.get("url", ""),
                published_at=result.get("published_date"),
                snippet=result.get("content"),
                source="Tavily"
            )
        )

    return {
        "evidence": evidence,
        "current_step": "research",
        "status": "processing",
    }



# ============================================================
# Content Generation Worker
# ============================================================

WORKER_SYSTEM = """
You are a professional content generation worker.

Your job is to write ONE section of a larger article.

Rules:

1. Focus only on the assigned section.
2. Follow the section goal and bullet points.
3. Use the provided research evidence when relevant.
4. Do not invent facts or sources.
5. Write clear, useful and practical content.
6. Do not write the introduction or conclusion unless assigned.
7. Return clean Markdown.
"""


def content_worker_node(
    state: AutomationState,
    task: Task
) -> tuple[int, str]:
    """
    Generate one content section from a planned task.

    Returns:
        (task_id, generated_markdown)
    """

    evidence_text = ""

    for item in state.get("evidence", []):
        evidence_text += (
            f"- {item.title}\n"
            f"  URL: {item.url}\n"
            f"  Information: {item.snippet or ''}\n"
        )

    prompt = f"""
Topic:
{state["topic"]}

Section:
{task.title}

Section goal:
{task.goal}

Required points:
{chr(10).join("- " + bullet for bullet in task.bullets)}

Target words:
{task.target_words}

Research evidence:
{evidence_text if evidence_text else "No external evidence available."}

Write this section in Markdown.
"""

    try:

        response = llm.invoke(
            [
                SystemMessage(
                    content=WORKER_SYSTEM
                ),
                HumanMessage(
                    content=prompt
                ),
            ]
        )

        content = response.content

        if isinstance(content, list):
            content = "\n".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )

        return task.id, content

    except Exception as e:

        print(
            f"OpenAI worker unavailable for "
            f"section {task.id}: {e}"
        )

        # Development fallback
        fallback_content = (
            f"## {task.title}\n\n"
            f"{task.goal}\n\n"
            "This section explains the following key areas:\n\n"
            + "\n".join(
                f"- {bullet}"
                for bullet in task.bullets
            )
            + "\n\n"
            f"The target audience should consider these "
            f"points when applying {state['topic']} "
            f"in a practical business environment."
        )

        return task.id, fallback_content


# ============================================================
# Worker Manager (LangGraph adapter)
# ============================================================

def worker_node(state: AutomationState) -> dict:
    """
    LangGraph entry point for a single content worker.

    content_worker_node() takes (state, task) and can't be a
    normal graph node, which only receives (state). This node
    is the wrapper: LangGraph invokes it once per task (fanned
    out in parallel by assign_workers()/Send() in graph.py),
    each invocation carrying its own `task` in the state payload.

    It delegates the actual generation to content_worker_node(),
    then reshapes the (task_id, content) tuple it returns into
    the {"task_id", "content"} dict shape reducer_node() expects,
    and hands back a one-item "sections" list. LangGraph merges
    every parallel worker's list into the shared state via the
    operator.add reducer declared on AutomationState.sections.
    """

    task: Task = state["task"]

    task_id, content = content_worker_node(state, task)

    section: Section = {
        "task_id": task_id,
        "content": content,
    }

    return {
        "sections": [section]
    }


# ============================================================
# Content Reducer
# ============================================================

def reducer_node(state: AutomationState) -> dict:
    """
    Combine all generated sections into one final article.

    Sections are sorted by task ID so the final article keeps
    the order defined by the content plan.
    """

    sections = state.get("sections", [])

    if not sections:
        return {
            "final_content": "",
            "current_step": "reduction",
            "status": "failed",
            "error": "No generated sections available.",
        }

    # Sort sections according to the original plan
    sorted_sections = sorted(
        sections,
        key=lambda item: item["task_id"]
    )

    # Combine the generated Markdown
    article_parts = []

    for section in sorted_sections:
        article_parts.append(
            section["content"].strip()
        )

    final_content = "\n\n".join(article_parts)

    return {
        "final_content": final_content,
        "current_step": "reduction",
        "status": "completed",
    }


ORCHESTRATOR_SYSTEM = """
You are the content planning engine of an AI automation system.

Create a detailed, practical content plan for the requested topic.

The plan must:

1. Have a clear and useful title.
2. Identify the target audience.
3. Select an appropriate tone.
4. Select the appropriate content type.
5. Break the content into logical sections.
6. Give each section a clear goal.
7. Provide 3-6 useful bullet points for every section.
8. Estimate the target word count for every section.
9. Identify whether research, citations, or code are required.

Avoid unnecessary sections and avoid repeating the same information.
"""


def orchestrator_node(state: AutomationState) -> dict:
    """
    Create a structured content plan.

    Uses OpenAI when available and falls back to a deterministic
    development plan when the AI provider is unavailable.
    """

    planner = llm.with_structured_output(
        Plan
    )

    evidence_text = ""

    for item in state.get("evidence", []):
        evidence_text += (
            f"\nTitle: {item.title}"
            f"\nURL: {item.url}"
            f"\nSnippet: {item.snippet or ''}"
            "\n"
        )

    prompt = f"""
Topic:
{state["topic"]}

Content mode:
{state.get("mode", "closed_book")}

Research evidence:
{evidence_text if evidence_text else "No external research was required."}

Create the complete content plan.
"""

    try:

        plan = planner.invoke(
            [
                SystemMessage(
                    content = ORCHESTRATOR_SYSTEM
                ),
                HumanMessage(
                    content=prompt
                ),
            ]
        )

        return {
            "plan": plan,
            "current_step": "planning",
            "status": "processing",
        }

    except Exception as e:

        print(
            f"OpenAI planner unavailable: {e}"
        )

        fallback_plan = Plan(
            blog_title=state["topic"],
            audience="Small and medium-sized business owners",
            tone="Professional and practical",
            blog_kind="explainer",
            constraints=[
                "Use clear language",
                "Avoid unsupported claims",
                "Use research evidence where available"
            ],
            tasks=[
                Task(
                    id=1,
                    title="Introduction",
                    goal="Explain the topic and why it matters.",
                    bullets=[
                        "Define the topic",
                        "Explain its importance",
                        "Introduce the main benefits"
                    ],
                    target_words=250,
                    tags=["introduction"],
                    requires_research=True,
                    requires_citations=True,
                    requires_code=False
                ),
                Task(
                    id=2,
                    title="Key Concepts",
                    goal="Explain the important concepts related to the topic.",
                    bullets=[
                        "Core concepts",
                        "Common use cases",
                        "Important considerations"
                    ],
                    target_words=400,
                    tags=["concepts"],
                    requires_research=True,
                    requires_citations=True,
                    requires_code=False
                ),
                Task(
                    id=3,
                    title="Practical Applications",
                    goal="Show how the topic can be applied in real situations.",
                    bullets=[
                        "Business applications",
                        "Automation opportunities",
                        "Expected benefits"
                    ],
                    target_words=500,
                    tags=["applications"],
                    requires_research=True,
                    requires_citations=True,
                    requires_code=False
                ),
                Task(
                    id=4,
                    title="Implementation Guide",
                    goal="Provide practical steps for implementation.",
                    bullets=[
                        "Getting started",
                        "Required tools",
                        "Common mistakes to avoid"
                    ],
                    target_words=500,
                    tags=["implementation"],
                    requires_research=False,
                    requires_citations=False,
                    requires_code=False
                ),
                Task(
                    id=5,
                    title="Conclusion",
                    goal="Summarize the main ideas and recommended next steps.",
                    bullets=[
                        "Key takeaways",
                        "Recommended next steps",
                        "Final considerations"
                    ],
                    target_words=200,
                    tags=["conclusion"],
                    requires_research=False,
                    requires_citations=False,
                    requires_code=False
                ),
            ],
        )

        return {
            "plan": fallback_plan,
            "current_step": "planning",
            "status": "processing",
            "error": "AI planner unavailable; using development fallback plan.",
        }