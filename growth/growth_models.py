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


class ContentDiagnosis(BaseModel):
    summary: str
    strongest_format: str
    engagement_status: str
    consistency_status: str
    caption_status: str


class WeeklyRoadmapItem(BaseModel):
    week: int
    objective: str
    missions: list[str] = Field(default_factory=list)
    success_metric: str


class GrowthForecast(BaseModel):
    horizon_days: int = 30
    expected_outcome: str
    confidence: str
    assumptions: list[str] = Field(default_factory=list)


class GrowthManagerResponse(BaseModel):
    executive_summary: str

    growth_score: int

    daily_focus: str

    recommendations: list[Recommendation]

    daily_tasks: list[DailyTask]

    # Keep daily_tasks for Android clients; daily_missions is the V6 name.
    daily_missions: list[DailyTask]

    content_diagnosis: ContentDiagnosis

    weekly_roadmap: list[WeeklyRoadmapItem]

    growth_forecast: GrowthForecast

    bio: BioDoctor

    profile: ProfileDoctor

    highlights: HighlightDoctor

    publish: ReadyToPublish
