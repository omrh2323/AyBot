from bs4 import BeautifulSoup
from urllib.parse import urljoin
from utils.helpers import normalize_url, is_valid_link
from utils.config import MIN_CONTENT_LENGTH, JS_RENDER_THRESHOLD
from utils.logger import logger
from langdetect import detect
import re

def extract_links(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    links = set()
    for a in soup.find_all('a', href=True):
        href = a.get('href', '').strip()
        if href and not href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            abs_url = urljoin(base_url, href)
            if is_valid_link(abs_url):
                links.add(normalize_url(abs_url))
    return list(links)

def extract_content(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    meta_robots = soup.find("meta", attrs={"name": "robots"})
    if meta_robots and "noindex" in meta_robots.get("content", "").lower():
        return None, None, None, None
    
    title = soup.title.string.strip() if soup.title else 'No Title'
    if not title or '404' in title.lower() or 'not found' in title.lower():
        return None, None, None, None
    
    script_count = len(soup.find_all('script'))
    
    for element in soup(["script", "style", "noscript", "meta", "link", "header", "footer", "nav"]):
        element.decompose()
        
    text = soup.get_text(separator=' ', strip=True)
    
    lang = 'unknown'
    if text and len(text) > 100:
        try:
            lang = detect(text[:500])
        except:
            pass
            
    return title, text, lang, script_count