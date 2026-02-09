from __future__ import annotations
import asyncpg  

async def get_lesson(conn: asyncpg.Connection, lesson_id: int) -> asyncpg.Record | None:
    query = "SELECT id, slug, title FROM lessons WHERE id = $1"
    return await conn.fetchrow(query, lesson_id)
    
async def get_assembled_blocks(conn: asyncpg.Connection, lesson_id: int, tenant_id: int, user_id: int) -> list[asyncpg.Record]:
    query = """
        SELECT
            b.id            AS block_id,
            b.block_type,
            lb.position,
            bv.id           AS variant_id,
            bv.tenant_id    AS variant_tenant_id,
            bv.data         AS variant_data,
            ubp.status      AS user_progress
        FROM lesson_blocks lb
        JOIN blocks b ON b.id = lb.block_id
        JOIN LATERAL (
            SELECT bv2.id, bv2.tenant_id, bv2.data
            FROM block_variants bv2
            WHERE bv2.block_id = b.id
              AND (bv2.tenant_id = $2 OR bv2.tenant_id IS NULL)
            ORDER BY bv2.tenant_id NULLS LAST
            LIMIT 1
        ) bv ON true
        LEFT JOIN user_block_progress ubp
            ON ubp.user_id = $3
           AND ubp.lesson_id = $1
           AND ubp.block_id = b.id
        WHERE lb.lesson_id = $1
        ORDER BY lb.position
        """
    return await conn.fetch(query, lesson_id, tenant_id, user_id)
    
async def get_progress_summary(conn: asyncpg.Connection, user_id: int, lesson_id: int) -> asyncpg.Record:
    query ="""
        SELECT
            (SELECT count(*) FROM lesson_blocks WHERE lesson_id = $2)::int
                AS total_blocks,
            count(*) FILTER (WHERE ubp.status IN ('seen', 'completed'))::int
                AS seen_blocks,
            count(*) FILTER (WHERE ubp.status = 'completed')::int
                AS completed_blocks,
            (
                SELECT ubp2.block_id
                FROM user_block_progress ubp2
                JOIN lesson_blocks lb2
                    ON lb2.lesson_id = $2 AND lb2.block_id = ubp2.block_id
                WHERE ubp2.user_id = $1 AND ubp2.lesson_id = $2
                ORDER BY lb2.position DESC
                LIMIT 1
            ) AS last_seen_block_id
        FROM lesson_blocks lb
        LEFT JOIN user_block_progress ubp
            ON ubp.user_id = $1
           AND ubp.lesson_id = $2
           AND ubp.block_id = lb.block_id
        WHERE lb.lesson_id = $2
        """
    return await conn.fetchrow(query, user_id, lesson_id)

async def validate_user_access(
    conn: asyncpg.Connection,
    tenant_id: int,
    user_id: int,
    lesson_id: int,
) -> tuple[bool, str]:
    row = await conn.fetchrow("SELECT 1 FROM tenants WHERE id = $1", tenant_id)
    if not row:
        return False, "Tenant not found"

    row = await conn.fetchrow(
        "SELECT 1 FROM users WHERE id = $1 AND tenant_id = $2", user_id, tenant_id
    )
    if not row:
        return False, "User not found or does not belong to tenant"

    row = await conn.fetchrow(
        "SELECT 1 FROM lessons WHERE id = $1 AND tenant_id = $2", lesson_id, tenant_id
    )
    if not row:
        return False, "Lesson not found or does not belong to tenant"

    return True, ""
    
async def upsert_progress(
    conn: asyncpg.Connection,
    user_id: int,
    lesson_id: int,
    block_id: int,
    status: str,
) -> str:
    query ="""
        INSERT INTO user_block_progress (user_id, lesson_id, block_id, status, updated_at)
        VALUES ($1, $2, $3, $4, now())
        ON CONFLICT (user_id, lesson_id, block_id) DO UPDATE
            SET status = CASE
                    WHEN user_block_progress.status = 'completed' THEN 'completed'
                    ELSE EXCLUDED.status
                END,
                updated_at = now()
        RETURNING status
        """
    row = await conn.fetchrow(query, user_id, lesson_id, block_id, status)
    return row["status"]

async def validate_block_in_lesson(
    conn: asyncpg.Connection, lesson_id: int, block_id: int
) -> bool:
    query = "SELECT 1 FROM lesson_blocks WHERE lesson_id = $1 AND block_id = $2"
    row = await conn.fetchrow(query,
        lesson_id,
        block_id,
    )
    return row is not None