import asyncpg
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


async def get_conn():
    return await asyncpg.connect(DATABASE_URL)


async def setup_jobs_table():
    """Create scraped_jobs table if it doesn't exist."""
    conn = await get_conn()
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS scraped_jobs (
            id           TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            company      TEXT NOT NULL,
            location     TEXT,
            is_remote    BOOLEAN DEFAULT FALSE,
            url          TEXT UNIQUE NOT NULL,
            description  TEXT,
            salary_min   INTEGER,
            salary_max   INTEGER,
            source       TEXT,
            tags         TEXT[],
            scraped_at   TIMESTAMP DEFAULT NOW()
        )
    """)

    # Add tags column if it doesn't exist (for existing tables)
    await conn.execute("""
        ALTER TABLE scraped_jobs
        ADD COLUMN IF NOT EXISTS tags TEXT[]
    """)

    await conn.close()
    print("✅ scraped_jobs table ready")


async def get_all_users() -> list[dict]:
    """Read all user profiles from the User table (shared Neon DB)."""
    conn = await get_conn()
    rows = await conn.fetch("""
        SELECT
            id,
            name,
            email,
            "targetCompanies",
            "targetRoles",
            "yearsOfExperience",
            skills
        FROM "User"
        WHERE "hasCompletedOnboarding" = TRUE
    """)
    await conn.close()
    return [dict(row) for row in rows]


async def get_user_by_id(user_id: str) -> dict | None:
    """Read a single user profile by ID."""
    conn = await get_conn()
    row = await conn.fetchrow("""
        SELECT
            id,
            name,
            email,
            "targetCompanies",
            "targetRoles",
            "yearsOfExperience",
            skills
        FROM "User"
        WHERE id = $1
    """, user_id)
    await conn.close()
    return dict(row) if row else None


async def save_jobs(jobs: list[dict]):
    if not jobs:
        return

    conn = await get_conn()
    saved = 0

    for job in jobs:
        try:
            await conn.execute("""
                INSERT INTO scraped_jobs
                    (id, title, company, location, is_remote, url, description, tags, source, scraped_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                ON CONFLICT (url)
                DO UPDATE SET
                    title      = EXCLUDED.title,
                    location   = EXCLUDED.location,
                    is_remote  = EXCLUDED.is_remote,
                    description= EXCLUDED.description,
                    tags       = EXCLUDED.tags,
                    scraped_at = NOW()
            """,
            str(uuid.uuid4()),
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
            job.get("is_remote", False),
            job.get("url", ""),
            job.get("description", ""),
            job.get("tags", []),
            job.get("source", ""),
            )
            saved += 1
        except Exception as e:
            print(f"  ⚠️  Failed to save: {job.get('title')} → {e}")

    await conn.close()
    print(f"  💾 Saved {saved}/{len(jobs)} jobs to DB")


async def cleanup_stale_jobs():
    """Remove jobs not seen in the last 2 days."""
    conn = await get_conn()
    result = await conn.execute("""
        DELETE FROM scraped_jobs
        WHERE scraped_at < NOW() - INTERVAL '2 days'
    """)
    await conn.close()
    print(f"  🗑️  Cleaned up stale jobs: {result}")


async def get_jobs_for_user(companies: list[str], limit: int = 100) -> list[dict]:
    """Fetch scraped jobs matching user's target companies."""
    conn = await get_conn()
    rows = await conn.fetch("""
        SELECT * FROM scraped_jobs
        WHERE company = ANY($1::text[])
        ORDER BY scraped_at DESC
        LIMIT $2
    """, companies, limit)
    await conn.close()
    return [dict(row) for row in rows]


async def get_all_jobs(limit: int = 200) -> list[dict]:
    conn = await get_conn()
    rows = await conn.fetch(
        "SELECT * FROM scraped_jobs ORDER BY scraped_at DESC LIMIT $1", limit
    )
    await conn.close()
    return [dict(row) for row in rows]
