import aiohttp
import asyncio
import psutil
import random
from utils.logger import logger
from utils.config import MAX_CONCURRENT_REQUESTS
from database import mysql_handler
from .crawler import process_url

class DynamicConfig:
    def __init__(self):
        self.concurrency_level = 3
        self.timeout_factor = 1.0
        self.update_count = 0
        
    def update_based_on_resources(self):
        cpu_percent = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_percent = ram.percent
        
        old_concurrency = self.concurrency_level
        old_timeout = self.timeout_factor
        
        if cpu_percent > 80 or ram_percent > 80:
            self.concurrency_level = max(1, self.concurrency_level - 1)
            self.timeout_factor = min(2.0, self.timeout_factor + 0.1)
        elif cpu_percent < 50 and ram_percent < 60 and self.concurrency_level < MAX_CONCURRENT_REQUESTS:
            self.concurrency_level = min(MAX_CONCURRENT_REQUESTS, self.concurrency_level + 1)
            self.timeout_factor = max(0.7, self.timeout_factor - 0.1)
        
        if old_concurrency != self.concurrency_level or old_timeout != self.timeout_factor:
            logger.info(f"Konfig güncellendi: Concurrency={self.concurrency_level} TimeoutF={self.timeout_factor:.1f} "
                        f"(CPU={cpu_percent}% RAM={ram_percent}%)")
        
        self.update_count += 1
        if self.update_count > 10:
            self.concurrency_level = 3
            self.timeout_factor = 1.0
            self.update_count = 0

dynamic_config = DynamicConfig()

async def main_worker():
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit_per_host=5),
        trust_env=True
    ) as session:
        while True:
            try:
                dynamic_config.update_based_on_resources()
                
                batch = mysql_handler.get_unvisited_links(limit=dynamic_config.concurrency_level)
                
                if not batch:
                    logger.info("İşlenecek link yok, 10 saniye bekleniyor...")
                    await asyncio.sleep(10)
                    continue
                
                logger.info(f"{len(batch)} adet link işleme alındı")
                
                tasks = []
                for item in batch:
                    tasks.append(process_url(session, item))
                
                await asyncio.gather(*tasks)
                
                logger.info(f"Batch işlemi tamamlandı, 3 saniye bekleniyor...")
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"Ana döngü hatası: {str(e)}", exc_info=True)
                await asyncio.sleep(10)