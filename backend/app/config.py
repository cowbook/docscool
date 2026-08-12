import os
import re
from dotenv import load_dotenv


load_dotenv()


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


class Config:
    SECRET_KEY = os.getenv('APP_SECRET_KEY', 'change-me')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_EXPIRES_HOURS = int(os.getenv('JWT_EXPIRES_HOURS', '8'))

    SYNOLOGY_BASE_URL = os.getenv('SYNOLOGY_BASE_URL', '').rstrip('/')
    SYNOLOGY_AUTH_SESSION = os.getenv('SYNOLOGY_AUTH_SESSION', 'DocsCool')
    SYNOLOGY_VERIFY_SSL = _to_bool(os.getenv('SYNOLOGY_VERIFY_SSL', 'false'))
    SYNOLOGY_USER = os.getenv('SYNOLOGY_USER', '').strip()
    SYNOLOGY_PASSWORD = os.getenv('SYNOLOGY_PASSWORD', '').strip()

    CONTRACT_STORAGE_ROOT = os.getenv('CONTRACT_STORAGE_ROOT', '/volume1/contracts')
    CONTRACT_STORAGE_MODE = os.getenv('CONTRACT_STORAGE_MODE', 'local').strip().lower()
    SYNOLOGY_FILESTATION_ROOT = os.getenv('SYNOLOGY_FILESTATION_ROOT', '')
    SYNOLOGY_FILESTATION_SCAN = os.getenv('SYNOLOGY_FILESTATION_SCAN', '').strip()

    MINIMAX_API_KEY = os.getenv('MINIMAX_API_KEY', '')
    MINERU_API_KEY = os.getenv('MINERU_API_KEY', '')
    MINIMAX_API_URL = os.getenv('MINIMAX_API_URL', 'https://api.minimaxi.com/v1/chat/completions')
    MINIMAX_MODEL = os.getenv('MINIMAX_MODEL', 'MiniMax-M2.5')
    HT_DETAIL_API_URL = os.getenv('HT_DETAIL_API_URL', 'http://10.254.56.59:7002/Liems/webservice/getHtDetail').strip()
    HT_DETAIL_API_USERNAME = os.getenv('HT_DETAIL_API_USERNAME', '').strip()
    HT_DETAIL_API_PASSWORD = os.getenv('HT_DETAIL_API_PASSWORD', '').strip()
    HT_DETAIL_API_TIMEOUT_SECONDS = int(os.getenv('HT_DETAIL_API_TIMEOUT_SECONDS', '15'))
    XUNFEI_APP_ID = os.getenv('XUNFEI_APP_ID', '')
    XUNFEI_API_KEY = os.getenv('XUNFEI_API_KEY', '')
    XUNFEI_API_SECRET = os.getenv('XUNFEI_API_SECRET', '')
    XUNFEI_API_URL = os.getenv('XUNFEI_API_URL', 'https://api.xf-yun.com/v1/private/hh_ocr_recognize_doc')
    MY_COMP = os.getenv('MY_COMP', '').strip()


def _normalize_db_uri(uri: str) -> str:
    # Resolve relative sqlite paths against backend project root, not current shell cwd.
    if not uri.startswith('sqlite:///'):
        return uri

    db_path = uri.replace('sqlite:///', '', 1)
    if os.path.isabs(db_path):
        return uri

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    absolute_path = os.path.abspath(os.path.join(project_root, db_path)).replace('\\', '/')
    return f'sqlite:///{absolute_path}'


db_uri = os.getenv('DATABASE_URL') or os.getenv('MYSQL_DATABASE_URL')
if not db_uri:
    raise RuntimeError('DATABASE_URL or MYSQL_DATABASE_URL must be set for the backend database connection')

if db_uri.startswith('sqlite'):
    raise RuntimeError('SQLite is disabled; configure DATABASE_URL or MYSQL_DATABASE_URL to a MySQL connection')

if not db_uri.startswith('mysql'):
    raise RuntimeError('Only MySQL connections are supported; configure DATABASE_URL or MYSQL_DATABASE_URL to mysql+...')

Config.SQLALCHEMY_DATABASE_URI = _normalize_db_uri(db_uri)
Config.SQLALCHEMY_ENGINE_OPTIONS = {
    'connect_args': {
        'charset': 'utf8mb4',
        'use_unicode': True,
    }
}


def _to_filestation_path(storage_root: str) -> str:
    normalized = (storage_root or '').replace('\\', '/').strip()
    if not normalized:
        return '/contracts'
    # /volume1/share/folder -> /share/folder
    converted = re.sub(r'^/volume\d+', '', normalized)
    if not converted.startswith('/'):
        converted = f'/{converted}'
    return converted


if not Config.SYNOLOGY_FILESTATION_ROOT:
    Config.SYNOLOGY_FILESTATION_ROOT = _to_filestation_path(Config.CONTRACT_STORAGE_ROOT)
