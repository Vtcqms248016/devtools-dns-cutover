from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class CutoverPhase(StrEnum):
    PLANNED = "planned"
    RELEASED = "released"
    ROLLED_BACK = "rolled_back"


class CutoverRequest(BaseModel):
    domain: str = Field(min_length=1, examples=["example.com"])
    name: str = Field(min_length=1, examples=["tools"])
    record_type: Literal["A", "CNAME"]
    content: str = Field(min_length=1)
    ttl: int = Field(default=60, ge=30, le=300)
    build_id: str = Field(min_length=1)


class BuildEvent(BaseModel):
    build_id: str
    status: Literal["ready"] = "ready"


class ReleaseOperation(BaseModel):
    phase: CutoverPhase
    zone_id: str
    previous_record: dict[str, Any] | None
    active_record: dict[str, Any]


class Diagnostic(BaseModel):
    check: str
    status: Literal["pass", "attention"]
    detail: str


class CutoverResult(BaseModel):
    build: BuildEvent
    release: ReleaseOperation
    diagnostics: list[Diagnostic]
