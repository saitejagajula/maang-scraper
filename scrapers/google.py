import asyncio
import random
from playwright.async_api import async_playwright

BASE_URL = "https://careers.google.com"


async def scrape_google(search_query: str = "software engineer") -> list[dict]:
    jobs = []
    print(f"    🔍 Google → '{search_query}'")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        try:
            url = (
                f"{BASE_URL}/jobs/results/"
                f"?q={search_query.replace(' ', '+')}"
                f"&category=SOFTWARE_ENGINEERING"
                f"&employment_type=FULL_TIME"
            )
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(random.uniform(2, 3))

            for _ in range(3):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(random.uniform(1, 2))

            cards = await page.query_selector_all("li.lLd3Je")

            for card in cards:
                try:
                    title_el    = await card.query_selector("h3.QJPWVe")
                    location_el = await card.query_selector(".r0wTof")
                    link_el     = await card.query_selector("a.WpHeLc")

                    title    = await title_el.inner_text()    if title_el    else None
                    location = await location_el.inner_text() if location_el else ""
                    href     = await link_el.get_attribute("href") if link_el else None

                    if title and href:
                        jobs.append({
                            "title":     title.strip(),
                            "company":   "Google",
                            "location":  location.strip(),
                            "is_remote": "remote" in location.lower(),
                            "url":       BASE_URL + href if href.startswith("/") else href,
                            "source":    "careers.google.com",
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"    ❌ Google error: {e}")
        finally:
            await browser.close()

    print(f"    ✅ Google: {len(jobs)} jobs")
    return jobs
