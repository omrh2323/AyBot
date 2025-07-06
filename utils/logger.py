import logging
from logging.handlers import RotatingFileHandler
from .config import LOG_PATH

def setup_logger():
    logger = logging.getLogger('AyBot')
    logger.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=10*1024*1024, backupCount=2)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger

logger = setup_logger()