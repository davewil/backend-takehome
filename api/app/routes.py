from __future__ import annotations

import json

from .models import (
    Lesson, 
    LessonBlock,
    LessonResponse,
    ProgressSummary,
    Variant,
    ErrorResponse,
    ErrorDetail
)
from .queries import (
    get_lesson,
    get_assembled_blocks,
    get_progress_summary,
    validate_user_access
)

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump())

def build_progress_summary(row) -> ProgressSummary:
    total = row["total_blocks"]
    completed = row["completed_blocks"]
    return ProgressSummary(
        total_blocks=total,
        seen_blocks=row["seen_blocks"],
        completed_blocks=completed,
        last_seen_block_id=row["last_seen_block_id"],
        completed=total > 0 and completed == total,
    )

@router.get("/tenants/{tenant_id}/users/{user_id}/lessons/{lesson_id}")
async def get_lesson_content(tenant_id: int, user_id:int, lesson_id: int, request: Request):
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        ok, msg = await validate_user_access(conn, tenant_id, user_id, lesson_id)
        if not ok:
            return error_response(404, "not_found", msg)

        lesson_row = await get_lesson(conn, lesson_id)
        block_rows = await get_assembled_blocks(conn, lesson_id, tenant_id, user_id)
        progress_row = await get_progress_summary(conn, lesson_id, user_id)
        
    blocks = [
        LessonBlock(
            id=r["block_id"],
            type=r["block_type"],
            position=r["position"],
            variant=Variant(
                id=r["variant_id"],
                tenant_id=r["variant_tenant_id"],
                data=json.loads(r["variant_data"])
            ),
            user_progress=r["user_progress"]
        )
        for r in block_rows
    ]

    return LessonResponse(
        lesson=Lesson(
            id=lesson_row["id"],
            slug=lesson_row["slug"],
            title=lesson_row["title"]
        ),
        blocks=blocks,
        progress_summary=build_progress_summary(progress_row)
    )