import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'rss-extractor'),
    'user': os.getenv('DB_USER', 'testuser101'),
    'password': os.getenv('DB_PASSWORD', 'password@123')
}