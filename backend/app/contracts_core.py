# --- 文件末尾追加 ---
# 仪表盘统计接口，需在 contracts_bp 定义后声明
import os
import posixpath
import re
import json
import time
import tempfile
import getpass
import mimetypes
from importlib import import_module

from difflib import SequenceMatcher
from io import BytesIO
from uuid import uuid4
from urllib.parse import unquote, urlparse
from email.utils import format_datetime
from datetime import timezone
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import String, cast, func, or_
from flask import Blueprint, current_app, g, jsonify, request, send_file
from .auth import get_cached_user_password, require_auth
from .extensions import db
from .models import Contract, Department, ProjectOption
from .ocr_utils import (
    extract_ai_content_from_pdf,
    extract_pdf_text,
    extract_pdf_text_via_ocr,
    get_ocr_engine,
    mineru_extract_text_from_uploaded_pdf,
    mineru_auth_headers,
    _preview_lines,
)

contracts_bp = Blueprint('contracts', __name__, url_prefix='/api')
EXTERNAL_API_TIMEOUT_SECONDS = 300
DEFAULT_DEPARTMENT_NAME = '财务部'

_SYNOLOGY_FILESTATION_CLIENTS = {}



CONTRACT_FIELD_KEYS = [
    'contract_name',
    'contract_number',
    'contract_unit',
    'contract_amount',
    'handler',
    'handling_department',
    'contract_determination_method',
    'handling_date',
    'contract_type',
    'purchase_type',
    'stamp_tax_rate',
    'pricing_method',
    'is_archived',
    'project',
]

STAMP_TAX_RATE_BY_CONTRACT_TYPE = {
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

LEGACY_INVALID_CONTRACT_TYPES = {
    '会议承办',
    '会议承办合同',
    '工程类',
    '采购类',
    '服务类',
}

OPTION_FIELD_DEFAULTS = {
    'project': '无',
    'contract_determination_method': '直接采购',
    'is_archived': '已归档',
}


CSV_OPTION_DEFAULTS = {
    'contract_determination_method': ['询比采购', '竞价采购', '谈判采购', '直接采购','非采购类'],
    'contract_type': ['买卖合同', '借款合同', '租赁合同', '承揽合同', '建设工程合同', '运输合同', '技术合同', '保管合同', '仓储合同', '财产保险合同','人力资源','其它'],
    'purchase_type': ['工程', '服务', '设备采购', '非采购类'],
    'pricing_method': ['单价合同', '总价合同','其他'],
    'is_archived': ['已归档', '未归档'],
}


SYNOLOGY_AUTH_ERROR_MESSAGES = {
    400: '账号或密码错误',
    401: '账号被停用',
    402: '账号权限不足',
    403: '需要二步验证(OTP)',
    404: '二步验证(OTP)错误',
    407: 'IP 被阻止，请稍后重试',
}


SYNOLOGY_COMMON_ERROR_MESSAGES = {
    100: '未知错误',
    101: '参数错误',
    102: 'API 不存在',
    103: '方法不存在',
    104: 'API 版本不支持',
    105: '权限不足',
    106: '会话已超时，请重新登录',
    107: '会话被中断，请重新登录',
    119: '会话无效或不存在，请检查上传会话配置并重新登录',
}


SYNOLOGY_FILESTATION_ERROR_MESSAGES = {
    1100: '请求参数无效或目录/文件名不符合规则',
    400: '上传参数错误',
    401: '文件路径非法',
    402: '系统繁忙，请稍后再试',
    403: '无上传权限',
    404: '目录不存在',
    405: '文件已存在且不允许覆盖',
    406: '存储配额不足',
    407: '存储空间不足',
    408: '文件系统为只读',
    418: '文件名或路径包含非法字符',
    414: '目录已存在',
    415: '目录不存在',
}


AI_AMOUNT_UNIT_TO_YUAN = {
    '元': Decimal('1'),
    '千元': Decimal('1000'),
    '万元': Decimal('10000'),
    '万': Decimal('10000'),
    '亿元': Decimal('100000000'),
    '亿': Decimal('100000000'),
}


EXCEL_ALLOWED_EXTENSIONS = {'.xls', '.xlsx'}


AI_MATCH_CANDIDATE_LIMIT = 20



def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _safe_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _normalize_contract_type_value(value: str) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    if text in LEGACY_INVALID_CONTRACT_TYPES:
        return ''
    return text


def _format_decimal_plain(value: Decimal) -> str:
    text = format(value, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text or '0'




def _department_dir(department: str) -> str:
    root = current_app.config['CONTRACT_STORAGE_ROOT']
    target = os.path.join(root, department)
    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'local':
        os.makedirs(target, exist_ok=True)
    return target


def _build_filestation_path(*parts: str) -> str:
    root = (current_app.config.get('SYNOLOGY_FILESTATION_ROOT') or '/contracts').replace('\\', '/').rstrip('/')
    clean_parts = [str(part).strip('/').replace('\\', '/') for part in parts if str(part).strip('/')]
    if clean_parts:
        return f"{root}/{posixpath.join(*clean_parts)}"
    return root


def _sanitize_upload_filename(file_name: str) -> str:
    base = (file_name or '').strip()
    base = os.path.basename(base).replace('\\', '').replace('/', '')
    if not base:
        return 'upload.bin'
    return base


def _next_available_filename(existing_names, incoming_name: str) -> str:
    existing = set(existing_names)
    if incoming_name not in existing:
        return incoming_name

    stem, ext = os.path.splitext(incoming_name)
    match = re.match(r'^(.*)_(\d+)$', stem)
    if match:
        base_stem = match.group(1)
        number = int(match.group(2)) + 1
    else:
        base_stem = stem
        number = 1

    while True:
        candidate = f"{base_stem}_{number}{ext}"
        if candidate not in existing:
            return candidate
        number += 1


def _synology_upload_login() -> str:
    base_url = current_app.config.get('SYNOLOGY_BASE_URL', '').rstrip('/')
    username = (getattr(g, 'current_user', '') or '').strip()
    if not base_url:
        raise RuntimeError('Missing SYNOLOGY_BASE_URL in .env')
    if not username:
        raise PermissionError('未找到当前登录用户，请重新登录后重试')

    password = get_cached_user_password(username)
    if not password:
        raise PermissionError('登录凭据已过期，请重新登录后重试')

    return _synology_user_login(username, password, session_name='FileStation')


def _synology_sdk_error_payload(exc: Exception) -> dict:
    code = getattr(exc, 'error_code', None)
    return {
        'success': False,
        'error': {
            'code': code if code is not None else 'exception',
            'message': f'{exc.__class__.__name__}: {exc}',
        },
        'data': {},
    }


def _synology_sdk_normalize_payload(result) -> dict:
    if isinstance(result, dict):
        if 'success' in result:
            return result
        return {'success': True, 'data': result}

    if isinstance(result, tuple) and len(result) == 2:
        status_code, payload = result
        if isinstance(payload, dict):
            if 'success' in payload:
                return payload
            return {
                'success': False,
                'error': {
                    'code': status_code,
                    'message': str(payload),
                },
                'data': payload,
            }

    if isinstance(result, str):
        lowered = result.lower()
        if 'task id is' in lowered or 'taskid' in lowered:
            return {'success': True, 'data': {'message': result}}
        return {
            'success': False,
            'error': {
                'code': 'sdk-error',
                'message': result,
            },
            'data': {},
        }

    return {
        'success': False,
        'error': {
            'code': 'unknown-sdk-result',
            'message': str(result),
        },
        'data': {},
    }


def _synology_parse_array_text(value):
    if isinstance(value, list):
        return [str(item or '').strip() for item in value if str(item or '').strip()]

    text = str(value or '').strip()
    if not text:
        return []

    if text.startswith('[') and text.endswith(']'):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item or '').strip() for item in parsed if str(item or '').strip()]
        except Exception:
            pass

    cleaned = text.strip('"').strip()
    return [cleaned] if cleaned else []


def _synology_json_array_text(value) -> str:
    return json.dumps(_synology_parse_array_text(value), ensure_ascii=False)


def _synology_bool_text(value, default=False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes'}


def _coerce_unix_timestamp(value):
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        parsed = int(value)
        return parsed if parsed > 0 else None

    text = str(value).strip()
    if not text:
        return None

    try:
        parsed = int(float(text))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _synology_new_filestation_client(account: str, password: str):
    base_url = (current_app.config.get('SYNOLOGY_BASE_URL') or '').strip()
    if not base_url or not account or not password:
        raise RuntimeError('Missing Synology login parameters')

    parsed = urlparse(base_url)
    if not parsed.hostname:
        raise RuntimeError(f'Invalid SYNOLOGY_BASE_URL: {base_url}')

    secure = parsed.scheme.lower() == 'https'
    port = parsed.port or (5001 if secure else 5000)

    # synology-api 0.8.2 使用 BaseApi.shared_session 全局复用，可能造成跨 application API 列表污染。
    base_api = import_module('synology_api.base_api')
    base_api.BaseApi.shared_session = None

    filestation = import_module('synology_api.filestation')
    return filestation.FileStation(
        parsed.hostname,
        str(port),
        account,
        password,
        secure=secure,
        cert_verify=bool(current_app.config.get('SYNOLOGY_VERIFY_SSL', False)),
        dsm_version=int(current_app.config.get('SYNOLOGY_DSM_VERSION', 7)),
        debug=False,
        interactive_output=False,
    )


def _synology_get_filestation_client_by_sid(sid: str):
    sid_text = str(sid or '').strip()
    if sid_text and sid_text in _SYNOLOGY_FILESTATION_CLIENTS:
        return _SYNOLOGY_FILESTATION_CLIENTS[sid_text]

    username = (getattr(g, 'current_user', '') or '').strip()
    if not username:
        raise PermissionError('未找到当前登录用户，请重新登录后重试')

    password = get_cached_user_password(username)
    if not password:
        raise PermissionError('登录凭据已过期，请重新登录后重试')

    client = _synology_new_filestation_client(username, password)
    new_sid = str(getattr(client, '_sid', '') or '').strip()
    if new_sid:
        _SYNOLOGY_FILESTATION_CLIENTS[new_sid] = client
    return client


def _synology_user_login(account: str, password: str, session_name: str = 'DocsCoolDownload') -> str:
    _ = session_name
    client = _synology_new_filestation_client(account, password)
    sid = str(getattr(client, '_sid', '') or '').strip()
    if not sid:
        raise RuntimeError('Synology 登录失败: 未返回有效会话')

    _SYNOLOGY_FILESTATION_CLIENTS[sid] = client
    return sid


def _synology_api_get(sid: str, params: dict) -> dict:
    api_name = str((params or {}).get('api') or '').strip()
    method_name = str((params or {}).get('method') or '').strip().lower()

    try:
        client = _synology_get_filestation_client_by_sid(sid)

        if api_name == 'SYNO.FileStation.List' and method_name == 'list':
            result = client.get_file_list(
                folder_path=(params or {}).get('folder_path'),
                additional=_synology_json_array_text((params or {}).get('additional')),
            )
            return _synology_sdk_normalize_payload(result)

        return {
            'success': False,
            'error': {
                'code': 'unsupported-sdk-api',
                'message': f'Unsupported GET API mapping: {api_name}.{method_name}',
            },
            'data': {},
        }
    except Exception as exc:
        return _synology_sdk_error_payload(exc)


def _synology_api_post(sid: str, params: dict, data: dict = None, files: dict = None) -> dict:
    api_name = str((params or {}).get('api') or '').strip()
    method_name = str((params or {}).get('method') or '').strip().lower()
    body = data or {}

    try:
        client = _synology_get_filestation_client_by_sid(sid)

        if api_name == 'SYNO.FileStation.CreateFolder' and method_name == 'create':
            folder_path_values = _synology_parse_array_text(body.get('folder_path'))
            name_values = _synology_parse_array_text(body.get('name'))
            folder_path_param = folder_path_values if len(folder_path_values) != 1 else folder_path_values[0]
            name_param = name_values if len(name_values) != 1 else name_values[0]
            result = client.create_folder(
                folder_path=folder_path_param,
                name=name_param,
                force_parent=_synology_bool_text(body.get('force_parent'), default=False),
            )
            return _synology_sdk_normalize_payload(result)

        if api_name == 'SYNO.FileStation.Upload' and method_name == 'upload':
            file_payload = (files or {}).get('file')
            if not isinstance(file_payload, tuple) or len(file_payload) < 2:
                return {
                    'success': False,
                    'error': {'code': 101, 'message': 'file is required'},
                    'data': {},
                }

            upload_name = str(file_payload[0] or 'upload.bin')
            stream = file_payload[1]

            with tempfile.TemporaryDirectory(prefix='docscool_upload_') as tmp_dir:
                tmp_path = os.path.join(tmp_dir, upload_name)
                with open(tmp_path, 'wb') as tmp_file:
                    content = stream.read() if hasattr(stream, 'read') else b''
                    if isinstance(content, str):
                        content = content.encode('utf-8')
                    tmp_file.write(content or b'')

                if hasattr(stream, 'seek'):
                    try:
                        stream.seek(0)
                    except Exception:
                        pass

                result = client.upload_file(
                    dest_path=str(body.get('path') or ''),
                    file_path=tmp_path,
                    create_parents=_synology_bool_text(body.get('create_parents'), default=True),
                    overwrite=_synology_bool_text(body.get('overwrite'), default=False),
                    verify=bool(current_app.config.get('SYNOLOGY_VERIFY_SSL', False)),
                    progress_bar=False,
                )
                return _synology_sdk_normalize_payload(result)

        if api_name == 'SYNO.FileStation.Delete' and method_name in {'delete', 'start'}:
            path_values = _synology_parse_array_text(body.get('path'))
            path_param = path_values if len(path_values) != 1 else path_values[0]
            result = client.start_delete_task(
                path=path_param,
                recursive=_synology_bool_text(body.get('recursive'), default=False),
            )
            return _synology_sdk_normalize_payload(result)

        if api_name == 'SYNO.FileStation.Rename' and method_name == 'rename':
            path_values = _synology_parse_array_text(body.get('path'))
            name_values = _synology_parse_array_text(body.get('name'))
            path_param = path_values if len(path_values) != 1 else path_values[0]
            name_param = name_values if len(name_values) != 1 else name_values[0]
            result = client.rename_folder(path=path_param, name=name_param)
            return _synology_sdk_normalize_payload(result)

        if api_name == 'SYNO.FileStation.CopyMove' and method_name == 'start':
            path_values = _synology_parse_array_text(body.get('path'))
            path_param = path_values if len(path_values) != 1 else path_values[0]
            result = client.start_copy_move(
                path=path_param,
                dest_folder_path=str(body.get('dest_folder_path') or ''),
                remove_src=_synology_bool_text(body.get('remove_src'), default=False),
                overwrite=_synology_bool_text(body.get('overwrite'), default=False),
            )
            return _synology_sdk_normalize_payload(result)

        return {
            'success': False,
            'error': {
                'code': 'unsupported-sdk-api',
                'message': f'Unsupported POST API mapping: {api_name}.{method_name}',
            },
            'data': {},
        }
    except Exception as exc:
        return _synology_sdk_error_payload(exc)


def _synology_json_array(*values: str) -> str:
    return json.dumps([str(value or '') for value in values], ensure_ascii=False)


def _synology_ensure_remote_folder(sid: str, remote_folder: str) -> None:
    parent = posixpath.dirname(remote_folder.rstrip('/')) or '/'
    leaf = posixpath.basename(remote_folder.rstrip('/'))
    if not leaf:
        return

    payload = _synology_api_post(
        sid,
        {
            'api': 'SYNO.FileStation.CreateFolder',
            'version': '2',
            'method': 'create',
        },
        data={
            'folder_path': _synology_json_array(parent),
            'name': _synology_json_array(leaf),
            'force_parent': 'true',
        },
    )

    if payload.get('success'):
        return

    code = _synology_error_code(payload)
    # Existing folder should not block upload.
    if code in {408, 414}:
        return
    raise RuntimeError(f"Synology 创建目录失败: {_synology_error_message(payload, 'filestation')}")


def _synology_list_file_names(sid: str, remote_folder: str):
    payload = _synology_api_get(
        sid,
        {
            'api': 'SYNO.FileStation.List',
            'version': '2',
            'method': 'list',
            'folder_path': remote_folder,
            'additional': '[]',
        },
    )
    if not payload.get('success'):
        raise RuntimeError(f"Synology 目录读取失败: {_synology_error_message(payload, 'filestation')}")

    files = payload.get('data', {}).get('files', [])
    return [item.get('name', '') for item in files if not item.get('isdir')]


def _synology_upload_file(remote_folder: str, file_name: str, uploaded_file) -> None:
    sid = _synology_upload_login()

    _synology_ensure_remote_folder(sid, remote_folder)
    existing_names = _synology_list_file_names(sid, remote_folder)
    resolved_name = _next_available_filename(existing_names, file_name)

    payload = _synology_api_post(
        sid,
        {
            'api': 'SYNO.FileStation.Upload',
            'version': '2',
            'method': 'upload',
        },
        data={
            'path': remote_folder,
            'create_parents': 'true',
            'overwrite': 'false',
        },
        files={
            'file': (resolved_name, uploaded_file.stream, uploaded_file.mimetype or 'application/octet-stream'),
        },
    )
    if not payload.get('success'):
        raise RuntimeError(f"Synology 文件上传失败: {_synology_error_message(payload, 'filestation')}")

    return resolved_name


def _build_synology_file_path(*parts: str) -> str:
    clean_parts = [str(part).strip('/').replace('\\', '/') for part in parts if str(part).strip('/')]
    return posixpath.join(*clean_parts) if clean_parts else ''


def _filename_from_content_disposition(value: str) -> str:
    if not value:
        return ''

    match_utf8 = re.search(r"filename\*=UTF-8''([^;]+)", value, flags=re.IGNORECASE)
    if match_utf8:
        return unquote(match_utf8.group(1).strip('"'))

    match_plain = re.search(r'filename=([^;]+)', value, flags=re.IGNORECASE)
    if match_plain:
        return match_plain.group(1).strip().strip('"')

    return ''


def _safe_local_file_path(relative_path: str) -> str:
    root = os.path.abspath(current_app.config['CONTRACT_STORAGE_ROOT'])
    normalized = (relative_path or '').replace('\\', '/').lstrip('/')
    resolved = os.path.abspath(os.path.join(root, normalized.replace('/', os.sep)))
    if os.path.commonpath([root, resolved]) != root:
        raise ValueError('invalid file_path')
    return resolved


def _normalize_contract_file_path(raw_path: str) -> str:
    if not raw_path:
        return ''

    value = str(raw_path).strip().replace('\\', '/')
    if not value:
        return ''

    base_url = (current_app.config.get('SYNOLOGY_BASE_URL') or '').strip().rstrip('/')
    storage_root = (current_app.config.get('CONTRACT_STORAGE_ROOT') or '').strip().replace('\\', '/').rstrip('/')
    filestation_root = (current_app.config.get('SYNOLOGY_FILESTATION_ROOT') or '').strip().replace('\\', '/').rstrip('/')

    if base_url and value.startswith(base_url):
        value = value[len(base_url):]
    value = value.lstrip('/')

    if storage_root and value.startswith(storage_root.lstrip('/') + '/'):
        value = value[len(storage_root.lstrip('/')) + 1:]
    elif storage_root and value == storage_root.lstrip('/'):
        value = ''

    if filestation_root and value.startswith(filestation_root.lstrip('/') + '/'):
        value = value[len(filestation_root.lstrip('/')) + 1:]
    elif filestation_root and value == filestation_root.lstrip('/'):
        value = ''

    return value.lstrip('/')


def _load_contract_file_payload(record: Contract):
    normalized_file_path = _normalize_contract_file_path(record.file_path)
    if not normalized_file_path:
        raise FileNotFoundError('该合同未上传文件')

    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        password = get_cached_user_password(g.current_user)
        if not password:
            raise PermissionError('登录凭据已过期，请重新登录后下载')

        remote_file_path = _build_filestation_path(normalized_file_path)
        client = _synology_new_filestation_client(g.current_user, password)
        sid = str(getattr(client, '_sid', '') or '').strip()
        if sid:
            _SYNOLOGY_FILESTATION_CLIENTS[sid] = client

        try:
            content_stream = client.get_file(
                path=remote_file_path,
                mode='serve',
                verify=bool(current_app.config.get('SYNOLOGY_VERIFY_SSL', False)),
            )
        except Exception as exc:
            payload = _synology_sdk_error_payload(exc)
            code = _synology_error_code(payload)
            if code in {404, 415}:
                raise FileNotFoundError('文件不存在或路径无效')
            raise RuntimeError(_synology_error_message(payload, 'filestation'))

        if content_stream is None:
            raise FileNotFoundError('文件不存在或路径无效')
        if isinstance(content_stream, str):
            raise RuntimeError(content_stream)

        file_name = os.path.basename(normalized_file_path) or f'contract_{record.id}.bin'
        mime = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
        return content_stream.read(), file_name, mime

    local_file_path = _safe_local_file_path(normalized_file_path)
    if not os.path.isfile(local_file_path):
        raise FileNotFoundError('文件不存在或已被移动')

    file_name = os.path.basename(local_file_path)
    mime = 'application/pdf' if file_name.lower().endswith('.pdf') else 'application/octet-stream'
    with open(local_file_path, 'rb') as f:
        return f.read(), file_name, mime


def _delete_contract_file(record: Contract) -> None:
    normalized_file_path = _normalize_contract_file_path(record.file_path)
    if not normalized_file_path:
        return

    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        remote_file_path = _build_filestation_path(normalized_file_path)
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
        if payload.get('success'):
            return

        code = _synology_error_code(payload)
        if code in {404, 415}:
            return
        raise RuntimeError(_synology_error_message(payload, 'filestation'))

    local_file_path = _safe_local_file_path(normalized_file_path)
    if os.path.isfile(local_file_path):
        os.remove(local_file_path)


def _normalize_relative_path(raw_path: str) -> str:
    value = (raw_path or '').replace('\\', '/').strip().lstrip('/')
    if not value:
        return ''

    normalized = posixpath.normpath(value)
    if normalized in {'.', ''}:
        return ''
    if normalized == '..' or normalized.startswith('../'):
        raise ValueError('invalid path')
    return normalized.lstrip('/')


def _safe_local_folder_path(relative_path: str) -> str:
    root = os.path.abspath(current_app.config['CONTRACT_STORAGE_ROOT'])
    normalized = _normalize_relative_path(relative_path)
    resolved = os.path.abspath(os.path.join(root, normalized.replace('/', os.sep)))
    if os.path.commonpath([root, resolved]) != root:
        raise ValueError('invalid path')
    return resolved


def _list_local_entries(relative_path: str):
    folder_path = _safe_local_folder_path(relative_path)
    if not os.path.isdir(folder_path):
        raise FileNotFoundError('目录不存在')

    directories = []
    files = []
    with os.scandir(folder_path) as entries:
        for entry in entries:
            entry_rel_path = _build_synology_file_path(relative_path, entry.name)
            if entry.is_dir(follow_symlinks=False):
                directories.append({
                    'name': entry.name,
                    'path': entry_rel_path,
                })
            elif entry.is_file(follow_symlinks=False):
                stat_result = entry.stat(follow_symlinks=False)
                modified_by = getpass.getuser() or '-'
                files.append({
                    'name': entry.name,
                    'path': entry_rel_path,
                    'size': int(stat_result.st_size),
                    'mtime': int(stat_result.st_mtime),
                    'modified_by': modified_by,
                })

    directories.sort(key=lambda item: item['name'].lower())
    files.sort(key=lambda item: item['name'].lower())
    return directories, files


def _remote_folder_path(relative_path: str) -> str:
    normalized = _normalize_relative_path(relative_path)
    return _build_filestation_path(normalized)


def _list_remote_entries(relative_path: str, sid: str = ''):
    resolved_sid = sid or _synology_upload_login()
    folder_path = _remote_folder_path(relative_path)
    payload = _synology_api_get(
        resolved_sid,
        {
            'api': 'SYNO.FileStation.List',
            'version': '2',
            'method': 'list',
            'folder_path': folder_path,
            'additional': '["size","time","owner"]',
        },
    )
    if not payload.get('success'):
        code = _synology_error_code(payload)
        if code in {404, 415}:
            raise FileNotFoundError('目录不存在')
        raise RuntimeError(_synology_error_message(payload, 'filestation'))

    directories = []
    files = []
    for item in payload.get('data', {}).get('files', []):
        name = (item.get('name') or '').strip()
        if not name:
            continue

        entry_rel_path = _build_synology_file_path(relative_path, name)
        if item.get('isdir'):
            directories.append({
                'name': name,
                'path': entry_rel_path,
            })
            continue

        additional = item.get('additional') or {}
        mtime = _coerce_unix_timestamp((additional.get('time') or {}).get('mtime'))
        size = additional.get('size')
        owner = additional.get('owner') or {}
        modified_by = (
            (owner.get('user') or '').strip()
            or (owner.get('group') or '').strip()
            or (owner.get('uid') or '').strip()
            or '-'
        )
        files.append({
            'name': name,
            'path': entry_rel_path,
            'size': int(size) if isinstance(size, (int, float)) else 0,
            'mtime': mtime,
            'modified_by': modified_by,
        })

    directories.sort(key=lambda entry: entry['name'].lower())
    files.sort(key=lambda entry: entry['name'].lower())
    return directories, files


def _list_storage_entries(relative_path: str):
    normalized = _normalize_relative_path(relative_path)
    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        return _list_remote_entries(normalized)
    return _list_local_entries(normalized)


def _build_folder_tree(relative_path: str):
    directories, _files = _list_storage_entries(relative_path)
    children = [_build_folder_tree(item['path']) for item in directories]
    name = os.path.basename(relative_path.rstrip('/')) if relative_path else ''
    return {
        'name': name or _storage_root_name(),
        'path': relative_path,
        'children': children,
    }


def _storage_root_name() -> str:
    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        root = (current_app.config.get('SYNOLOGY_FILESTATION_ROOT') or '').replace('\\', '/').rstrip('/')
    else:
        root = (current_app.config.get('CONTRACT_STORAGE_ROOT') or '').replace('\\', '/').rstrip('/')
    return os.path.basename(root) or root or '/'


def _normalize_match_text(value: str) -> str:
    text = str(value or '').strip().lower()
    if not text:
        return ''
    text = re.sub(r'\.(pdf|PDF)$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[^\w\u4e00-\u9fff]+', '', text)
    return text


def _collect_storage_pdf_files() -> list:
    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        sid = _synology_upload_login()
        stack = ['']
        result = []
        while stack:
            current_path = stack.pop()
            directories, files = _list_remote_entries(current_path, sid=sid)
            for item in files:
                name = item.get('name') or ''
                if name.lower().endswith('.pdf'):
                    result.append({
                        'name': name,
                        'path': item.get('path') or '',
                        'mtime': _coerce_unix_timestamp(item.get('mtime')) or 0,
                        'modified_by': (item.get('modified_by') or '').strip() or '-',
                    })
            for directory in directories:
                child_path = directory.get('path') or ''
                if child_path:
                    stack.append(child_path)
        return result

    root = os.path.abspath(current_app.config['CONTRACT_STORAGE_ROOT'])
    result = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            if not filename.lower().endswith('.pdf'):
                continue
            full_path = os.path.join(dirpath, filename)
            relative_path = os.path.relpath(full_path, root).replace('\\', '/')
            try:
                mtime = int(os.path.getmtime(full_path))
            except OSError:
                mtime = 0
            result.append({
                'name': filename,
                'path': relative_path,
                'mtime': mtime,
                'modified_by': getpass.getuser() or '-',
            })
    return result


def _collect_storage_files() -> list:
    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        sid = _synology_upload_login()
        stack = ['']
        result = []
        while stack:
            current_path = stack.pop()
            directories, files = _list_remote_entries(current_path, sid=sid)
            for item in files:
                result.append({
                    'name': item.get('name') or '',
                    'path': item.get('path') or '',
                    'mtime': _coerce_unix_timestamp(item.get('mtime')) or 0,
                })
            for directory in directories:
                child_path = directory.get('path') or ''
                if child_path:
                    stack.append(child_path)
        return result

    root = os.path.abspath(current_app.config['CONTRACT_STORAGE_ROOT'])
    result = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            relative_path = os.path.relpath(full_path, root).replace('\\', '/')
            try:
                mtime = int(os.path.getmtime(full_path))
            except OSError:
                mtime = 0
            result.append({
                'name': filename,
                'path': relative_path,
                'mtime': mtime,
            })
    return result


def _select_best_pdf_match(row, pdf_files: list):
    def _to_year(value: str):
        text = str(value or '').strip()
        if not text.isdigit():
            return None
        num = int(text)
        if 1000 <= num <= 9999:
            return num
        if 0 <= num <= 99:
            return 2000 + num
        return None

    def _extract_path_year_range(path_value: str):
        path_text = str(path_value or '')
        if not path_text:
            return None

        # 匹配形如: 2021-2023 / 21-23 / 2021－23 等范围写法
        range_match = re.search(r'(\d{2,4})[^\d]*[\-－~—–_][^\d]*(\d{2,4})', path_text)
        if range_match:
            start_year = _to_year(range_match.group(1))
            end_year = _to_year(range_match.group(2))
            if start_year and end_year:
                return min(start_year, end_year), max(start_year, end_year)

        # 匹配单个年份: 2024 或 24（按 20XX 解释）
        single_match = re.search(r'(?<!\d)(\d{4}|\d{2})(?!\d)', path_text)
        if single_match:
            year = _to_year(single_match.group(1))
            if year:
                return year, year

        return None

    def _extract_contract_year(value):
        if isinstance(value, date):
            return value.year
        if isinstance(value, datetime):
            return value.year
        text = str(value or '').strip()
        match = re.search(r'(20\d{2})', text)
        if match:
            return int(match.group(1))
        return None

    contract_name = row.contract_name or ''
    normalized_contract = _normalize_match_text(contract_name)
    if not normalized_contract:
        return None, []

    contract_year = _extract_contract_year(getattr(row, 'handling_date', None))

    matched = []

    department = (getattr(row, 'department', '') or '').strip()
    if department:

        for item in pdf_files:
            item_path = item.get('path') or ''
            if department not in item_path:
                continue
            
            #如果item的name中匹配row.contract_number,即有包含关系又要防止短的合同编号（字母数字和连字符）误匹配长的，则优先匹配
            contract_number_in_name = re.search(r'([a-zA-Z0-9\-]{5,})', item.get('name') or '')
            if row.contract_number and contract_number_in_name and row.contract_number == contract_number_in_name.group(0):
                exact_match = {
                    'name': item.get('name') or '', 
                    'path': item.get('path') or '',
                    'similarity': 1.0,
                    'mtime': _coerce_unix_timestamp(item.get('mtime')) or 0,
                }
                return exact_match, [exact_match]
            




            year_range = _extract_path_year_range(item.get('path').split('/')[1] if len(item.get('path').split('/')) > 1 else '')
            if contract_year and year_range:
                start_year, end_year = year_range
                if start_year <= contract_year <= end_year:
                    similarity = SequenceMatcher(None, normalized_contract, _normalize_match_text(item.get('name') or '')).ratio()         
                    matched.append({
                        'name': item.get('name') or '', 
                        'path': item.get('path') or '',
                        'similarity': similarity,
                        'mtime': _coerce_unix_timestamp(item.get('mtime')) or 0,
                    })
        if matched:
            matched.sort(key=lambda row: (-row['similarity'], -row['mtime'], row['name']))
            return matched[0], matched

    matched = []

    for item in pdf_files:
        

        file_name = item.get('name') or ''
        normalized_file = _normalize_match_text(file_name)
        if not normalized_file:
            continue
        if normalized_contract in normalized_file:
            similarity = SequenceMatcher(None, normalized_contract, normalized_file).ratio()
            matched.append({
                'name': file_name,
                'path': item.get('path') or '',
                'similarity': similarity,
                'mtime': _coerce_unix_timestamp(item.get('mtime')) or 0,
            })

    if not matched:
        return None, []

    matched.sort(key=lambda row: (-row['similarity'], -row['mtime'], row['name']))
    return matched[0], matched


def _get_department_names():
    rows = Department.query.order_by(Department.name.asc()).all()
    return [row.name for row in rows]


def _get_project_names():
    rows = ProjectOption.query.order_by(ProjectOption.name.asc()).all()
    return [row.name for row in rows]


def _merge_options(default_values, db_values):
    merged = []
    seen = set()
    for item in default_values + db_values:
        value = (item or '').strip()
        if not value or value in seen:
            continue
        seen.add(value)
        merged.append(value)
    return merged


def _synology_error_code(payload: dict):
    error = payload.get('error') or {}
    code = error.get('code')
    if code is None:
        return None
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def _synology_error_message(payload: dict, scope: str) -> str:
    code = _synology_error_code(payload)
    if code is None:
        return 'Synology 未返回具体错误码'

    if scope == 'auth':
        text = SYNOLOGY_AUTH_ERROR_MESSAGES.get(code)
    elif scope == 'filestation':
        text = SYNOLOGY_FILESTATION_ERROR_MESSAGES.get(code)
    else:
        text = None

    if text is None:
        text = SYNOLOGY_COMMON_ERROR_MESSAGES.get(code, '未知错误')
    return f'{text}(错误码: {code})'

from .contracts_core_ai import (
    _extract_ai_content,
    _extract_json_object,
    _normalize_date_value,
    _find_contract_number,
    _find_amount,
    _normalize_company_name,
    _exclude_my_company,
    _normalize_ai_fields,
    _normalize_option_text,
    _find_ai_match_candidates,
    _match_option_value,
    _get_contract_option_sets,
    _normalize_option_fields,
    _has_any_field_value,
    _minimax_extract_fields,
    _preview_lines,
)
