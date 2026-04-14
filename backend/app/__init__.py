import os
import posixpath
import logging

from flask import Flask, jsonify
from flask_cors import CORS

from .auth import auth_bp
from .config import Config
from .contracts import contracts_bp
from .extensions import db
from .models import Contract, Department, ProjectOption


DEFAULT_PROJECT_OPTIONS = [
    'ERP三期/MIS建设',
    '江苏沿海管道如东-常熟-太仓段输气管线工程',
    '江苏沿海输气管网南通调控维抢中心',
    '江苏沿海输气管道华峰超纤项目配套天然气直供管道',
    '江苏沿海输气管道启东-海门支线段工程',
    '江苏沿海输气管道如东-盐城-滨海段（A段）工程',
    '江苏沿海输气管道朱家墩储气库支线段',
    '江苏沿海输气管道海安-泰州-扬州段（A段）工程',
    '江苏沿海输气管道淮安-建湖-盐城段工程',
    '江苏沿海输气管道淮安储气库支线段工程',
]

DEFAULT_DEPARTMENT_NAME = '财务部'


def _ensure_contract_columns():
    required_columns = {
        'contract_unit': 'ALTER TABLE contracts ADD COLUMN contract_unit VARCHAR(255)',
        'approval_status': 'ALTER TABLE contracts ADD COLUMN approval_status VARCHAR(64)',
        'handler': 'ALTER TABLE contracts ADD COLUMN handler VARCHAR(64)',
        'contract_determination_method': 'ALTER TABLE contracts ADD COLUMN contract_determination_method VARCHAR(64)',
        'handling_date': 'ALTER TABLE contracts ADD COLUMN handling_date DATE',
        'contract_type': 'ALTER TABLE contracts ADD COLUMN contract_type VARCHAR(64)',
        'invoice_type': 'ALTER TABLE contracts ADD COLUMN invoice_type VARCHAR(64)',
        'tax_rate': 'ALTER TABLE contracts ADD COLUMN tax_rate VARCHAR(16)',
        'pricing_method': 'ALTER TABLE contracts ADD COLUMN pricing_method VARCHAR(64)',
        'is_archived': 'ALTER TABLE contracts ADD COLUMN is_archived VARCHAR(32)',
        'project': 'ALTER TABLE contracts ADD COLUMN project VARCHAR(255)',
        'fullbody': 'ALTER TABLE contracts ADD COLUMN fullbody TEXT',
    }

    result = db.session.execute(db.text("PRAGMA table_info(contracts)"))
    existing = {row[1] for row in result.fetchall()}
    for column, ddl in required_columns.items():
        if column not in existing:
            db.session.execute(db.text(ddl))
    db.session.commit()


def _seed_project_options():
    existing = {row.name for row in ProjectOption.query.all()}
    missing = [name for name in DEFAULT_PROJECT_OPTIONS if name not in existing]
    if not missing:
        return

    for name in missing:
        db.session.add(ProjectOption(name=name))
    db.session.commit()


def _seed_departments():
    existing = {row.name for row in Department.query.all()}
    if DEFAULT_DEPARTMENT_NAME in existing:
        return

    db.session.add(Department(name=DEFAULT_DEPARTMENT_NAME))
    db.session.commit()


def _normalize_file_path(raw_path: str, base_url: str, storage_root: str) -> str:
    if not raw_path:
        return raw_path

    value = raw_path.strip().replace('\\', '/')
    if not value:
        return value

    normalized_root = (storage_root or '').strip().replace('\\', '/').rstrip('/')
    normalized_base = (base_url or '').strip().rstrip('/')

    # Remove full URL prefix first, e.g. https://nas:5001/volume1/contracts/...
    if normalized_base and value.startswith(normalized_base):
        value = value[len(normalized_base):]
        if not value.startswith('/'):
            value = f'/{value}'

    # Convert absolute NAS path to library-relative path.
    if normalized_root and value.startswith(normalized_root + '/'):
        value = value[len(normalized_root) + 1:]
    elif normalized_root and value == normalized_root:
        value = ''

    # Trim leading slash so stored result is relative root path.
    return value.lstrip('/')


def _migrate_legacy_file_paths(app: Flask):
    base_url = app.config.get('SYNOLOGY_BASE_URL', '')
    storage_root = app.config.get('CONTRACT_STORAGE_ROOT', '')

    changed = False
    rows = Contract.query.filter(Contract.file_path.isnot(None)).all()
    for row in rows:
        original = row.file_path or ''
        normalized = _normalize_file_path(original, base_url, storage_root)
        if normalized != original:
            row.file_path = normalized
            changed = True

    if changed:
        db.session.commit()


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.logger.setLevel(logging.INFO)

    os.makedirs(app.instance_path, exist_ok=True)
    if app.config.get('CONTRACT_STORAGE_MODE') == 'local':
        os.makedirs(app.config['CONTRACT_STORAGE_ROOT'], exist_ok=True)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)

    with app.app_context():
        db.create_all()
        _ensure_contract_columns()
        _seed_departments()
        _seed_project_options()
        _migrate_legacy_file_paths(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(contracts_bp)

    @app.get('/api/health')
    def health():
        return jsonify({'status': 'ok'})

    return app
