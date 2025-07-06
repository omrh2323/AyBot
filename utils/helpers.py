import re
from urllib.parse import urlparse, urljoin
from langdetect import detect, DetectorFactory
from .config import SPAM_KEYWORDS, SKIP_EXTENSIONS

# Langdetect stabilizasyonu
DetectorFactory.seed = 0

def is_spam(text):
    if not text:
        return True
        
    text_lower = text.lower()
    
    for keyword in SPAM_KEYWORDS:
        if text_lower.count(keyword) >= 5:
            return True
            
    http_count = text_lower.count('http')
    www_count = text_lower.count('www.')
    
    return http_count > 25 or www_count > 25

def is_valid_link(link):
    if not link:
        return False
    if link.startswith(("javascript:", "mailto:", "tel:")):
        return False
    return link.startswith("http") and not SKIP_EXTENSIONS.search(link)

def normalize_url(url):
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme or "http"
        netloc = parsed.netloc.lower().replace("www.", "")
        path = parsed.path.rstrip('/')
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{scheme}://{netloc}{path}{query}"
    except Exception:
        return url.strip()