import asyncio
import random
from playwright.async_api import async_playwright

BASE_URL = "https://jobs.apple.com"


async def scrape_apple(search_query: str = "software engineer") -> list[dict]:
    jobs = []
    print(f"    🔍 Apple → '{search_query}'")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        try:
            url = f"{BASE_URL}/en-us/search?search={search_query.replace(' ', '+')}&sort=newest"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(random.uniform(2, 3))

            cards = await page.query_selector_all("tbody tr")

            for card in cards:
                try:
                    title_el    = await card.query_selector("td.table-col-1 a")
                    location_el = await card.query_selector("td.table-col-2")

                    title    = await title_el.inner_text()    if title_el    else None
                    location = await location_el.inner_text() if location_el else ""
                    href     = await title_el.get_attribute("href") if title_el else None

                    if title and href:
                        full_url = BASE_URL + href if href.startswith("/") else href
                        jobs.append({
                            "title":     title.strip(),
                            "company":   "Apple",
                            "location":  location.strip(),
                            "is_remote": "remote" in location.lower(),
                            "url":       full_url,
                            "source":    "jobs.apple.com",
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"    ❌ Apple error: {e}")
        finally:
            await browser.close()

    print(f"    ✅ Apple: {len(jobs)} jobs")
    return jobs
