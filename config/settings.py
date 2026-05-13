"""Main configuration settings."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=False)

# BASE PATHS
BASE_DIR = Path(__file__).resolve().parent.parent

# MUSIC MATCHING CONFIGURATION
MUSIC_MATCHING_CONFIG = {
    'musicbrainz': {
        'user_agent': os.getenv('MUSICBRAINZ_USER_AGENT', 'WhatsAppSongScanner/1.0.0'),
        'rate_limit_per_second': float(os.getenv('MUSICBRAINZ_RATE_LIMIT', '1.0')),
        'cache_duration_hours': int(os.getenv('MUSICBRAINZ_CACHE_HOURS', '168')),  # 7 days
    },
    'jamendo': {
        'client_id': os.getenv('JAMENDO_CLIENT_ID', ''),
        'client_secret': os.getenv('JAMENDO_CLIENT_SECRET', ''),
        'base_url': os.getenv('JAMENDO_BASE_URL', 'https://api.jamendo.com/v3.0'),
        'timeout_seconds': float(os.getenv('JAMENDO_TIMEOUT_SECONDS', '8.0')),
        'max_results': int(os.getenv('JAMENDO_MAX_RESULTS', '10')),
    },
    'fuzzy_matching': {
        'min_match_score': int(os.getenv('MIN_MATCH_SCORE', '80')),
        'max_candidates': int(os.getenv('MAX_CANDIDATES', '5')),
    },
    'fallback_apis': {
        'spotify_client_id': os.getenv('SPOTIFY_CLIENT_ID', ''),
        'spotify_client_secret': os.getenv('SPOTIFY_CLIENT_SECRET', ''),
        'deezer_app_id': os.getenv('DEEZER_APP_ID', ''),
    }
}

# DATABASE CONFIGURATION
DATABASE_CONFIG = {
    'mariadb': {
        'host': os.getenv('MARIADB_HOST', 'localhost'),
        'port': int(os.getenv('MARIADB_PORT', '3306')),
        'database': os.getenv('MARIADB_DATABASE', 'song_scanner'),
        'username': os.getenv('MARIADB_USERNAME', 'scanner_bot'),
        'password': os.getenv('MARIADB_PASSWORD', ''),
        'charset': 'utf8mb4',
        'pool_size': 10,
        'max_overflow': 20,
    },
    'radiodj': {
        'db_path': os.getenv('RADIODJ_DB_PATH', ''),
        'library_path': os.getenv('RADIODJ_LIBRARY_PATH', os.getenv('RADIODJ_DB_PATH', '')),
        'api_url': os.getenv('RADIODJ_API_URL', ''),
        'api_key': os.getenv('RADIODJ_API_KEY', ''),
        'default_playlist_id': int(os.getenv('RADIODJ_DEFAULT_PLAYLIST_ID', '1')),
        'db_host': os.getenv('RADIODJ_DB_HOST', os.getenv('MARIADB_HOST', 'localhost')),
        'db_port': int(os.getenv('RADIODJ_DB_PORT', '3306')),
        'db_name': os.getenv('RADIODJ_DB_NAME', 'radiodj2'),
        'db_username': os.getenv('RADIODJ_DB_USER', os.getenv('MARIADB_USERNAME', 'root')),
        'db_password': os.getenv('RADIODJ_DB_PASS', ''),
    }
}

# REDIS CONFIGURATION
REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', '6379')),
    'db': int(os.getenv('REDIS_DB', '0')),
    'password': os.getenv('REDIS_PASSWORD', ''),
}

# CELERY CONFIGURATION
CELERY_CONFIG = {
    'broker_url': os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    'result_backend': os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
}

# APPLICATION CONFIGURATION
APP_CONFIG = {
    'debug': os.getenv('DEBUG', 'False').lower() == 'true',
    'host': os.getenv('APP_HOST', '0.0.0.0'),
    'port': int(os.getenv('APP_PORT', '5000')),
    'log_level': os.getenv('LOG_LEVEL', 'INFO'),
    'data_dir': BASE_DIR / 'data',
    'max_workers': int(os.getenv('MAX_WORKERS', '4')),
}
