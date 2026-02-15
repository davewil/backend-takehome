from __future__ import annotations

from sqlalchemy import Integer, case, func, literal_column, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import (
    Block,
    BlockVariant,
    Lesson,
    LessonBlock,
    Tenant,
    User,
    UserBlockProgress,
)


async def get_lesson(session: AsyncSession, lesson_id: int):
    result = await session.get(Lesson, lesson_id)
    return result


async def get_assembled_blocks(
    session: AsyncSession, lesson_id: int, tenant_id: int, user_id: int
) -> list:
    # LATERAL subquery for best variant per block
    variant_subq = (
        select(
            BlockVariant.id,
            BlockVariant.tenant_id,
            BlockVariant.data,
        )
        .where(
            BlockVariant.block_id == Block.id,
            (BlockVariant.tenant_id == tenant_id) | (BlockVariant.tenant_id.is_(None)),
        )
        .order_by(BlockVariant.tenant_id.nulls_last())
        .limit(1)
        .lateral("bv")
    )

    stmt = (
        select(
            Block.id.label("block_id"),
            Block.block_type,
            LessonBlock.position,
            variant_subq.c.id.label("variant_id"),
            variant_subq.c.tenant_id.label("variant_tenant_id"),
            variant_subq.c.data.label("variant_data"),
            UserBlockProgress.status.label("user_progress"),
        )
        .select_from(LessonBlock)
        .join(Block, Block.id == LessonBlock.block_id)
        .join(variant_subq, literal_column("true"))
        .outerjoin(
            UserBlockProgress,
            (UserBlockProgress.user_id == user_id)
            & (UserBlockProgress.lesson_id == lesson_id)
            & (UserBlockProgress.block_id == Block.id),
        )
        .where(LessonBlock.lesson_id == lesson_id)
        .order_by(LessonBlock.position)
    )

    result = await session.execute(stmt)
    return result.all()


async def get_progress_summary(
    session: AsyncSession, user_id: int, lesson_id: int
):
    total_subq = (
        select(func.count())
        .select_from(LessonBlock)
        .where(LessonBlock.lesson_id == lesson_id)
        .correlate()
        .scalar_subquery()
    )

    last_seen_subq = (
        select(UserBlockProgress.block_id)
        .join(
            LessonBlock,
            (LessonBlock.lesson_id == lesson_id)
            & (LessonBlock.block_id == UserBlockProgress.block_id),
        )
        .where(
            UserBlockProgress.user_id == user_id,
            UserBlockProgress.lesson_id == lesson_id,
        )
        .order_by(LessonBlock.position.desc())
        .limit(1)
        .correlate()
        .scalar_subquery()
    )

    stmt = (
        select(
            total_subq.cast(Integer).label("total_blocks"),
            func.count()
            .filter(UserBlockProgress.status.in_(["seen", "completed"]))
            .cast(Integer)
            .label("seen_blocks"),
            func.count()
            .filter(UserBlockProgress.status == "completed")
            .cast(Integer)
            .label("completed_blocks"),
            last_seen_subq.label("last_seen_block_id"),
        )
        .select_from(LessonBlock)
        .outerjoin(
            UserBlockProgress,
            (UserBlockProgress.user_id == user_id)
            & (UserBlockProgress.lesson_id == lesson_id)
            & (UserBlockProgress.block_id == LessonBlock.block_id),
        )
        .where(LessonBlock.lesson_id == lesson_id)
    )

    result = await session.execute(stmt)
    return result.one()


async def validate_user_access(
    session: AsyncSession,
    tenant_id: int,
    user_id: int,
    lesson_id: int,
) -> tuple[bool, str]:
    row = (await session.execute(
        select(Tenant.id).where(Tenant.id == tenant_id)
    )).first()
    if not row:
        return False, "Tenant not found"

    row = (await session.execute(
        select(User.id).where(User.id == user_id, User.tenant_id == tenant_id)
    )).first()
    if not row:
        return False, "User not found or does not belong to tenant"

    row = (await session.execute(
        select(Lesson.id).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id)
    )).first()
    if not row:
        return False, "Lesson not found or does not belong to tenant"

    return True, ""


async def upsert_progress(
    session: AsyncSession,
    user_id: int,
    lesson_id: int,
    block_id: int,
    status: str,
) -> str:
    stmt = (
        pg_insert(UserBlockProgress)
        .values(
            user_id=user_id,
            lesson_id=lesson_id,
            block_id=block_id,
            status=status,
            updated_at=func.now(),
        )
        .on_conflict_do_update(
            index_elements=["user_id", "lesson_id", "block_id"],
            set_={
                "status": case(
                    (UserBlockProgress.status == "completed", "completed"),
                    else_=text("EXCLUDED.status"),
                ),
                "updated_at": func.now(),
            },
        )
        .returning(UserBlockProgress.status)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def validate_block_in_lesson(
    session: AsyncSession, lesson_id: int, block_id: int
) -> bool:
    row = (await session.execute(
        select(LessonBlock.block_id).where(
            LessonBlock.lesson_id == lesson_id,
            LessonBlock.block_id == block_id,
        )
    )).first()
    return row is not None
