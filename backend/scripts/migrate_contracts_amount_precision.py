import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Config


NEW_TABLE_DDL = '''
CREATE TABLE contracts (
    id INTEGER NOT NULL,
    contract_number VARCHAR(64),
    contract_name VARCHAR(255) NOT NULL,
    contract_unit VARCHAR(255),
    amount NUMERIC(20, 8) NOT NULL,
    currency VARCHAR(16) NOT NULL,
    approval_status VARCHAR(64),
    handler VARCHAR(64),
    department VARCHAR(128) NOT NULL,
    contract_determination_method VARCHAR(64),
    handling_date DATE,
    contract_type VARCHAR(64),
    invoice_type VARCHAR(64),
    tax_rate VARCHAR(16),
    pricing_method VARCHAR(64),
    is_archived VARCHAR(32),
    project VARCHAR(255),
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


CONTRACT_COLUMNS = [
    'id',
    'contract_number',
    'contract_name',
    'contract_unit',
    'amount',
    'currency',
    'approval_status',
    'handler',
    'department',
    'contract_determination_method',
    'handling_date',
    'contract_type',
    'invoice_type',
    'tax_rate',
    'pricing_method',
    'is_archived',
    'project',
    'start_date',
    'end_date',
    'status',
    'file_path',
    'created_by',
    'created_at',
    'updated_at',
]


def _resolve_sqlite_path() -> Path:
    uri = Config.SQLALCHEMY_DATABASE_URI
    prefix = 'sqlite:///'
    if not uri.startswith(prefix):
        raise RuntimeError(f'当前数据库不是 SQLite: {uri}')
    return Path(uri[len(prefix):])


def _fetch_amount_type(connection: sqlite3.Connection, table_name: str) -> str:
    rows = connection.execute(f'PRAGMA table_info({table_name})').fetchall()
    for row in rows:
        if row[1] == 'amount':
            return row[2]
    return ''


def _fetch_row_count(connection: sqlite3.Connection, table_name: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0])


def _drop_named_indexes(connection: sqlite3.Connection, table_name: str) -> None:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name = ? AND sql IS NOT NULL",
        (table_name,),
    ).fetchall()
    for row in rows:
        connection.execute(f'DROP INDEX IF EXISTS {row[0]}')


def main() -> int:
    db_path = _resolve_sqlite_path()
    if not db_path.exists():
        raise FileNotFoundError(f'数据库文件不存在: {db_path}')

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_backup_path = db_path.with_suffix(f'{db_path.suffix}.bak_{timestamp}')
    legacy_table_name = f'contracts_amount_backup_{timestamp}'

    shutil.copy2(db_path, file_backup_path)
    print(f'已创建数据库文件备份: {file_backup_path}')

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        current_amount_type = _fetch_amount_type(connection, 'contracts')
        print(f'迁移前 amount 列类型: {current_amount_type}')
        if current_amount_type.upper() == 'NUMERIC(20, 8)':
            print('contracts.amount 已经是 NUMERIC(20, 8)，无需迁移。')
            return 0

        original_count = _fetch_row_count(connection, 'contracts')
        column_list = ', '.join(CONTRACT_COLUMNS)

        connection.execute('BEGIN IMMEDIATE')
        connection.execute(f'ALTER TABLE contracts RENAME TO {legacy_table_name}')
        _drop_named_indexes(connection, legacy_table_name)
        connection.execute(NEW_TABLE_DDL)
        connection.execute('CREATE UNIQUE INDEX ix_contracts_contract_number ON contracts (contract_number)')
        connection.execute('CREATE INDEX ix_contracts_department ON contracts (department)')
        connection.execute(
            f'INSERT INTO contracts ({column_list}) '
            f'SELECT {column_list} FROM {legacy_table_name}'
        )
        migrated_count = _fetch_row_count(connection, 'contracts')
        if migrated_count != original_count:
            raise RuntimeError(f'迁移后行数不一致: before={original_count}, after={migrated_count}')

        connection.commit()

        new_amount_type = _fetch_amount_type(connection, 'contracts')
        print(f'迁移后 amount 列类型: {new_amount_type}')
        print(f'原表已保留为: {legacy_table_name}')
        print(f'迁移完成，共迁移 {migrated_count} 行。')
        return 0
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == '__main__':
    raise SystemExit(main())