from __future__ import annotations

import operator
from typing import Annotated, List, Optional, Literal, TypedDict

from pydantic import BaseModel, Field


# ============================================================
# Workflow Schemas
# ============================================================

class Task(BaseModel):
    id: int
    title: str
    goal: str = Field(
        ...,
        description="One sentence describing what the reader should understand."
    )
    bullets: List[str] = Field(
        ...,
        min_length=3,
        max_length=6
    )
    target_words: int = Field(
        ...,
        description="Target words for this section."
    )

    tags: List[str] = Field(default_factory=list)

    requires_research: bool = False
    requires_citations: bool = False
    requires_code: bool = False


class Plan(BaseModel):
    blog_title: str
    audience: str
    tone: str

    blog_kind: Literal[
        "explainer",
        "tutorial",
        "news_roundup",
        "comparison",
        "system_design"
    ] = "explainer"

    constraints: List[str] = Field(default_factory=list)

    tasks: List[Task]


class EvidenceItem(BaseModel):
    title: str
    url: str

    published_at: Optional[str] = None
    snippet: Optional[str] = None
    source: Optional[str] = None


class RouterDecision(BaseModel):
    needs_research: bool

    mode: Literal[
        "closed_book",
        "hybrid",
        "open_book"
    ]

    reason: str

    queries: List[str] = Field(default_factory=list)

    max_results_per_query: int = 5


class EvidencePack(BaseModel):
    evidence: List[EvidenceItem] = Field(
        default_factory=list
    )


class Section(TypedDict):
    """
    One completed content section, as produced by a worker
    and consumed by the reducer. Matches the dict shape
    content_worker_node's (task_id, content) tuple is
    reshaped into by worker_node().
    """
    task_id: int
    content: str


# ============================================================
# Image Planning Schemas
# ============================================================

class ImageSpec(BaseModel):
    placeholder: str = Field(
        ...,
        description="Example: [[IMAGE_1]]"
    )

    filename: str

    alt: str

    caption: str

    prompt: str

    size: Literal[
        "1024x1024",
        "1024x1536",
        "1536x1024"
    ] = "1024x1024"

    quality: Literal[
        "low",
        "medium",
        "high"
    ] = "medium"


class GlobalImagePlan(BaseModel):
    md_with_placeholders: str

    images: List[ImageSpec] = Field(
        default_factory=list
    )


# ============================================================
# Main LangGraph State
# ============================================================

class AutomationState(TypedDict, total=False):

    # --------------------------------------------------------
    # Job information
    # --------------------------------------------------------

    job_id: int

    topic: str

    status: str

    current_step: str

    error: str


    # --------------------------------------------------------
    # Routing / Research
    # --------------------------------------------------------

    mode: str

    needs_research: bool

    queries: List[str]

    evidence: List[EvidenceItem]


    # --------------------------------------------------------
    # Date / Recency
    # --------------------------------------------------------

    as_of: str

    recency_days: int


    # --------------------------------------------------------
    # Content Planning
    # --------------------------------------------------------

    plan: Optional[Plan]


    # --------------------------------------------------------
    # Worker Dispatch
    #
    # Set only on the per-invocation payload sent to the
    # "worker" node via Send(). Not part of the shared/reduced
    # state - each parallel worker gets its own Task here.
    # --------------------------------------------------------

    task: Task


    # --------------------------------------------------------
    # Parallel Worker Output
    #
    # operator.add allows multiple worker nodes
    # to contribute sections to the same state.
    # ------------------------------------------------------
    sections: Annotated[
        List[Section],
        operator.add
    ]


    # --------------------------------------------------------
    # Content Reduction
    # --------------------------------------------------------

    merged_md: str

    md_with_placeholders: str


    # --------------------------------------------------------
    # Image Generation
    # --------------------------------------------------------

    image_specs: List[dict]

    generated_image_paths: List[str]


    # --------------------------------------------------------
    # Final Output
    # --------------------------------------------------------

    final: str

    final_title: str
    final_content: str