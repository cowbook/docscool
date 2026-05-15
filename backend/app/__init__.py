import os
import posixpath
import logging

from flask import Flask, jsonify
from flask_cors import CORS

from .auth import auth_bp
from .config import Config
from .contracts import contracts_bp
from .files import files_bp
from .extensions import db
from .models import Contract, Department, ProjectOption, UserPermission


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
        'handler': 'ALTER TABLE contracts ADD COLUMN handler VARCHAR(64)',
        'contract_determination_method': 'ALTER TABLE contracts ADD COLUMN contract_determination_method VARCHAR(64)',
        'handling_date': 'ALTER TABLE contracts ADD COLUMN handling_date DATE',
        'contract_type': 'ALTER TABLE contracts ADD COLUMN contract_type VARCHAR(64)',
        'purchase_type': 'ALTER TABLE contracts ADD COLUMN purchase_type VARCHAR(64)',
        'stamp_tax_rate': 'ALTER TABLE contracts ADD COLUMN stamp_tax_rate VARCHAR(32)',
        'pricing_method': 'ALTER TABLE contracts ADD COLUMN pricing_method VARCHAR(64)',
        'copy_count': 'ALTER TABLE contracts ADD COLUMN copy_count INTEGER',
        'save_place': 'ALTER TABLE contracts ADD COLUMN save_place VARCHAR(50)',
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


def _drop_legacy_contract_columns():
    expected_columns = {
        'id',
        'contract_number',
        'contract_name',
        'contract_unit',
        'amount',
        'currency',
        'handler',
        'department',
        'contract_determination_method',
        'handling_date',
        'contract_type',
        'purchase_type',
        'stamp_tax_rate',
        'pricing_method',
        'copy_count',
        'save_place',
        'is_archived',
        'project',
        'fullbody',
        'start_date',
        'end_date',
        'status',
        'file_path',
        'created_by',
        'created_at',
        'updated_at',
    }
    table_info = db.session.execute(db.text('PRAGMA table_info(contracts)')).fetchall()
    existing = {row[1] for row in table_info}
    amount_column = next((row for row in table_info if row[1] == 'amount'), None)
    amount_is_not_null = bool(amount_column and int(amount_column[3] or 0) == 1)
    if not (existing - expected_columns) and not amount_is_not_null:
        return

    db.session.execute(db.text('BEGIN IMMEDIATE'))
    db.session.execute(db.text('ALTER TABLE contracts RENAME TO contracts_legacy_drop_fields'))
    db.session.execute(db.text(
        '''
        CREATE TABLE contracts (
            id INTEGER NOT NULL,
            contract_number VARCHAR(64),
            contract_name VARCHAR(255) NOT NULL,
            contract_unit VARCHAR(255),
            amount NUMERIC(20, 8),
            currency VARCHAR(16) NOT NULL,
            handler VARCHAR(64),
            department VARCHAR(128) NOT NULL,
            contract_determination_method VARCHAR(64),
            handling_date DATE,
            contract_type VARCHAR(64),
            purchase_type VARCHAR(64),
            stamp_tax_rate VARCHAR(32),
            pricing_method VARCHAR(64),
            copy_count INTEGER,
            save_place VARCHAR(50),
            is_archived VARCHAR(32),
            project VARCHAR(255),
            fullbody TEXT,
            start_date DATE,
            end_date DATE,
            status VARCHAR(32) NOT NULL,
            file_path VARCHAR(512),
            created_by VARCHAR(128) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id)
        )
        '''
    ))
    db.session.execute(db.text(
        '''
        INSERT INTO contracts (
            id, contract_number, contract_name, contract_unit, amount, currency,
            handler, department, contract_determination_method,
            handling_date, contract_type, purchase_type, stamp_tax_rate, pricing_method, copy_count, save_place, is_archived, project,
            fullbody, start_date, end_date, status, file_path, created_by,
            created_at, updated_at
        )
        SELECT
            id, contract_number, contract_name, contract_unit, amount, currency,
            handler, department, contract_determination_method,
            handling_date, contract_type, purchase_type, stamp_tax_rate, pricing_method, copy_count, save_place, is_archived, project,
            fullbody, start_date, end_date, status, file_path, created_by,
            created_at, updated_at
        FROM contracts_legacy_drop_fields
        '''
    ))
    db.session.execute(db.text('DROP TABLE contracts_legacy_drop_fields'))
    db.session.execute(db.text('CREATE UNIQUE INDEX IF NOT EXISTS ix_contracts_contract_number ON contracts (contract_number)'))
    db.session.execute(db.text('CREATE INDEX IF NOT EXISTS ix_contracts_department ON contracts (department)'))
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
        _drop_legacy_contract_columns()
        _seed_departments()
        _seed_project_options()
        _migrate_legacy_file_paths(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(contracts_bp)
    app.register_blueprint(files_bp)

    @app.get('/api/health')
    def health():
        return jsonify({'status': 'ok'})

    return app
