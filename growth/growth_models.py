from __future__ import annotations

from pydantic import BaseModel, Field


class Recommendation(BaseModel):
    title: str
    reason: str
    priority: str
    impact: str
    estimated_time: str
    action: str
    target_tool: str


class DailyTask(BaseModel):
    title: str
    description: str
    completed: bool = False
    priority: str = "medium"


class BioDoctor(BaseModel):
    score: int = 0
    problems: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    ready_bios: list[str] = Field(default_factory=list)


class ProfileDoctor(BaseModel):
    score: int = 0
    problems: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class HighlightDoctor(BaseModel):
    score: int = 0
    missing: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ReadyToPublish(BaseModel):
    hook: str = ""
    caption: str = ""
    cta: str = ""
    hashtags: list[str] = Field(default_factory=list)
    publish_time: str = ""
    image_prompt: str = ""


class GrowthManagerResponse(BaseModel):
    growth_score: int

    daily_focus: str

    recommendations: list[Recommendation]

    daily_tasks: list[DailyTask]

    bio: BioDoctor

    profile: ProfileDoctor

    highlights: HighlightDoctor

    publish: ReadyToPublish
