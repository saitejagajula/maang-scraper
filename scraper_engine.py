"""
Smart scraper engine.
- Builds queries from user profiles
- Runs scrapers per company + role combo
- Tags jobs with role keywords
"""

import asyncio
from scrapers.google    import scrape_google
from scrapers.meta      import scrape_meta
from scrapers.amazon    import scrape_amazon
from scrapers.apple     import scrape_apple
from scrapers.netflix   import scrape_netflix
from scrapers.microsoft import scrape_microsoft

SCRAPER_MAP = {
    "Google":    scrape_google,
    "Meta":      scrape_meta,
    "Amazon":    scrape_amazon,
    "Apple":     scrape_apple,
    "Netflix":   scrape_netflix,
    "Microsoft": scrape_microsoft,
}

# Role → search keywords
ROLE_KEYWORDS = {
    "Software Engineer":        ["software engineer"],
    "Senior Software Engineer": ["senior software engineer", "senior engineer"],
    "Staff Engineer":           ["staff engineer", "staff software engineer"],
    "Principal Engineer":       ["principal engineer"],
    "Machine Learning Engineer":["machine learning engineer", "ml engineer"],
    "Data Engineer":            ["data engineer"],
    "DevOps / SRE":             ["devops", "site reliability", "sre", "platform engineer"],
    "Engineering Manager":      ["engineering manager"],
}

DEFAULT_ROLES = ["Software Engineer", "Senior Software Engineer", "Machine Learning Engineer"]
DEFAULT_COMPANIES = list(SCRAPER_MAP.keys())


def build_queries(companies: list[str], roles: list[str]) -> list[tuple[str, str, list[str]]]:
    """
    Returns list of (company, search_query, tags).
    Deduplicates identical company+query combos.
    """
    seen = set()
    queries = []

    for company in companies:
        if company not in SCRAPER_MAP:
            continue
        role_list = roles if roles else DEFAULT_ROLES
        for role in role_list:
            keywords = ROLE_KEYWORDS.get(role, [role.lower()])
            for keyword in keywords:
                key = f"{company}::{keyword}"
                if key not in seen:
                    seen.add(key)
                    tags = [company.lower(), keyword] + role.lower().split()
                    queries.append((company, keyword, list(set(tags))))

    return queries


async def scrape_for_profile(
    companies: list[str],
    roles: list[str],
) -> list[dict]:
    """Run scrapers for a specific user profile (companies + roles)."""

    queries = build_queries(companies, roles)
    print(f"  📋 Queries to run: {len(queries)}")

    all_jobs = []

    for company, keyword, tags in queries:
        scraper_fn = SCRAPER_MAP.get(company)
        if not scraper_fn:
            continue
        try:
            print(f"  🔍 {company} — '{keyword}'")
            jobs = await scraper_fn(search_query=keyword)
            # Attach tags to each job
            for job in jobs:
                job["tags"] = tags
            all_jobs.extend(jobs)
            # Small delay between scrapers to be polite
            await asyncio.sleep(2)
        except Exception as e:
            print(f"  ❌ {company} '{keyword}' failed: {e}")

    print(f"  ✅ Total scraped: {len(all_jobs)} jobs")
    return all_jobs


async def scrape_all_profiles(users: list[dict]) -> list[dict]:
    """
    Build a unified query set from ALL user profiles,
    deduplicate, then scrape once per unique combo.
    """
    all_companies = set()
    all_roles = set()

    for user in users:
        for c in (user.get("targetCompanies") or []):
            all_companies.add(c)
        for r in (user.get("targetRoles") or []):
            all_roles.add(r)

    # Fall back to defaults if no profiles have data
    companies = list(all_companies) if all_companies else DEFAULT_COMPANIES
    roles     = list(all_roles)     if all_roles     else DEFAULT_ROLES

    print(f"  🏢 Companies: {companies}")
    print(f"  💼 Roles: {roles}")

    return await scrape_for_profile(companies, roles)
