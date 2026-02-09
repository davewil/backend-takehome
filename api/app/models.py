from __future__ import annotations
from pydantic import BaseModel
from typing import Any

class Lesson(BaseModel):
    id: int
    slug: str
    title: str

class Variant(BaseModel):
    id: int
    tenant_id: int | None
    data: dict[str, Any]
    
class LessonBlock(BaseModel):
    id: int
    type: str
    position: int
    variant: Variant
    user_progress: str | None = None
    
class ProgressSummary(BaseModel):
    total_blocks: int
    seen_blocks: int
    completed_blocks: int
    last_seen_block_id: int | None = None
    completed: bool
    
class LessonResponse(BaseModel):
    lesson: Lesson
    blocks: list[LessonBlock]
    progress_summary: ProgressSummary

class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail