from loguru import logger
import sys
from app.config import settings

def configure_logging():
    logger.remove()
    logger.add(sys.stdout, level=settings.LOG_LEVEL, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")
