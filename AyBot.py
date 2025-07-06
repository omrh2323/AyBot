import aiohttp
import asyncio
import signal
import sys
import platform
import os
import mysql.connector
import sqlite3
from utils import config, logger
from database import mysql_handler
from core.scheduler import main_worker
from core.crawler import parse_sitemap
from datetime import datetime
from urllib.parse import urlparse

def graceful_exit(signum, frame):
    logger.logger.info("Bot güvenli şekilde durduruluyor...")
    sys.exit(0)

signal.signal(signal.SIGINT, graceful_exit)

async def main_async():
    logger.logger.info("=== AyBot v6.0 - Gelişmiş Sürekli Tarama Motoru ===")
    logger.logger.info(f"Veri depolama: {os.path.abspath('data')}")
    logger.logger.info(f"Sistem: {platform.system()} {platform.release()}")
    
    # MySQL tablolarını oluştur
    conn = None
    try:
        conn = mysql_handler.mysql_pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                id INT AUTO_INCREMENT PRIMARY KEY,
                url VARCHAR(2048) NOT NULL UNIQUE,
                in_progress BOOLEAN NOT NULL DEFAULT 0,
                visited BOOLEAN NOT NULL DEFAULT 0,
                error_count INT NOT NULL DEFAULT 0,
                last_crawled DATETIME,
                last_error DATETIME,
                domain VARCHAR(255)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS domain_counters (
                domain VARCHAR(255) NOT NULL PRIMARY KEY,
                count INT NOT NULL DEFAULT 0,
                last_updated DATE NOT NULL,
                is_whitelisted BOOLEAN DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                url VARCHAR(2048),
                error_type VARCHAR(255),
                error_message TEXT,
                timestamp DATETIME
            )
        """)
        
        try:
            cursor.execute("ALTER TABLE bots ADD COLUMN domain VARCHAR(255)")
        except mysql.connector.Error as err:
            if err.errno != 1060:  # Column already exists
                logger.logger.error(f"MySQL domain sütunu ekleme hatası: {err}")
        
        cursor.execute("""
            UPDATE bots 
            SET domain = SUBSTRING_INDEX(SUBSTRING_INDEX(url, '://', -1), '/', 1)
            WHERE domain IS NULL
        """)
        
        for domain_ext in config.WHITELISTED_DOMAINS:
            cursor.execute("""
                UPDATE domain_counters 
                SET is_whitelisted = 1 
                WHERE domain LIKE %s
            """, (f'%{domain_ext}',))
        
        conn.commit()
        logger.logger.info("MySQL tabloları başarıyla kontrol edildi")
        
        cursor.execute("SELECT COUNT(*) FROM bots")
        count = cursor.fetchone()[0]
        
        if count == 0:
            start_urls = [
                "https://www.shiftdelete.net/"
            ]
            for url in start_urls:
                domain = urlparse(url).netloc
                cursor.execute(
                    "INSERT IGNORE INTO bots (url, domain) VALUES (%s, %s)",
                    (url, domain)
                )
            conn.commit()
            logger.logger.info(f"Başlangıç URL'leri eklendi: {start_urls}")
            
    except Exception as e:
        logger.logger.critical(f"MySQL tablo hatası: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        if conn:
            conn.close()
    
    # SQLite tablosunu oluştur
    sqlite_conn = None
    try:
        sqlite_conn = sqlite3.connect(config.SQLITE_DB_PATH, timeout=30)
        sqlite_conn.execute("PRAGMA journal_mode = WAL")
        cursor = sqlite_conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                content TEXT,
                language TEXT,
                timestamp TEXT,
                analyzed BOOLEAN DEFAULT 0
            )
        """)
        sqlite_conn.commit()
        logger.logger.info("SQLite tablosu başarıyla kontrol edildi")
    except Exception as e:
        logger.logger.critical(f"SQLite tablo hatası: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        if sqlite_conn:
            sqlite_conn.close()
    
    await main_worker()

if __name__ == '__main__':
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main_async())