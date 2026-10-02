import logging
import os

LOG_DIR = "logs"

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("CyberSahay")

logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(
    os.path.join(LOG_DIR, "cybersahay.log"),
    encoding="utf-8"
)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)

file_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(file_handler)