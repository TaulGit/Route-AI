"""Shared contracts for the graph, tools, API and offline evaluation."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TravelBrief(StrictModel):
    city: str = Field(default="", max_length=80)
    date: str = ""
    start_time: str = "09:00"
    end_time: str = "18:00"
    budget_max: float | None = Field(default=None, ge=0, le=100000)
    max_pois: int = Field(default=3, ge=1, le=6)
    preferences: list[str] = Field(default_factory=list, max_length=4)
    transportation: Literal["walking", "transit", "driving"] = "walking"
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_dates_and_times(self):
        if self.date:
            date.fromisoformat(self.date)
        minutes = []
        for value in (self.start_time, self.end_time):
            parts = value.split(":")
            if len(value) != 5 or len(parts) != 2 or not all(len(p) == 2 and p.isdigit() for p in parts):
                raise ValueError("时间必须为 HH:MM")
            h, m = map(int, parts)
            if not (0 <= h < 24 and 0 <= m < 60):
                raise ValueError("无效时间")
            minutes.append(h * 60 + m)
        if minutes[1] <= minutes[0]:
            raise ValueError("结束时间必须晚于开始时间（暂不支持跨日）")
        if any(not p.strip() or len(p) > 80 for p in self.preferences):
            raise ValueError("偏好必须为 1-80 字符")
        self.city = self.city.strip()
        return self


class ResearchTask(StrictModel):
    id: str
    query: str = Field(min_length=1, max_length=80)


class ResearchPlan(StrictModel):
    tasks: list[ResearchTask] = Field(min_length=1, max_length=3)


class EvidencePOI(StrictModel):
    id: str
    name: str
    address: str = ""
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    visit_minutes: int = Field(default=90, ge=15, le=360)
    estimated_ticket_cost: float = Field(default=0, ge=0)
    source: Literal["amap", "fixture"]
    source_url: str = ""
    fetched_at: str


class ResearchResult(StrictModel):
    task_id: str
    pois: list[EvidencePOI] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    tool_calls: int = 0
    model_calls: int = 0


class PlanStop(StrictModel):
    poi_id: str
    visit_minutes: int = Field(default=90, ge=15, le=360)
    reason: str = Field(default="", max_length=300)


class PlanDraft(StrictModel):
    stops: list[PlanStop] = Field(min_length=1, max_length=6)
    summary: str = Field(max_length=1500)
    caveats: list[str] = Field(default_factory=list, max_length=10)


class RunRequest(StrictModel):
    brief: TravelBrief
    mode: Literal["demo", "live"] = "live"
    provider: Literal["deepseek", "aliyun", "openai"] = "deepseek"


class ResumeRequest(StrictModel):
    interrupt_id: str
    action: Literal["clarify", "approve", "revise", "reject"]
    brief: TravelBrief | None = None
