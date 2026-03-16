import asyncio
import random
from playwright.async_api import async_playwright

BASE_URL = "https://www.amazon.jobs"


async def scrape_amazon(search_query: str = "software engineer") -> list[dict]:
    jobs = []
    print(f"    🔍 Amazon → '{search_query}'")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        try:
            url = (
                f"{BASE_URL}/en/search"
                f"?base_query={search_query.replace(' ', '+')}"
                f"&result_limit=50&sort=recent"
                f"&category[]=software-development"
            )
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(random.uniform(2, 3))

            cards = await page.query_selector_all(".job-tile")

            for card in cards:
                try:
                    title_el    = await card.query_selector("h3.job-title a, h3 a")
                    location_el = await card.query_selector(".location-and-id, .location")
                    link_el     = await card.query_selector("a.job-link, h3 a")

                    title    = await title_el.inner_text()    if title_el    else None
                    location = await location_el.inner_text() if location_el else ""
                    href     = await link_el.get_attribute("href") if link_el else None

                    if title and href:
                        full_url = BASE_URL + href if href.startswith("/") else href
                        jobs.append({
                            "title":     title.strip(),
                            "company":   "Amazon",
                            "location":  location.strip(),
                            "is_remote": "remote" in location.lower(),
                            "url":       full_url,
                            "source":    "amazon.jobs",
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"    ❌ Amazon error: {e}")
        finally:
            await browser.close()

    print(f"    ✅ Amazon: {len(jobs)} jobs")
    return jobs
