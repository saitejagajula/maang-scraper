import asyncio
import random
from playwright.async_api import async_playwright

BASE_URL = "https://jobs.netflix.com"


async def scrape_netflix(search_query: str = "software engineer") -> list[dict]:
    jobs = []
    print(f"    🔍 Netflix → '{search_query}'")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        try:
            url = f"{BASE_URL}/jobs?q={search_query.replace(' ', '+')}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(random.uniform(2, 3))

            for _ in range(3):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(1)

            # Try multiple selectors
            cards = await page.query_selector_all("li.css-1tlfecm")
            if not cards:
                cards = await page.query_selector_all("[data-testid='job-result']")
            if not cards:
                cards = await page.query_selector_all("a[href*='/jobs/']")

            for card in cards:
                try:
                    title_el    = await card.query_selector("span.css-1vkalcuni, h2, h3, span[class*='title']")
                    location_el = await card.query_selector("span.css-gg4vpm, span[class*='location']")
                    link_el     = await card.query_selector("a")

                    title    = await title_el.inner_text()    if title_el    else None
                    location = await location_el.inner_text() if location_el else ""
                    href     = await link_el.get_attribute("href") if link_el else None

                    if title and href:
                        full_url = BASE_URL + href if href.startswith("/") else href
                        jobs.append({
                            "title":     title.strip(),
                            "company":   "Netflix",
                            "location":  location.strip(),
                            "is_remote": "remote" in location.lower(),
                            "url":       full_url,
                            "source":    "jobs.netflix.com",
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"    ❌ Netflix error: {e}")
        finally:
            await browser.close()

    print(f"    ✅ Netflix: {len(jobs)} jobs")
    return jobs
