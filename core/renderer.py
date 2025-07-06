import asyncio
import sys
import random
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from langdetect import detect
from datetime import datetime
from utils.logger import logger
from utils.config import USER_AGENTS, REQUEST_TIMEOUT

# Windows'ta Playwright subprocess hatası için event loop politikası
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def fetch_with_js(url):
    browser = None
    try:
        logger.info(f"[JS Render] Sayfa yükleniyor (Playwright): {url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                ignore_https_errors=True,
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()

            # Bot tespitini azaltmak için navigator ayarları
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => false});
                window.navigator.chrome = { runtime: {} };
            """)

            await page.goto(url, timeout=REQUEST_TIMEOUT * 1000, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1, 3))

            # Basit scroll
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(0.3)
            await page.evaluate("window.scrollBy(0, 1000)")
            await asyncio.sleep(0.3)

            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            title = soup.title.string.strip() if soup.title else 'No Title'

            for tag in soup(["script", "style", "noscript", "meta", "link", "header", "footer", "nav"]):
                tag.decompose()

            text = soup.get_text(separator=' ', strip=True)
            lang = 'unknown'

            if text and len(text) > 100:
                try:
                    lang = detect(text[:500])
                except:
                    pass

            return title, text, lang, datetime.utcnow().isoformat()

    except Exception as e:
        logger.error(f"[JS Render] Playwright hatası: {url} - {str(e)}", exc_info=True)
        return None, None, None, None

    finally:
        if browser:
            await browser.close()
