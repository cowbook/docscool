import os
import posixpath
import logging
import warnings
import json
from sqlalchemy import inspect

from flask import Flask, jsonify
from flask_cors import CORS
from urllib3.exceptions import InsecureRequestWarning

from .auth import auth_bp
from .config import Config
from .contracts import contracts_bp
from .files import files_bp
from .extensions import db
from .models import Contract, Department, ProjectOption, StampTaxRateOption, UserPermission


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

DEFAULT_STAMP_TAX_RATE_OPTIONS = {
    '买卖合同': '0.03%',
    '借款合同': '0.005%',
    '租赁合同': '0.1%',
    '承揽合同': '0.03%',
    '建设工程合同': '0.03%',
    '运输合同': '0.03%',
    '技术合同': '0.03%',
    '保管合同': '0.1%',
    '仓储合同': '0.1%',
    '财产保险合同': '0.1%',
    '人力资源': '',
    '其它': '',
}


warnings.filterwarnings('ignore', category=InsecureRequestWarning)


def _is_sqlite_database() -> bool:
    return db.engine.dialect.name == 'sqlite'


def _ensure_contract_columns():
    required_columns = {
        'contract_unit': 'ALTER TABLE contracts ADD COLUMN contract_unit VARCHAR(255)',
        'handler': 'ALTER TABLE contracts ADD COLUMN handler VARCHAR(64)',
        'contract_form': 'ALTER TABLE contracts ADD COLUMN contract_form VARCHAR(32)',
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
        'original_contract_id': 'ALTER TABLE contracts ADD COLUMN original_contract_id INTEGER',
        'fullbody': 'ALTER TABLE contracts ADD COLUMN fullbody TEXT',
        'updated_by': 'ALTER TABLE contracts ADD COLUMN updated_by VARCHAR(128)',
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
        'current_management_department',
        'contract_determination_method',
        'handling_date',
        'contract_type',
        'purchase_type',
        'stamp_tax_rate',
        'pricing_method',
        'copy_count',
        'save_place',
        'is_archived',
        'color_flag',
        'completeness',
        'project',
        'contract_form',
        'original_contract_id',
        'fullbody',
        'start_date',
        'end_date',
        'status',
        'file_path',
        'created_by',
        'updated_by',
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
            current_management_department VARCHAR(128),
            contract_form VARCHAR(32),
            contract_determination_method VARCHAR(64),
            handling_date DATE,
            contract_type VARCHAR(64),
            purchase_type VARCHAR(64),
            stamp_tax_rate VARCHAR(32),
            pricing_method VARCHAR(64),
            copy_count INTEGER,
            save_place VARCHAR(50),
            is_archived VARCHAR(32),
            color_flag VARCHAR(32),
            completeness VARCHAR(4),
            project VARCHAR(255),
            original_contract_id INTEGER,
            fullbody TEXT,
            start_date DATE,
            end_date DATE,
            status VARCHAR(32) NOT NULL,
            file_path VARCHAR(512),
            created_by VARCHAR(128) NOT NULL,
            updated_by VARCHAR(128),
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(original_contract_id) REFERENCES contracts (id)
        )
        '''
    ))
    db.session.execute(db.text(
        '''
        INSERT INTO contracts (
            id, contract_number, contract_name, contract_unit, amount, currency,
            handler, department, current_management_department, contract_form, contract_determination_method,
            handling_date, contract_type, purchase_type, stamp_tax_rate, pricing_method, copy_count, save_place, is_archived, color_flag, completeness, project,
            original_contract_id,
            fullbody, start_date, end_date, status, file_path, created_by,
            updated_by, created_at, updated_at
        )
        SELECT
            id, contract_number, contract_name, contract_unit, amount, currency,
            handler, department, NULL, NULL, contract_determination_method,
            handling_date, contract_type, purchase_type, stamp_tax_rate, pricing_method, copy_count, save_place, is_archived, NULL, NULL, project,
            NULL,
            fullbody, start_date, end_date, status, file_path, created_by,
            created_by, created_at, updated_at
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


def _seed_stamp_tax_rate_options():
    existing = {
        (row.contract_type or '').strip()
        for row in StampTaxRateOption.query.all()
    }

    missing = [
        (contract_type, tax_rate)
        for contract_type, tax_rate in DEFAULT_STAMP_TAX_RATE_OPTIONS.items()
        if contract_type not in existing
    ]
    if not missing:
        return

    for contract_type, tax_rate in missing:
        db.session.add(StampTaxRateOption(contract_type=contract_type, tax_rate=tax_rate))
    db.session.commit()


def _ensure_department_columns():
    inspector = inspect(db.engine)
    existing = {col.get('name') for col in inspector.get_columns('departments')}

    required_columns = {
        'is_existing': 'ALTER TABLE departments ADD COLUMN is_existing BOOLEAN NOT NULL DEFAULT 1',
        'current_department_name': 'ALTER TABLE departments ADD COLUMN current_department_name VARCHAR(50)',
    }
    for column, ddl in required_columns.items():
        if column not in existing:
            db.session.execute(db.text(ddl))

    db.session.commit()


def _ensure_contract_business_columns():
    inspector = inspect(db.engine)
    existing = {col.get('name') for col in inspector.get_columns('contracts')}

    required_columns = {
        'current_management_department': 'ALTER TABLE contracts ADD COLUMN current_management_department VARCHAR(128)',
        'color_flag': 'ALTER TABLE contracts ADD COLUMN color_flag VARCHAR(32)',
        'completeness': 'ALTER TABLE contracts ADD COLUMN completeness VARCHAR(4)',
    }

    for column, ddl in required_columns.items():
        if column not in existing:
            db.session.execute(db.text(ddl))

    db.session.commit()


def _backfill_contract_completeness():
    changed = 0
    rows = Contract.query.all()
    for row in rows:
        has_file = bool(str(getattr(row, 'file_path', '') or '').strip())
        has_determination = bool(str(getattr(row, 'contract_determination_method', '') or '').strip())
        has_purchase_type = bool(str(getattr(row, 'purchase_type', '') or '').strip())
        next_value = '是' if has_file and has_determination and has_purchase_type else '否'
        if str(getattr(row, 'completeness', '') or '').strip() != next_value:
            row.completeness = next_value
            changed += 1

    if changed > 0:
        db.session.commit()


def _backfill_current_management_department():
    def _extract_department_from_file_path(file_path: str) -> str:
        normalized = str(file_path or '').strip().replace('\\', '/')
        if not normalized:
            return ''
        parts = [part.strip() for part in normalized.split('/') if part.strip()]
        return parts[0] if parts else ''

    def _resolve_mapped_department(department_name: str, department_map: dict) -> str:
        normalized = str(department_name or '').strip()
        if not normalized:
            return ''

        department_row = department_map.get(normalized)
        if not department_row:
            return normalized
        if bool(getattr(department_row, 'is_existing', True)):
            return normalized

        mapped_name = str(getattr(department_row, 'current_department_name', '') or '').strip()
        return mapped_name or normalized

    departments = Department.query.all()
    department_map = {
        str(row.name or '').strip(): row
        for row in departments
        if str(row.name or '').strip()
    }

    changed = 0
    rows = Contract.query.all()
    for row in rows:
        file_path_department = _extract_department_from_file_path(getattr(row, 'file_path', ''))
        fallback_department = str(getattr(row, 'department', '') or '').strip()
        source_department = file_path_department or fallback_department
        if not source_department:
            continue

        next_value = _resolve_mapped_department(source_department, department_map)

        current_value = str(getattr(row, 'current_management_department', '') or '').strip()
        if current_value != next_value:
            row.current_management_department = next_value
            changed += 1

    if changed > 0:
        db.session.commit()


def _ensure_user_permission_columns():
    required_columns = {
        'permission_list': 'ALTER TABLE users ADD COLUMN permission_list TEXT',
        'role': "ALTER TABLE users ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'admin'",
        'me_added': 'ALTER TABLE users ADD COLUMN me_added BOOLEAN NOT NULL DEFAULT 0',
    }

    result = db.session.execute(db.text('PRAGMA table_info(users)'))
    existing = {row[1] for row in result.fetchall()}
    for column, ddl in required_columns.items():
        if column not in existing:
            db.session.execute(db.text(ddl))
    db.session.commit()


def _normalize_permission_item_list(items):
    normalized = []
    contains_super_admin = False
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        permission = str(item.get('permission') or '').strip()
        if permission not in {'super_admin', 'edit', 'view'}:
            continue

        item_is_super_admin = permission == 'super_admin'
        if item_is_super_admin:
            contains_super_admin = True
            permission = 'edit'

        departments = []
        department_seen = set()
        for value in item.get('departments') if isinstance(item.get('departments'), list) else []:
            text = str(value or '').strip()
            if not text or text in department_seen:
                continue
            department_seen.add(text)
            departments.append(text)

        folders = []
        folder_seen = set()
        for value in item.get('folders') if isinstance(item.get('folders'), list) else []:
            text = str(value or '').strip()
            if not text or text in folder_seen:
                continue
            folder_seen.add(text)
            folders.append(text)

        if item_is_super_admin:
            departments = ['全部']
            folders = ['全部']

        normalized.append({
            'permission': permission,
            'departments': departments,
            'folders': folders,
        })
    return normalized, contains_super_admin


def _build_permission_list_json_for_legacy_row(row_mapping, has_permission_column, has_departments_column, has_folders_column):
    role = str(row_mapping.get('role') or '').strip()
    if role not in {'super_admin', 'admin', 'synology_super_admin'}:
        role = 'admin'

    parsed = []
    raw_permission_list = row_mapping.get('permission_list')
    if raw_permission_list:
        try:
            parsed = json.loads(raw_permission_list)
        except Exception:
            parsed = []

    normalized, contains_super_admin = _normalize_permission_item_list(parsed)
    if contains_super_admin:
        role = 'super_admin'
    if normalized:
        return role, json.dumps(normalized, ensure_ascii=False)

    legacy_permission = 'view'
    if has_permission_column:
        value = str(row_mapping.get('permission') or '').strip()
        if value in {'super_admin', 'edit', 'view'}:
            legacy_permission = value

    legacy_departments = []
    if has_departments_column:
        legacy_departments = [
            part.strip()
            for part in str(row_mapping.get('departments') or '').split(',')
            if part.strip()
        ]

    legacy_folders = []
    if has_folders_column:
        legacy_folders = [
            part.strip()
            for part in str(row_mapping.get('folders') or '').split(',')
            if part.strip()
        ]

    if legacy_permission == 'super_admin':
        role = 'super_admin'
        legacy_permission = 'edit'
        legacy_departments = ['全部']
        legacy_folders = ['全部']

    return role, json.dumps([{
        'permission': legacy_permission if legacy_permission in {'edit', 'view'} else 'view',
        'departments': list(dict.fromkeys(legacy_departments)),
        'folders': list(dict.fromkeys(legacy_folders)),
    }], ensure_ascii=False)


def _drop_legacy_user_permission_columns():
    expected_columns = {
        'id',
        'login_name',
        'me_added',
        'description',
        'role',
        'permission_list',
        'created_at',
        'updated_at',
    }
    table_info = db.session.execute(db.text('PRAGMA table_info(users)')).fetchall()
    existing = {row[1] for row in table_info}
    if existing == expected_columns:
        return

    has_permission_column = 'permission' in existing
    has_departments_column = 'departments' in existing
    has_folders_column = 'folders' in existing
    old_rows = db.session.execute(db.text('SELECT * FROM users')).mappings().all()

    migrated_rows = []
    for row in old_rows:
        role_value, permission_list_value = _build_permission_list_json_for_legacy_row(
            row,
            has_permission_column,
            has_departments_column,
            has_folders_column,
        )
        migrated_rows.append({
            'id': row.get('id'),
            'login_name': row.get('login_name'),
            'me_added': 1 if bool(row.get('me_added')) else 0,
            'description': row.get('description') or '',
            'role': role_value,
            'permission_list': permission_list_value,
            'created_at': row.get('created_at'),
            'updated_at': row.get('updated_at'),
        })

    db.session.execute(db.text('BEGIN IMMEDIATE'))
    db.session.execute(db.text('ALTER TABLE users RENAME TO users_legacy_drop_fields'))
    db.session.execute(db.text(
        '''
        CREATE TABLE users (
            id INTEGER NOT NULL,
            login_name VARCHAR(128) NOT NULL,
            me_added BOOLEAN NOT NULL DEFAULT 0,
            description VARCHAR(255),
            role VARCHAR(32) NOT NULL DEFAULT 'admin',
            permission_list TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id)
        )
        '''
    ))
    if migrated_rows:
        db.session.execute(
            db.text(
                '''
                INSERT INTO users (
                    id, login_name, me_added, description, role,
                    permission_list, created_at, updated_at
                )
                VALUES (
                    :id, :login_name, :me_added, :description, :role,
                    :permission_list, :created_at, :updated_at
                )
                '''
            ),
            migrated_rows,
        )
    db.session.execute(db.text('DROP TABLE users_legacy_drop_fields'))
    db.session.execute(db.text('CREATE UNIQUE INDEX IF NOT EXISTS ix_users_login_name ON users (login_name)'))
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
        _ensure_department_columns()
        _ensure_contract_business_columns()
        if _is_sqlite_database():
            _ensure_contract_columns()
            _ensure_user_permission_columns()
            _drop_legacy_contract_columns()
            _drop_legacy_user_permission_columns()
        _seed_departments()
        _seed_project_options()
        _seed_stamp_tax_rate_options()
        _migrate_legacy_file_paths(app)
        _backfill_current_management_department()
        _backfill_contract_completeness()

    app.register_blueprint(auth_bp)
    app.register_blueprint(contracts_bp)
    app.register_blueprint(files_bp)

    @app.get('/api/health')
    def health():
        return jsonify({'status': 'ok'})

    return app
