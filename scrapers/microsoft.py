import asyncio
import random
from playwright.async_api import async_playwright

BASE_URL = "https://jobs.careers.microsoft.com"


async def scrape_microsoft(search_query: str = "software engineer") -> list[dict]:
    jobs = []
    print(f"    🔍 Microsoft → '{search_query}'")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        try:
            url = (
                f"{BASE_URL}/global/en/search"
                f"?q={search_query.replace(' ', '%20')}"
                f"&lc=United%20States&l=en_us&pg=1&pgSz=20&o=Recent"
            )
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(random.uniform(2, 3))

            cards = await page.query_selector_all("div.ms-List-cell")

            for card in cards:
                try:
                    title_el    = await card.query_selector("h2")
                    location_el = await card.query_selector("span[aria-label*='location'], .location")
                    link_el     = await card.query_selector("a")

                    title    = await title_el.inner_text()    if title_el    else None
                    location = await location_el.inner_text() if location_el else ""
                    href     = await link_el.get_attribute("href") if link_el else None

                    if title and href:
                        full_url = href if href.startswith("http") else BASE_URL + href
                        jobs.append({
                            "title":     title.strip(),
                            "company":   "Microsoft",
                            "location":  location.strip(),
                            "is_remote": "remote" in location.lower(),
                            "url":       full_url,
                            "source":    "careers.microsoft.com",
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"    ❌ Microsoft error: {e}")
        finally:
            await browser.close()

    print(f"    ✅ Microsoft: {len(jobs)} jobs")
    return jobs
