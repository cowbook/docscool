import mimetypes
import os
import posixpath
import re

import requests
from difflib import SequenceMatcher
from flask import current_app

from .contracts_core import (
    EXTERNAL_API_TIMEOUT_SECONDS,
    _build_synology_file_path,
    _filename_from_content_disposition,
    _list_local_entries,
    _list_storage_entries,
    _list_remote_entries,
    _normalize_contract_file_path,
    _normalize_match_text,
    _normalize_relative_path,
    _remote_folder_path,
    _safe_local_file_path,
    _safe_local_folder_path,
    _synology_api_post,
    _synology_error_code,
    _synology_error_message,
    _synology_json_array,
    _synology_upload_login,
)
from .models import Contract

def _list_folder_children_nodes(relative_path: str):
    directories, _files = _list_storage_entries(relative_path)
    return [
        {
            'name': item['name'],
            'path': item['path'],
        }
        for item in directories
    ]


def _count_storage_files_recursive(relative_path: str) -> int:
    normalized = _normalize_relative_path(relative_path)
    queue = [normalized]
    visited = set()
    total = 0

    # Reuse one Synology session for the entire traversal to avoid repeated
    # login/list cycles that may trigger session invalidation (error code 119).
    remote_mode = current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote'
    sid = _synology_upload_login() if remote_mode else ''

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        if remote_mode:
            try:
                directories, files = _list_remote_entries(current, sid=sid)
            except RuntimeError as exc:
                # Session may expire during long traversals; re-login once.
                if '错误码: 119' not in str(exc):
                    raise
                sid = _synology_upload_login()
                directories, files = _list_remote_entries(current, sid=sid)
        else:
            directories, files = _list_local_entries(current)

        total += len(files)
        for item in directories:
            child_path = _normalize_relative_path(item.get('path') or '')
            if child_path not in visited:
                queue.append(child_path)

    return total

def _build_contract_file_index() -> dict:
    index = {}
    rows = Contract.query.filter(Contract.file_path.isnot(None)).all()
    for row in rows:
        normalized = _normalize_contract_file_path(row.file_path)
        if not normalized:
            continue
        if normalized not in index:
            index[normalized] = row
    return index


def _build_folder_file_items(relative_folder_path: str):
    _directories, files = _list_storage_entries(relative_folder_path)
    contract_index = _build_contract_file_index()

    payload = []
    for item in files:
        relative_file_path = item['path']
        matched = contract_index.get(relative_file_path)
        contract_payload = matched.to_dict() if matched else None

        row = {
            'name': item['name'],
            'file_path': relative_file_path,
            'size': item.get('size') or 0,
            'mtime': item.get('mtime'),
            'matched_contract_id': matched.id if matched else None,
            'contract_name': contract_payload.get('contract_name') if contract_payload else '<无匹配>',
            'contract_number': contract_payload.get('contract_number') if contract_payload else '',
            'contract_unit': contract_payload.get('contract_unit') if contract_payload else '',
            'contract_amount': contract_payload.get('contract_amount') if contract_payload else '',
            'handler': contract_payload.get('handler') if contract_payload else '',
            'handling_department': contract_payload.get('handling_department') if contract_payload else '',
            'handling_date': contract_payload.get('handling_date') if contract_payload else '',
            'contract_type': contract_payload.get('contract_type') if contract_payload else '',
            'purchase_type': contract_payload.get('purchase_type') if contract_payload else '',
            'stamp_tax_rate': contract_payload.get('stamp_tax_rate') if contract_payload else '',
            'copy_count': contract_payload.get('copy_count') if contract_payload else None,
            'save_place': contract_payload.get('save_place') if contract_payload else '',
            'is_archived': contract_payload.get('is_archived') if contract_payload else '',
            'project': contract_payload.get('project') if contract_payload else '',
            'contract': contract_payload,
        }
        payload.append(row)

    return payload

def _extract_match_key_from_filename(file_name: str) -> str:
    base_name = os.path.splitext(os.path.basename(str(file_name or '')))[0]
    if not base_name:
        return ''

    chinese_indexes = [idx for idx, ch in enumerate(base_name) if re.match(r'[\u4e00-\u9fff]', ch)]
    if not chinese_indexes:
        return ''

    start_idx = chinese_indexes[0]
    end_idx = chinese_indexes[-1]
    return base_name[start_idx:end_idx + 1].strip()


def _select_best_contract_by_key(match_key: str, candidates: list):
    normalized_key = _normalize_match_text(match_key)
    if not normalized_key:
        return None, '', []

    scored = []
    for row in candidates:
        normalized_contract_name = _normalize_match_text(row.contract_name)
        if not normalized_contract_name:
            continue

        exact = normalized_contract_name == normalized_key
        contains = normalized_key in normalized_contract_name
        if not exact and not contains:
            continue

        similarity = SequenceMatcher(None, normalized_key, normalized_contract_name).ratio()
        scored.append({
            'row': row,
            'normalized_name': normalized_contract_name,
            'exact': exact,
            'contains': contains,
            'similarity': similarity,
        })

    if not scored:
        return None, '', []

    exact_rows = [item for item in scored if item['exact']]
    if exact_rows:
        exact_rows.sort(key=lambda item: (-item['similarity'], item['row'].id))
        return exact_rows[0]['row'], 'exact', exact_rows

    contains_rows = [item for item in scored if item['contains']]
    if len(contains_rows) == 1:
        return contains_rows[0]['row'], 'contains-single', contains_rows

    contains_rows.sort(key=lambda item: (-item['similarity'], item['row'].id))
    return contains_rows[0]['row'], 'contains-best', contains_rows

def _create_storage_folder(parent_path: str, folder_name: str) -> str:
    normalized_parent = _normalize_relative_path(parent_path)
    name = (folder_name or '').strip()
    if not name:
        raise ValueError('文件夹名称不能为空')
    if '/' in name or '\\' in name:
        raise ValueError('文件夹名称不能包含斜杠')

    target_relative_path = _build_synology_file_path(normalized_parent, name)
    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        sid = _synology_upload_login()
        payload = _synology_api_post(
            sid,
            {
                'api': 'SYNO.FileStation.CreateFolder',
                'version': '2',
                'method': 'create',
            },
            data={
                'folder_path': _synology_json_array(_remote_folder_path(normalized_parent)),
                'name': _synology_json_array(name),
                'force_parent': 'false',
            },
        )
        if not payload.get('success'):
            code = _synology_error_code(payload)
            if code == 414:
                raise FileExistsError('文件夹已存在')
            raise RuntimeError(_synology_error_message(payload, 'filestation'))
        return target_relative_path

    target_path = _safe_local_folder_path(target_relative_path)
    os.makedirs(target_path, exist_ok=False)
    return target_relative_path


def _delete_storage_folder(relative_path: str) -> None:
    normalized = _normalize_relative_path(relative_path)
    if not normalized:
        raise ValueError('不允许删除根目录')

    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        sid = _synology_upload_login()
        directories, files = _list_remote_entries(normalized, sid=sid)
        if files:
            raise RuntimeError('该文件夹下存在文件，不能删除')
        if directories:
            raise RuntimeError('该文件夹下存在子文件夹，不能删除')

        payload = _synology_api_post(
            sid,
            {
                'api': 'SYNO.FileStation.Delete',
                'version': '2',
                'method': 'delete',
            },
            data={
                'path': f'["{_remote_folder_path(normalized)}"]',
                'recursive': 'false',
            },
        )
        if not payload.get('success'):
            code = _synology_error_code(payload)
            if code in {404, 415}:
                raise FileNotFoundError('目录不存在')
            raise RuntimeError(_synology_error_message(payload, 'filestation'))
        return

    folder_path = _safe_local_folder_path(normalized)
    if not os.path.isdir(folder_path):
        raise FileNotFoundError('目录不存在')

    child_dirs = []
    child_files = []
    with os.scandir(folder_path) as entries:
        for entry in entries:
            if entry.is_file(follow_symlinks=False):
                child_files.append(entry.name)
            elif entry.is_dir(follow_symlinks=False):
                child_dirs.append(entry.name)

    if child_files:
        raise RuntimeError('该文件夹下存在文件，不能删除')
    if child_dirs:
        raise RuntimeError('该文件夹下存在子文件夹，不能删除')

    os.rmdir(folder_path)


def _load_storage_file_payload(relative_file_path: str):
    normalized = _normalize_relative_path(relative_file_path)
    if not normalized:
        raise ValueError('file_path is required')

    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        sid = _synology_upload_login()
        remote_file_path = _remote_folder_path(normalized)
        response = None
        for path_value in (f'["{remote_file_path}"]', remote_file_path):
            candidate = requests.get(
                f"{current_app.config.get('SYNOLOGY_BASE_URL', '').rstrip('/')}/webapi/entry.cgi",
                params={
                    'api': 'SYNO.FileStation.Download',
                    'version': '2',
                    'method': 'download',
                    'mode': 'download',
                    'path': path_value,
                    '_sid': sid,
                },
                timeout=EXTERNAL_API_TIMEOUT_SECONDS,
                verify=current_app.config.get('SYNOLOGY_VERIFY_SSL', False),
            )
            if candidate.status_code == 404:
                continue
            candidate.raise_for_status()
            response = candidate
            break

        if response is None:
            raise FileNotFoundError('文件不存在或路径无效')

        content_type = (response.headers.get('Content-Type') or '').lower()
        if 'application/json' in content_type:
            try:
                payload = response.json()
                if not payload.get('success'):
                    raise RuntimeError(_synology_error_message(payload, 'filestation'))
            except ValueError:
                pass

        file_name = _filename_from_content_disposition(response.headers.get('Content-Disposition', ''))
        if not file_name:
            file_name = os.path.basename(normalized) or 'download.bin'

        mime = response.headers.get('Content-Type') or mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
        return response.content, file_name, mime

    local_file_path = _safe_local_file_path(normalized)
    if not os.path.isfile(local_file_path):
        raise FileNotFoundError('文件不存在或已被移动')

    file_name = os.path.basename(local_file_path)
    mime = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
    with open(local_file_path, 'rb') as f:
        return f.read(), file_name, mime


def _delete_storage_file(relative_file_path: str) -> str:
    normalized = _normalize_relative_path(relative_file_path)
    if not normalized:
        raise ValueError('file_path is required')

    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        remote_file_path = _remote_folder_path(normalized)
        sid = _synology_upload_login()
        payload = _synology_api_post(
            sid,
            {
                'api': 'SYNO.FileStation.Delete',
                'version': '2',
                'method': 'delete',
            },
            data={
                'path': f'["{remote_file_path}"]',
            },
        )
        if not payload.get('success'):
            code = _synology_error_code(payload)
            if code in {404, 415}:
                raise FileNotFoundError('文件不存在')
            raise RuntimeError(_synology_error_message(payload, 'filestation'))
        return normalized

    local_file_path = _safe_local_file_path(normalized)
    if not os.path.isfile(local_file_path):
        raise FileNotFoundError('文件不存在')

    os.remove(local_file_path)
    return normalized


def _rename_storage_file(relative_file_path: str, new_name: str) -> tuple[str, str]:
    normalized = _normalize_relative_path(relative_file_path)
    if not normalized:
        raise ValueError('file_path is required')

    target_name = (new_name or '').strip()
    if not target_name:
        raise ValueError('文件名不能为空')
    if '/' in target_name or '\\' in target_name:
        raise ValueError('文件名不能包含斜杠')

    parent_path = posixpath.dirname(normalized)
    if parent_path == '.':
        parent_path = ''
    new_relative_path = _build_synology_file_path(parent_path, target_name)

    if new_relative_path == normalized:
        return normalized, normalized

    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        sid = _synology_upload_login()
        old_remote_path = _remote_folder_path(normalized)
        payload = _synology_api_post(
            sid,
            {
                'api': 'SYNO.FileStation.Rename',
                'version': '2',
                'method': 'rename',
            },
            data={
                'path': f'["{old_remote_path}"]',
                'name': _synology_json_array(target_name),
            },
        )
        if not payload.get('success'):
            code = _synology_error_code(payload)
            if code in {404, 415}:
                raise FileNotFoundError('文件不存在')
            if code in {405, 408}:
                raise FileExistsError('同名文件已存在')
            raise RuntimeError(_synology_error_message(payload, 'filestation'))
        return normalized, new_relative_path

    old_local_path = _safe_local_file_path(normalized)
    if not os.path.isfile(old_local_path):
        raise FileNotFoundError('文件不存在')

    new_local_path = _safe_local_file_path(new_relative_path)
    if os.path.exists(new_local_path):
        raise FileExistsError('同名文件已存在')

    os.rename(old_local_path, new_local_path)
    return normalized, new_relative_path


def _clear_contract_file_path_by_relative_path(relative_file_path: str) -> list[int]:
    normalized_target = _normalize_relative_path(relative_file_path)
    if not normalized_target:
        return []

    affected_ids = []
    rows = Contract.query.filter(Contract.file_path.isnot(None)).all()
    for row in rows:
        if _normalize_contract_file_path(row.file_path) != normalized_target:
            continue
        row.file_path = None
        affected_ids.append(row.id)

    return affected_ids


def _replace_contract_file_path_by_relative_path(old_relative_path: str, new_relative_path: str) -> list[int]:
    normalized_old = _normalize_relative_path(old_relative_path)
    normalized_new = _normalize_relative_path(new_relative_path)
    if not normalized_old or not normalized_new:
        return []

    affected_ids = []
    rows = Contract.query.filter(Contract.file_path.isnot(None)).all()
    for row in rows:
        if _normalize_contract_file_path(row.file_path) != normalized_old:
            continue
        row.file_path = normalized_new
        affected_ids.append(row.id)

    return affected_ids
