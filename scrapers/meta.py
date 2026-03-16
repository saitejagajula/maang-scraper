import asyncio
import random
from playwright.async_api import async_playwright

BASE_URL = "https://www.metacareers.com"


async def scrape_meta(search_query: str = "software engineer") -> list[dict]:
    jobs = []
    print(f"    🔍 Meta → '{search_query}'")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        try:
            url = f"{BASE_URL}/jobs/?q={search_query.replace(' ', '%20')}&teams[0]=Engineering%2C%20Tech%20%26%20Design"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(random.uniform(2, 4))

            for _ in range(4):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(random.uniform(1, 2))

            # Try multiple possible selectors
            cards = await page.query_selector_all("div._9ata")
            if not cards:
                cards = await page.query_selector_all("[data-testid='job-listing-item']")
            if not cards:
                cards = await page.query_selector_all("a[href*='/jobs/']")

            for card in cards:
                try:
                    title_el    = await card.query_selector("._8muv, h2, h3")
                    location_el = await card.query_selector("._8mut, [data-testid='job-location']")
                    link_el     = await card.query_selector("a")

                    title    = await title_el.inner_text()    if title_el    else None
                    location = await location_el.inner_text() if location_el else ""
                    href     = await link_el.get_attribute("href") if link_el else None

                    if not title and card.tag_name == "a":
                        title = await card.inner_text()
                        href  = await card.get_attribute("href")

                    if title and href:
                        full_url = BASE_URL + href if href.startswith("/") else href
                        jobs.append({
                            "title":     title.strip()[:200],
                            "company":   "Meta",
                            "location":  location.strip(),
                            "is_remote": "remote" in location.lower(),
                            "url":       full_url,
                            "source":    "metacareers.com",
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"    ❌ Meta error: {e}")
        finally:
            await browser.close()

    print(f"    ✅ Meta: {len(jobs)} jobs")
    return jobs
