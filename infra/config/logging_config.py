"""
Logging configuration for Hungry Panda
"""
import logging
import sys
from pathlib import Path
from infra.config.settings import config

# Create logs directory
LOGS_DIR = Path(config.DATABASE_PATH).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def setup_logging():
    """
    Configure logging for the application.
    Logs to both console and file.
    """
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG if config.DEBUG else logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            # Console handler
            logging.StreamHandler(sys.stdout),
            # File handler
            logging.FileHandler(
                LOGS_DIR / "hungry_panda.log",
                encoding="utf-8"
            )
        ]
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    
    return logging.getLogger("hungry_panda")


logger = setup_logging()
