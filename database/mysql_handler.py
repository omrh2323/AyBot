import mysql.connector
from mysql.connector import pooling, errors
from datetime import datetime
from utils.logger import logger
from utils.config import MYSQL_CONFIG, MAX_ERROR_COUNT, PRIORITY_DOMAINS, PRIORITY_INTERVAL, WHITELISTED_DOMAINS, DOMAIN_LIMIT, SQLITE_DB_PATH
from urllib.parse import urlparse
import sqlite3
import sys
from utils.helpers import is_valid_link 
from utils.helpers import normalize_url


# MySQL Connection Pool
try:
    mysql_pool = pooling.MySQLConnectionPool(
        pool_name="aysearch_pool",
        pool_size=10,
        **MYSQL_CONFIG
    )
    logger.info("MySQL bağlantı havuzu başarıyla oluşturuldu")
except Exception as e:
    logger.critical(f"MySQL bağlantı havuzu oluşturulamadı: {str(e)}")
    sys.exit(1)

def get_unvisited_links(limit=5):
    conn = None
    try:
        conn = mysql_pool.get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        
        conn.start_transaction()
        
        priority_domains = PRIORITY_DOMAINS
        priority_interval = PRIORITY_INTERVAL
        
        query = """
            SELECT b.id, b.url 
            FROM bots b
            WHERE 
                (
                    (b.visited = 1 AND b.domain IN (%s) 
                    AND b.last_crawled < NOW() - INTERVAL %s SECOND)
                    OR 
                    (b.visited = 0 AND b.in_progress = 0)
                )
                AND (b.error_count < %s OR b.error_count IS NULL)
            ORDER BY 
                b.domain IN (%s) DESC,
                b.last_crawled ASC,
                b.id ASC 
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        """
        
        domain_placeholders = ', '.join(['%s'] * len(priority_domains))
        query = query % (domain_placeholders, '%s', '%s', domain_placeholders, '%s')
        params = (
            *priority_domains, 
            priority_interval,
            MAX_ERROR_COUNT,
            *priority_domains,
            limit
        )
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        if results:
            ids = [str(row['id']) for row in results]
            
            update_query = f"""
                UPDATE bots 
                SET in_progress = 1 
                WHERE id IN ({', '.join(['%s'] * len(ids))})
            """
            cursor.execute(update_query, tuple(ids))
        
        conn.commit()
        
        for row in results:
            parsed = urlparse(row['url'])
            row['domain'] = parsed.netloc
            
        return results
        
    except mysql.connector.Error as err:
        logger.error(f"MySQL get_links hatası: {err}", exc_info=True)
        if conn:
            conn.rollback()
        return []
    except Exception as e:
        logger.error(f"Genel get_links hatası: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        return []
    finally:
        if conn:
            conn.close()

def insert_links_bulk(links):
    if not links:
        return

    conn = None
    sqlite_conn = None
    try:
        normalized_links = list({normalize_url(link) for link in links if is_valid_link(link)})
        logger.info(f"{len(normalized_links)} geçerli link bulundu")
        if not normalized_links:
            return

        sqlite_conn = sqlite3.connect(SQLITE_DB_PATH, timeout=30)
        sqlite_cursor = sqlite_conn.cursor()
        unique_links = []

        for link in normalized_links:
            sqlite_cursor.execute("SELECT 1 FROM pages WHERE url = ? LIMIT 1", (link,))
            if not sqlite_cursor.fetchone():
                unique_links.append(link)

        sqlite_conn.close()

        if not unique_links:
            logger.info("Tüm linkler zaten SQLite'ta kayıtlı")
            return

        conn = mysql_pool.get_connection()
        conn.start_transaction()
        cursor = conn.cursor()

        batch_size = 100
        existing_urls = set()
        for i in range(0, len(unique_links), batch_size):
            batch = unique_links[i:i + batch_size]
            query = f"""
                SELECT url 
                FROM bots 
                WHERE url IN ({', '.join(['%s'] * len(batch))})
            """
            cursor.execute(query, tuple(batch))
            existing_urls.update(row[0] for row in cursor.fetchall())

        final_links = [link for link in unique_links if link not in existing_urls]
        if not final_links:
            logger.info("Tüm linkler MySQL'de zaten mevcut")
            conn.commit()
            return

        logger.info(f"MySQL'e eklenecek yeni link sayısı: {len(final_links)}")
        insert_query = "INSERT IGNORE INTO bots (url, in_progress, visited, domain) VALUES (%s, 0, 0, %s)"
        
        batch_data = []
        for link in final_links:
            domain = urlparse(link).netloc
            batch_data.append((link, domain))
        
        for i in range(0, len(batch_data), batch_size):
            batch = batch_data[i:i + batch_size]
            try:
                cursor.executemany(insert_query, batch)
            except mysql.connector.IntegrityError:
                for data in batch:
                    try:
                        cursor.execute(insert_query, data)
                    except mysql.connector.IntegrityError:
                        pass
            
        conn.commit()
        logger.info(f"MySQL'e toplam {len(final_links)} yeni link eklendi")
        
    except mysql.connector.Error as err:
        logger.error(f"MySQL insert_links_bulk() hatası: {err}", exc_info=True)
        if conn:
            conn.rollback()
    except Exception as e:
        logger.error(f"Genel insert_links_bulk() hatası: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
        if sqlite_conn:
            sqlite_conn.close()

def mark_link_visited(link_id):
    conn = None
    try:
        conn = mysql_pool.get_connection()
        conn.start_transaction()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bots 
            SET visited = 1, 
                in_progress = 0, 
                last_crawled = %s 
            WHERE id = %s
        """, (datetime.utcnow().isoformat(), link_id))
        conn.commit()
    except Exception as e:
        logger.error(f"İşaretleme hatası: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def mark_link_error(link_id):
    conn = None
    try:
        conn = mysql_pool.get_connection()
        conn.start_transaction()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bots 
            SET in_progress = 0, 
                error_count = error_count + 1,
                last_error = %s 
            WHERE id = %s
        """, (datetime.utcnow().isoformat(), link_id))
        conn.commit()
        
        cursor.execute("SELECT error_count FROM bots WHERE id = %s", (link_id,))
        error_count = cursor.fetchone()[0]
        if error_count >= MAX_ERROR_COUNT:
            logger.warning(f"URL blacklist'e alındı (ID: {link_id})")
    except Exception as e:
        logger.error(f"Hata işaretleme hatası: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def update_domain_counter(domain):
    conn = None
    try:
        is_whitelisted = any(domain.endswith(ext) for ext in WHITELISTED_DOMAINS)
        
        conn = mysql_pool.get_connection()
        conn.start_transaction()
        cursor = conn.cursor()
        
        today = datetime.utcnow().date()
        
        cursor.execute("""
            SELECT count, last_updated 
            FROM domain_counters 
            WHERE domain = %s
            FOR UPDATE
        """, (domain,))
        result = cursor.fetchone()
        
        if result:
            count, last_updated = result
            if last_updated < today and not is_whitelisted:
                count = 0
        else:
            count = 0
        
        if not is_whitelisted and count >= DOMAIN_LIMIT:
            conn.commit()
            return count, is_whitelisted
        
        count += 1
        cursor.execute("""
            INSERT INTO domain_counters (domain, count, last_updated, is_whitelisted)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                count = VALUES(count),
                last_updated = VALUES(last_updated),
                is_whitelisted = VALUES(is_whitelisted)
        """, (domain, count, today, is_whitelisted))
        
        conn.commit()
        return count, is_whitelisted
    except Exception as e:
        logger.error(f"Domain sayaç hatası: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        return 0, False
    finally:
        if conn:
            conn.close()