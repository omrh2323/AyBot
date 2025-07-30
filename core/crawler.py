import aiohttp
import asyncio
import random
from .parser import extract_links, extract_content
from .renderer import fetch_with_js
from utils.helpers import is_spam, normalize_url
from utils.logger import logger
from utils.config import MIN_CONTENT_LENGTH, JS_RENDER_THRESHOLD, REQUEST_TIMEOUT, USER_AGENTS, ROBOTS_TIMEOUT
from database import sqlite_handler
from database import mysql_handler
from datetime import datetime
from tenacity import retry, wait_exponential, stop_after_attempt
from urllib.parse import urlparse

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(2),
    reraise=True
)
async def can_fetch(session, url):
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        try:
            async with session.get(robots_url, timeout=ROBOTS_TIMEOUT) as response:
                if response.status == 200:
                    content = await response.text()
                    disallowed = []
                    user_agents = ['*']
                    current_ua = None
                    
                    for line in content.split('\n'):
                        line = line.strip()
                        if not line: continue
                        
                        if line.lower().startswith('user-agent:'):
                            parts = line.split(':', 1)
                            if len(parts) > 1:
                                current_ua = parts[1].strip().lower()
                                if current_ua not in user_agents:
                                    current_ua = None
                        elif line.lower().startswith('disallow:') and current_ua is not None:
                            parts = line.split(':', 1)
                            if len(parts) > 1:
                                path = parts[1].strip()
                                if path:
                                    disallowed.append(path)
                    
                    for dis_path in disallowed:
                        if parsed.path.startswith(dis_path):
                            logger.info(f"Robots.txt engelledi: {url} (Path: {dis_path})")
                            return False
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.debug(f"Robots.txt hatası: {robots_url} - {str(e)}")
            return True
        
        return True
    except Exception as e:
        logger.error(f"Robots.txt kontrol hatası: {str(e)}", exc_info=True)
        return True

async def parse_sitemap(session, domain):
    sitemap_urls = [
        f"{domain}/sitemap.xml",
        f"{domain}/sitemap_index.xml",
        f"{domain}/sitemap"
    ]
    
    found_links = set()
    for sitemap_url in sitemap_urls:
        if not sitemap_url.startswith('http'):
            sitemap_url = f"https://{sitemap_url}"
        
        try:
            async with session.get(sitemap_url, timeout=10) as response:
                if response.status == 200:
                    content = await response.text()
                    if "<urlset" in content or "<sitemapindex" in content:
                        soup = BeautifulSoup(content, "xml")
                        
                        if soup.find("sitemapindex"):
                            sitemap_locs = [loc.text.strip() for loc in soup.find_all("loc")]
                            for loc in sitemap_locs:
                                if loc.startswith("http"):
                                    sub_domain = urlparse(loc).netloc
                                    found_links.update(await parse_sitemap(session, sub_domain))
                        else:
                            urls = [loc.text.strip() for loc in soup.find_all("loc")]
                            for url in urls:
                                if is_valid_link(url):
                                    found_links.add(url)
        except Exception as e:
            logger.debug(f"Sitemap hatası: {sitemap_url} - {str(e)}")
            continue
    
    return found_links

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(2),
    reraise=True
)
async def crawl_page(session, url):
    try:
        logger.info(f"Tarama başladı: {url}")
        
        if not await can_fetch(session, url):
            return [], None, None, None, None
        
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.google.com/',
            'DNT': '1' if random.random() > 0.5 else '0'
        }
        
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        
        try:
            async with session.get(
                url, 
                headers=headers, 
                timeout=timeout,
            ) as response:
                if response.status == 403 and "bot" in (await response.text()).lower():
                    logger.warning(f"Bot tuzaklı sayfa: {url}")
                    return [], None, None, None, None
                    
                if response.status != 200:
                    logger.info(f"HTTP {response.status} hatası: {url}")
                    return [], None, None, None, None
                    
                html = await response.text()
        except aiohttp.ClientConnectionError:
            logger.warning(f"Bağlantı hatası: {url}")
            return [], None, None, None, None
        except asyncio.TimeoutError:
            logger.warning(f"Zaman aşımı: {url}")
            return [], None, None, None, None
        except aiohttp.ClientPayloadError:
            logger.warning(f"Veri alma hatası: {url}")
            return [], None, None, None, None
        
        title, text, lang, script_count = extract_content(html)
        if not title:
            return [], None, None, None, None
            
        if len(text) < MIN_CONTENT_LENGTH and script_count > JS_RENDER_THRESHOLD:
            logger.info(f"JavaScript render gerekli ({script_count} script): {url}")
            js_title, js_text, js_lang, js_timestamp = await fetch_with_js(url)
            if js_text and len(js_text) >= MIN_CONTENT_LENGTH:
                title = js_title
                text = js_text
                lang = js_lang
                timestamp = js_timestamp
            else:
                return [], None, None, None, None
        else:
            if len(text) < MIN_CONTENT_LENGTH:
                logger.info(f"Yetersiz içerik: {url}")
                return [], None, None, None, None
                
            timestamp = datetime.utcnow().isoformat()
            
        if is_spam(text):
            logger.info(f"Spam içerik engellendi: {url}")
            return [], None, None, None, None
            
        links = extract_links(html, url)
        logger.info(f"{len(links)} yeni link bulundu")
        return links, title, text, lang, timestamp
        
    except Exception as e:
        logger.error(f"Tarama hatası: {url} - {str(e)}", exc_info=True)
        return [], None, None, None, None

async def process_url(session, item):
    try:
        url = item['url']
        domain = item.get('domain', urlparse(url).netloc)
        logger.info(f"İşleniyor: {url}")
        
        try:
            sitemap_links = await parse_sitemap(session, domain)
            if sitemap_links:
                logger.info(f"{domain} için {len(sitemap_links)} sitemap linki bulundu")
                mysql_handler.insert_links_bulk(sitemap_links)
        except Exception as e:
            logger.error(f"Sitemap tarama hatası: {url} - {str(e)}", exc_info=True)
        
        new_links, title, text, lang, timestamp = await crawl_page(session, url)
        if title and text:
            logger.info(f"Başarıyla taranan: {url} - {title[:50]}...")
            sqlite_handler.save_to_sqlite(url, title, text, lang, timestamp)
            if new_links:
                logger.info(f"{len(new_links)} yeni link bulundu, MySQL'e ekleniyor...")
                mysql_handler.insert_links_bulk(new_links)
            mysql_handler.mark_link_visited(item['id'])
        else:
            mysql_handler.mark_link_error(item['id'])
            
        logger.info(f"İşlem tamamlandı: {url}")
        
    except Exception as e:
        logger.error(f"URL işleme hatası: {url} - {str(e)}", exc_info=True)
        mysql_handler.mark_link_error(item['id'])
    finally:
        await asyncio.sleep(random.uniform(1, 4))