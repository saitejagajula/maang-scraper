import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from db import (
    setup_jobs_table,
    save_jobs,
    get_all_jobs,
    get_all_users,
    get_user_by_id,
    get_jobs_for_user,
    cleanup_stale_jobs,
)
from scraper_engine import scrape_for_profile, scrape_all_profiles

load_dotenv()

scheduler = AsyncIOScheduler()

# Track which users already have jobs scraped (in-memory, resets on restart)
scraped_users: set[str] = set()


# ─── Nightly Full Scrape ───────────────────────────────────────────────────────

async def nightly_scrape():
    """Runs every midnight — scrapes jobs for ALL user profiles."""
    print("\n🌙 Nightly scrape started...")

    users = await get_all_users()
    print(f"  👥 Found {len(users)} users in DB")

    if not users:
        print("  ⚠️  No users found — using defaults")

    jobs = await scrape_all_profiles(users)
    await save_jobs(jobs)
    await cleanup_stale_jobs()

    # Mark all users as scraped
    for user in users:
        scraped_users.add(user["id"])

    print(f"✅ Nightly scrape done — {len(jobs)} jobs saved\n")


# ─── Instant Scrape for New User ──────────────────────────────────────────────

async def instant_scrape_for_user(user_id: str):
    """
    Triggered immediately when a new user completes onboarding.
    Scrapes jobs just for their profile so they don't wait until midnight.
    """
    print(f"\n⚡ Instant scrape triggered for user: {user_id}")

    user = await get_user_by_id(user_id)
    if not user:
        print(f"  ❌ User {user_id} not found")
        return

    companies = user.get("targetCompanies") or []
    roles     = user.get("targetRoles")     or []

    print(f"  🏢 Companies: {companies}")
    print(f"  💼 Roles: {roles}")

    jobs = await scrape_for_profile(companies, roles)
    await save_jobs(jobs)

    scraped_users.add(user_id)
    print(f"  ✅ Instant scrape done — {len(jobs)} jobs saved for {user.get('name')}\n")


# ─── FastAPI App ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await setup_jobs_table()

    # Schedule nightly scrape at midnight
    scheduler.add_job(
        nightly_scrape,
        "cron",
        hour=0,
        minute=0,
        id="nightly_scrape",
    )
    scheduler.start()
    print("⏰ Scheduler started — nightly scrape at midnight")

    yield

    scheduler.shutdown()


app = FastAPI(
    title="MAANG Job Scraper",
    description="Profile-linked job scraper for MAANG companies",
    lifespan=lifespan,
)


# ─── Request Models ───────────────────────────────────────────────────────────

class NewUserRequest(BaseModel):
    user_id: str


class ManualProfileRequest(BaseModel):
    companies: list[str]
    roles:     list[str]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "scraped_users": len(scraped_users)}


@app.post("/scrape/new-user")
async def scrape_new_user(req: NewUserRequest, background_tasks: BackgroundTasks):
    """
    Called by Next.js when a new user completes onboarding.
    Immediately starts scraping in the background — non-blocking.
    User gets jobs within 2-3 minutes without waiting for midnight.
    """
    if req.user_id in scraped_users:
        return {"status": "already_scraped", "user_id": req.user_id}

    background_tasks.add_task(instant_scrape_for_user, req.user_id)
    return {"status": "scraping_started", "user_id": req.user_id, "eta_minutes": 3}


@app.post("/scrape/run")
async def manual_full_scrape(background_tasks: BackgroundTasks):
    """Manually trigger the full nightly scrape — for testing/admin."""
    background_tasks.add_task(nightly_scrape)
    return {"status": "started", "message": "Full scrape running in background"}


@app.post("/scrape/profile")
async def scrape_custom_profile(req: ManualProfileRequest, background_tasks: BackgroundTasks):
    """Scrape jobs for a custom company+role combo — for testing."""
    async def run():
        jobs = await scrape_for_profile(req.companies, req.roles)
        await save_jobs(jobs)
    background_tasks.add_task(run)
    return {"status": "started", "companies": req.companies, "roles": req.roles}


@app.get("/jobs")
async def list_jobs(company: str = None, limit: int = 100):
    """Return all scraped jobs, optionally filtered by company."""
    jobs = await get_all_jobs(limit=limit)
    if company:
        jobs = [j for j in jobs if j["company"].lower() == company.lower()]
    return {"total": len(jobs), "jobs": jobs}


@app.get("/jobs/for-user/{user_id}")
async def jobs_for_user(user_id: str):
    """
    Return scraped jobs matched to a specific user's target companies.
    Called by Next.js /api/jobs to get personalized jobs.
    """
    user = await get_user_by_id(user_id)
    if not user:
        return {"error": "User not found"}, 404

    companies = user.get("targetCompanies") or []
    jobs = await get_jobs_for_user(companies)

    return {
        "total":    len(jobs),
        "jobs":     jobs,
        "user":     user.get("name"),
        "companies": companies,
    }


@app.get("/jobs/stats")
async def job_stats():
    """Count of jobs per company in DB."""
    jobs = await get_all_jobs(limit=10000)
    stats = {}
    for job in jobs:
        company = job["company"]
        stats[company] = stats.get(company, 0) + 1
    return {"stats": stats, "total": len(jobs)}


@app.get("/users")
async def list_users():
    """List all users from shared DB — for admin/debugging."""
    users = await get_all_users()
    return {"total": len(users), "users": [
        {"id": u["id"], "name": u["name"], "companies": u["targetCompanies"]}
        for u in users
    ]}
