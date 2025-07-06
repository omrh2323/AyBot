import sqlite3
from utils.logger import logger
from utils.config import SQLITE_DB_PATH

def save_to_sqlite(url, title, text, lang, timestamp):
    conn = None
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH, timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                content TEXT,
                language TEXT,
                timestamp TEXT,
                analyzed BOOLEAN DEFAULT 0
            )
        ''')
        
        cursor.execute("SELECT id FROM pages WHERE url = ?", (url,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
                UPDATE pages 
                SET title = ?, content = ?, language = ?, timestamp = ?, analyzed = 0
                WHERE url = ?
            ''', (title, text[:5000], lang, timestamp, url))
            logger.debug(f"SQLite güncellendi: {url}")
        else:
            cursor.execute('''
                INSERT INTO pages (url, title, content, language, timestamp, analyzed) 
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (url, title, text[:5000], lang, timestamp))
            logger.debug(f"SQLite kaydedildi: {url}")
            
        conn.commit()
    except sqlite3.IntegrityError:
        logger.warning(f"SQLite IntegrityError: {url}")
    except Exception as e:
        logger.error(f"SQLite kayıt hatası: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()