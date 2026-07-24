import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.extensions import db

TABLES_TO_IMPORT = [
    'departments',
    'project_options',
    'stamp_tax_rate_options',
    'users',
    'contracts',
]


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_source_and_target_urls() -> tuple[str, str]:
    load_dotenv(_workspace_root() / '.env')

    source_url = os.getenv('SOURCE_SQLITE_URL', 'sqlite:///instance/contracts.db').strip()
    target_url = os.getenv('MYSQL_DATABASE_URL', '').strip() or os.getenv('DATABASE_URL', '').strip()

    if not source_url.startswith('sqlite:///'):
        raise RuntimeError(f'SOURCE_SQLITE_URL 必须是 sqlite:///...，当前: {source_url}')
    if not target_url:
        raise RuntimeError('MYSQL_DATABASE_URL 和 DATABASE_URL 不能同时为空')
    if target_url.startswith('sqlite:///'):
        raise RuntimeError('DATABASE_URL 仍指向 SQLite，请先改为 MySQL 连接串')

    return source_url, target_url


def _resolve_sqlite_url(source_url: str) -> str:
    prefix = 'sqlite:///'
    source_path = source_url[len(prefix):]
    source_file = Path(source_path)
    if source_file.is_absolute():
        return source_url

    absolute = (_workspace_root() / source_file).resolve().as_posix()
    return f'sqlite:///{absolute}'


def _table_rows(connection, table_name: str) -> list[dict]:
    result = connection.execute(text(f'SELECT * FROM {table_name}')).mappings().all()
    return [dict(row) for row in result]


def _sync_autoincrement(target_connection, table_name: str, imported_count: int) -> None:
    if imported_count <= 0:
        return

    max_id = target_connection.execute(text(f'SELECT MAX(id) AS max_id FROM {table_name}')).scalar()
    next_id = int(max_id or 0) + 1
    target_connection.execute(text(f'ALTER TABLE {table_name} AUTO_INCREMENT = :next_id'), {'next_id': next_id})


def main() -> int:
    source_url, target_url = _load_source_and_target_urls()
    source_url = _resolve_sqlite_url(source_url)

    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url, pool_pre_ping=True)

    # Ensure target schema exists before data import.
    db.metadata.create_all(bind=target_engine)

    inserted_total = 0
    with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
        target_conn.execute(text('SET FOREIGN_KEY_CHECKS=0'))
        try:
            for table_name in TABLES_TO_IMPORT:
                rows = _table_rows(source_conn, table_name)
                target_conn.execute(text(f'DELETE FROM {table_name}'))
                if rows:
                    target_conn.execute(db.metadata.tables[table_name].insert(), rows)
                _sync_autoincrement(target_conn, table_name, len(rows))
                inserted_total += len(rows)
                print(f'{table_name}: imported {len(rows)} rows')
        finally:
            target_conn.execute(text('SET FOREIGN_KEY_CHECKS=1'))

    print(f'Import completed, total rows imported: {inserted_total}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
