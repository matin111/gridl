from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SignalEvidence(BaseModel):
    key: str
    label: str
    value: str


class Recommendation(BaseModel):
    title: str
    reason: str
    priority: Literal["critical", "high", "medium", "low"]
    impact: str
    estimated_time: str
    action: str
    target_tool: str
    teaching: str = ""
    source_signals: list[SignalEvidence] = Field(default_factory=list)


class DailyTask(BaseModel):
    title: str
    description: str
    completed: bool = False
    priority: Literal["high", "medium", "low"] = "medium"
    success_metric: str = ""
    teaching: str = ""
    source_signals: list[SignalEvidence] = Field(default_factory=list)


class BioDoctor(BaseModel):
    score: int = 0
    problems: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    ready_bios: list[str] = Field(default_factory=list)
    teaching: str = ""
    source_signals: list[SignalEvidence] = Field(default_factory=list)


class ProfileDoctor(BaseModel):
    score: int = 0
    problems: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    teaching: str = ""
    source_signals: list[SignalEvidence] = Field(default_factory=list)


class HighlightDoctor(BaseModel):
    score: int = 0
    missing: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ContentDiagnosis(BaseModel):
    score: int
    summary: str
    problems: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    teaching: str
    source_signals: list[SignalEvidence] = Field(default_factory=list)


class RoadmapDay(BaseModel):
    day: int
    title: str
    actions: list[str]
    success_metric: str
    teaching: str


class GrowthForecast(BaseModel):
    horizon_days: int = 30
    expected_improvement: str
    confidence: Literal["low", "medium", "high"]
    confidence_score: int
    basis: str
    caveat: str
    source_signals: list[SignalEvidence] = Field(default_factory=list)


class ReadyToPublish(BaseModel):
    topic: str = ""
    content_type: str = ""
    hook: str = ""
    scenario: list[str] = Field(default_factory=list)
    caption: str = ""
    cta: str = ""
    hashtags: list[str] = Field(default_factory=list)
    publish_time: str = ""
    image_prompt: str = ""
    teaching: str = ""
    source_signals: list[SignalEvidence] = Field(default_factory=list)


class GrowthManagerResponse(BaseModel):
    version: int = 6
    executive_summary: str = ""
    growth_score: int
    score_explanation: str = ""
    daily_focus: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    daily_tasks: list[DailyTask] = Field(default_factory=list)
    bio: BioDoctor
    profile: ProfileDoctor
    highlights: HighlightDoctor
    content_diagnosis: ContentDiagnosis | None = None
    weekly_roadmap: list[RoadmapDay] = Field(default_factory=list)
    forecast: GrowthForecast | None = None
    publish: ReadyToPublish
