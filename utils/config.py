import re
import os
import platform

# Windows için özel düzeltme
if platform.system() == 'Windows':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Data klasörü oluşturma
if not os.path.exists('data'):
    os.makedirs('data')

# Ayarlar
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', ''),
    'port': os.getenv('MYSQL_PORT', '3306'),
    'user': os.getenv('MYSQL_USER', ''),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DATABASE', '')
}

SQLITE_DB_PATH = 'data/ayfilter_data.db'
LOG_PATH = 'data/aybot_crawler.log'
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.60',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
]

SPAM_KEYWORDS = ['xxx', 'viagra', 'casino', 'porn', 'adult']
SKIP_EXTENSIONS = re.compile(r'\.(jpg|jpeg|png|gif|pdf|zip|rar|exe|mp4|mp3|avi|wmv|svg|css|js|woff2?|ico)$', re.IGNORECASE)
DOMAIN_LIMIT = 50
MAX_CONCURRENT_REQUESTS = 5
REQUEST_TIMEOUT = 20
ROBOTS_TIMEOUT = 3
JS_RENDER_THRESHOLD = 3
MIN_CONTENT_LENGTH = 50
MAX_ERROR_COUNT = 3

# Özel domain ayarları
PRIORITY_DOMAINS = ['haberler.com']
PRIORITY_INTERVAL = 48 * 3600
WHITELISTED_DOMAINS = ['gov.tr', 'edu.tr', 'tbb.org.tr', 'gov', 'edu']