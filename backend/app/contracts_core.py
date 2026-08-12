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
from .auth import require_auth
from .extensions import db
from .models import Contract, Department, ProjectOption, StampTaxRateOption
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
    'current_management_department',
    'contract_form',
    'contract_determination_method',
    'handling_date',
    'contract_type',
    'purchase_type',
    'contract_execution_status',
    'stamp_tax_rate',
    'pricing_method',
    'is_archived',
    'color_flag',
    'completeness',
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
    'project': '',
    'contract_form': '新签合同',
    'contract_determination_method': '直接采购',
    'is_archived': '已归档',
}


CSV_OPTION_DEFAULTS = {
    'contract_form': ['新签合同', '补充合同', '补充协议', '变更合同'],
    'contract_determination_method': ['公开招标', '邀请招标', '询比采购', '竞价采购', '谈判采购', '直接采购', '电商直采', '零星', '其他', '非采购类'],
    'contract_type': ['买卖合同', '借款合同', '租赁合同', '承揽合同', '建设工程合同', '运输合同', '技术合同', '保管合同', '仓储合同', '财产保险合同','人力资源','其它'],
    'purchase_type': ['工程采购', '服务采购', '设备采购', '非采购类'],
    'contract_execution_status': ['正在执行', '正常终止', '变更终止', '解除终止'],
    'pricing_method': ['单价合同', '总价合同','其他'],
    'is_archived': ['已归档', '未归档'],
    'color_flag': ['红旗', '橙旗', '黄旗', '绿旗', '蓝旗'],
    'completeness': ['是', '否'],
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
    username, password = _get_storage_service_credentials()
    if not base_url:
        raise RuntimeError('Missing SYNOLOGY_BASE_URL in .env')

    return _synology_user_login(username, password, session_name='FileStation')


def _get_storage_service_credentials() -> tuple[str, str]:
    username = (current_app.config.get('SYNOLOGY_USER') or '').strip()
    password = (current_app.config.get('SYNOLOGY_PASSWORD') or '').strip()
    if not username or not password:
        raise RuntimeError('Missing SYNOLOGY_USER or SYNOLOGY_PASSWORD in .env')
    return username, password


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
    try:
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
    except Exception as exc:
        payload = _synology_sdk_error_payload(exc)
        code = _synology_error_code(payload)
        scope = 'auth' if exc.__class__.__name__ == 'LoginError' or code in {400, 401, 402, 403, 404, 407} else 'filestation'
        raise RuntimeError(_synology_error_message(payload, scope))


def _synology_get_filestation_client_by_sid(sid: str):
    sid_text = str(sid or '').strip()
    if sid_text and sid_text in _SYNOLOGY_FILESTATION_CLIENTS:
        return _SYNOLOGY_FILESTATION_CLIENTS[sid_text]

    username, password = _get_storage_service_credentials()

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

    for attempt in range(2):
        try:
            current_app.logger.info(
                '[synology-debug] api_get attempt=%s sid=%s api=%s method=%s params=%s',
                attempt + 1,
                bool(sid),
                api_name,
                method_name,
                params,
            )
            client = _synology_get_filestation_client_by_sid(sid)

            if api_name == 'SYNO.FileStation.List' and method_name == 'list':
                result = client.get_file_list(
                    folder_path=(params or {}).get('folder_path'),
                    additional=_synology_json_array_text((params or {}).get('additional')),
                )
                normalized = _synology_sdk_normalize_payload(result)
                current_app.logger.info(
                    '[synology-debug] api_get success attempt=%s sid=%s api=%s method=%s payload=%s',
                    attempt + 1,
                    bool(sid),
                    api_name,
                    method_name,
                    normalized,
                )
                return normalized

            return {
                'success': False,
                'error': {
                    'code': 'unsupported-sdk-api',
                    'message': f'Unsupported GET API mapping: {api_name}.{method_name}',
                },
                'data': {},
            }
        except Exception as exc:
            payload = _synology_sdk_error_payload(exc)
            code = _synology_error_code(payload)
            if attempt == 0 and code in {119, '119'}:
                current_app.logger.warning(
                    '[synology-debug] api_get expired-session retrying sid=%s api=%s method=%s code=%s',
                    bool(sid),
                    api_name,
                    method_name,
                    code,
                )
                sid = _synology_upload_login()
                continue
            current_app.logger.exception(
                '[synology-debug] api_get error attempt=%s sid=%s api=%s method=%s payload=%s',
                attempt + 1,
                bool(sid),
                api_name,
                method_name,
                payload,
            )
            return payload


def _synology_api_post(sid: str, params: dict, data: dict = None, files: dict = None) -> dict:
    api_name = str((params or {}).get('api') or '').strip()
    method_name = str((params or {}).get('method') or '').strip().lower()
    body = data or {}

    for attempt in range(2):
        try:
            current_app.logger.info(
                '[synology-debug] api_post attempt=%s sid=%s api=%s method=%s data=%s files=%s',
                attempt + 1,
                bool(sid),
                api_name,
                method_name,
                body,
                bool(files),
            )
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
                normalized = _synology_sdk_normalize_payload(result)
                current_app.logger.info(
                    '[synology-debug] api_post success attempt=%s sid=%s api=%s method=%s payload=%s',
                    attempt + 1,
                    bool(sid),
                    api_name,
                    method_name,
                    normalized,
                )
                return normalized

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
                    normalized = _synology_sdk_normalize_payload(result)
                    current_app.logger.info(
                        '[synology-debug] api_post success attempt=%s sid=%s api=%s method=%s payload=%s',
                        attempt + 1,
                        bool(sid),
                        api_name,
                        method_name,
                        normalized,
                    )
                    return normalized

            if api_name == 'SYNO.FileStation.Delete' and method_name in {'delete', 'start'}:
                path_values = _synology_parse_array_text(body.get('path'))
                path_param = path_values if len(path_values) != 1 else path_values[0]
                result = client.start_delete_task(
                    path=path_param,
                    recursive=_synology_bool_text(body.get('recursive'), default=False),
                )
                normalized = _synology_sdk_normalize_payload(result)
                current_app.logger.info(
                    '[synology-debug] api_post success attempt=%s sid=%s api=%s method=%s payload=%s',
                    attempt + 1,
                    bool(sid),
                    api_name,
                    method_name,
                    normalized,
                )
                return normalized

            if api_name == 'SYNO.FileStation.Rename' and method_name == 'rename':
                path_values = _synology_parse_array_text(body.get('path'))
                name_values = _synology_parse_array_text(body.get('name'))
                path_param = path_values if len(path_values) != 1 else path_values[0]
                name_param = name_values if len(name_values) != 1 else name_values[0]
                result = client.rename_folder(path=path_param, name=name_param)
                normalized = _synology_sdk_normalize_payload(result)
                current_app.logger.info(
                    '[synology-debug] api_post success attempt=%s sid=%s api=%s method=%s payload=%s',
                    attempt + 1,
                    bool(sid),
                    api_name,
                    method_name,
                    normalized,
                )
                return normalized

            if api_name == 'SYNO.FileStation.CopyMove' and method_name == 'start':
                path_values = _synology_parse_array_text(body.get('path'))
                path_param = path_values if len(path_values) != 1 else path_values[0]
                result = client.start_copy_move(
                    path=path_param,
                    dest_folder_path=str(body.get('dest_folder_path') or ''),
                    remove_src=_synology_bool_text(body.get('remove_src'), default=False),
                    overwrite=_synology_bool_text(body.get('overwrite'), default=False),
                )
                normalized = _synology_sdk_normalize_payload(result)
                current_app.logger.info(
                    '[synology-debug] api_post success attempt=%s sid=%s api=%s method=%s payload=%s',
                    attempt + 1,
                    bool(sid),
                    api_name,
                    method_name,
                    normalized,
                )
                return normalized

            return {
                'success': False,
                'error': {
                    'code': 'unsupported-sdk-api',
                    'message': f'Unsupported POST API mapping: {api_name}.{method_name}',
                },
                'data': {},
            }
        except Exception as exc:
            payload = _synology_sdk_error_payload(exc)
            code = _synology_error_code(payload)
            if attempt == 0 and code in {119, '119'}:
                current_app.logger.warning(
                    '[synology-debug] api_post expired-session retrying sid=%s api=%s method=%s code=%s',
                    bool(sid),
                    api_name,
                    method_name,
                    code,
                )
                sid = _synology_upload_login()
                continue
            current_app.logger.exception(
                '[synology-debug] api_post error attempt=%s sid=%s api=%s method=%s payload=%s',
                attempt + 1,
                bool(sid),
                api_name,
                method_name,
                payload,
            )
            return payload


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
        username, password = _get_storage_service_credentials()

        remote_file_path = _build_filestation_path(normalized_file_path)
        client = _synology_new_filestation_client(username, password)
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


def _sanitize_contract_file_stem(raw_text: str) -> str:
    text = str(raw_text or '').strip()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', '_', text)
    text = re.sub(r'\s+', ' ', text).strip(' .')
    return text


def _build_contract_attachment_base_name(record: Contract) -> str:
    number = _sanitize_contract_file_stem(getattr(record, 'contract_number', '') or '')
    name = _sanitize_contract_file_stem(getattr(record, 'contract_name', '') or '')
    return f"{number}{name}".strip()


def _build_contract_attachment_target_directory(record: Contract) -> str:
    current_management_department = str(getattr(record, 'current_management_department', '') or '').strip()
    if not current_management_department:
        current_management_department = _resolve_current_management_department_name(getattr(record, 'department', '') or '')

    if not current_management_department:
        current_management_department = str(getattr(record, 'department', '') or '').strip()

    if not current_management_department:
        return ''

    handling_date = getattr(record, 'handling_date', None)
    if isinstance(handling_date, (date, datetime)):
        year_text = str(handling_date.year)
    else:
        year_text = str(datetime.now().year)

    return _build_synology_file_path(current_management_department, year_text)


def _next_available_folder_name(parent_dir: str, desired_name: str) -> str:
    if not os.path.isdir(parent_dir):
        return desired_name

    existing = {
        item.name.lower()
        for item in os.scandir(parent_dir)
        if item.is_dir(follow_symlinks=False)
    }
    if desired_name.lower() not in existing:
        return desired_name

    index = 1
    while True:
        candidate = f"{desired_name}_{index}"
        if candidate.lower() not in existing:
            return candidate
        index += 1


def _rename_ocr_dir_for_file_rename(old_file_path: str, new_file_path: str) -> None:
    old_normalized = _normalize_relative_path(old_file_path)
    new_normalized = _normalize_relative_path(new_file_path)
    if not old_normalized or not new_normalized:
        return

    old_parent = posixpath.dirname(old_normalized)
    new_parent = posixpath.dirname(new_normalized)
    old_stem = os.path.splitext(posixpath.basename(old_normalized))[0].strip()
    new_stem = os.path.splitext(posixpath.basename(new_normalized))[0].strip()
    if not old_stem or not new_stem:
        return

    old_ocr_rel = posixpath.join(old_parent, old_stem) if old_parent not in {'', '.'} else old_stem
    new_ocr_rel = posixpath.join(new_parent, new_stem) if new_parent not in {'', '.'} else new_stem
    if old_ocr_rel == new_ocr_rel:
        return

    ocr_root = os.path.realpath(os.path.join(current_app.root_path, '..', 'instance', 'ocr'))
    old_abs = os.path.realpath(os.path.join(ocr_root, old_ocr_rel.replace('/', os.sep)))
    if not (old_abs == ocr_root or old_abs.startswith(ocr_root + os.sep)):
        return
    if not os.path.isdir(old_abs):
        return

    desired_new_abs = os.path.realpath(os.path.join(ocr_root, new_ocr_rel.replace('/', os.sep)))
    if not (desired_new_abs == ocr_root or desired_new_abs.startswith(ocr_root + os.sep)):
        return

    new_parent_abs = os.path.dirname(desired_new_abs)
    os.makedirs(new_parent_abs, exist_ok=True)

    final_stem = os.path.basename(desired_new_abs)
    final_stem = _next_available_folder_name(new_parent_abs, final_stem)
    final_abs = os.path.join(new_parent_abs, final_stem)

    if old_abs == final_abs:
        return

    os.rename(old_abs, final_abs)


def _rename_contract_file_to_contract_identity(record: Contract) -> str:
    normalized_file_path = _normalize_contract_file_path(record.file_path)
    if not normalized_file_path:
        return ''

    old_name = posixpath.basename(normalized_file_path)
    if not old_name:
        return normalized_file_path

    target_directory = _build_contract_attachment_target_directory(record)
    target_base = _build_contract_attachment_base_name(record)
    if not target_base or not target_directory:
        return normalized_file_path

    old_stem, ext = os.path.splitext(old_name)
    desired_name = f"{target_base}{ext}"
    desired_file_path = _build_synology_file_path(target_directory, desired_name)

    if desired_file_path == normalized_file_path:
        return normalized_file_path

    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        remote_folder = _build_filestation_path(target_directory)
        remote_file_path = _build_filestation_path(normalized_file_path)
        sid = _synology_upload_login()
        _synology_ensure_remote_folder(sid, remote_folder)
        existing_names = _synology_list_file_names(sid, remote_folder)
        final_name = _next_available_filename(existing_names, desired_name)

        current_folder = posixpath.dirname(normalized_file_path)
        if current_folder != target_directory:
            payload = _synology_api_post(
                sid,
                {
                    'api': 'SYNO.FileStation.CopyMove',
                    'version': '3',
                    'method': 'start',
                },
                data={
                    'path': f'["{remote_file_path}"]',
                    'dest_folder_path': remote_folder,
                    'remove_src': 'true',
                    'overwrite': 'false',
                },
            )
            if not payload.get('success'):
                raise RuntimeError(f"Synology 文件移动失败: {_synology_error_message(payload, 'filestation')}")

        if final_name != old_name:
            target_remote_path = _build_filestation_path(target_directory, old_name)
            payload = _synology_api_post(
                sid,
                {
                    'api': 'SYNO.FileStation.Rename',
                    'version': '2',
                    'method': 'rename',
                },
                data={
                    'path': _synology_json_array(target_remote_path if current_folder != target_directory else remote_file_path),
                    'name': _synology_json_array(final_name),
                },
            )
            if not payload.get('success'):
                raise RuntimeError(f"Synology 文件重命名失败: {_synology_error_message(payload, 'filestation')}")
        new_file_path = _build_synology_file_path(target_directory, final_name)
    else:
        local_file_path = _safe_local_file_path(normalized_file_path)
        if not os.path.isfile(local_file_path):
            raise FileNotFoundError('文件不存在或已被移动')

        target_local_dir = _safe_local_folder_path(target_directory)
        os.makedirs(target_local_dir, exist_ok=True)
        existing_names = [
            name for name in os.listdir(target_local_dir)
            if os.path.isfile(os.path.join(target_local_dir, name)) and name != old_name
        ]
        final_name = _next_available_filename(existing_names, desired_name)
        new_file_path = _build_synology_file_path(target_directory, final_name)
        if final_name != old_name or posixpath.dirname(normalized_file_path) != target_directory:
            new_local_path = _safe_local_file_path(new_file_path)
            os.rename(local_file_path, new_local_path)

    if old_stem and os.path.splitext(posixpath.basename(new_file_path))[0] != old_stem:
        _rename_ocr_dir_for_file_rename(normalized_file_path, new_file_path)

    return new_file_path


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
                # On Windows, st_ctime is creation time and better matches upload time semantics.
                uploaded_at = int(getattr(stat_result, 'st_ctime', 0) or 0)
                files.append({
                    'name': entry.name,
                    'path': entry_rel_path,
                    'size': int(stat_result.st_size),
                    'mtime': int(stat_result.st_mtime),
                    'uploaded_at': uploaded_at or int(stat_result.st_mtime),
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
    current_app.logger.info(
        '[synology-debug] list_remote_entries start relative_path=%s folder_path=%s sid=%s',
        relative_path,
        folder_path,
        bool(resolved_sid),
    )
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
    current_app.logger.info(
        '[synology-debug] list_remote_entries result relative_path=%s folder_path=%s success=%s payload=%s',
        relative_path,
        folder_path,
        payload.get('success'),
        payload,
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
        time_info = additional.get('time') or {}
        mtime = _coerce_unix_timestamp(time_info.get('mtime'))
        uploaded_at = (
            _coerce_unix_timestamp(time_info.get('crtime'))
            or _coerce_unix_timestamp(time_info.get('ctime'))
            or mtime
        )
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
            'uploaded_at': uploaded_at,
            'modified_by': modified_by,
        })

    directories.sort(key=lambda entry: entry['name'].lower())
    files.sort(key=lambda entry: entry['name'].lower())
    return directories, files


def _list_storage_entries(relative_path: str):
    normalized = _normalize_relative_path(relative_path)
    current_app.logger.info(
        '[synology-debug] list_storage_entries normalized=%s mode=%s',
        normalized,
        current_app.config.get('CONTRACT_STORAGE_MODE'),
    )
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
                        'uploaded_at': _coerce_unix_timestamp(item.get('uploaded_at')) or _coerce_unix_timestamp(item.get('mtime')) or 0,
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
            try:
                uploaded_at = int(os.path.getctime(full_path))
            except OSError:
                uploaded_at = mtime
            result.append({
                'name': filename,
                'path': relative_path,
                'mtime': mtime,
                'uploaded_at': uploaded_at,
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
    rows = (
        Department.query
        .filter(Department.is_existing.is_(True))
        .order_by(Department.name.asc())
        .all()
    )
    return [row.name for row in rows]


def _get_all_department_names():
    rows = Department.query.order_by(Department.name.asc()).all()
    return [row.name for row in rows]


def _resolve_current_management_department_name(department_name: str) -> str:
    normalized = str(department_name or '').strip()
    if not normalized:
        return ''

    row = Department.query.filter_by(name=normalized).first()
    if not row:
        return normalized

    if bool(getattr(row, 'is_existing', True)):
        return normalized

    mapped = str(getattr(row, 'current_department_name', '') or '').strip()
    return mapped or normalized


def _get_project_names():
    rows = ProjectOption.query.order_by(ProjectOption.name.asc()).all()
    return [row.name for row in rows]


def _get_stamp_tax_rate_mapping():
    rows = StampTaxRateOption.query.order_by(StampTaxRateOption.id.asc()).all()
    if not rows:
        return dict(STAMP_TAX_RATE_BY_CONTRACT_TYPE)

    mapping = {}
    for row in rows:
        key = (row.contract_type or '').strip()
        if not key:
            continue
        mapping[key] = (row.tax_rate or '').strip()
    return mapping


def _get_contract_type_options():
    mapping = _get_stamp_tax_rate_mapping()
    options = [key for key in mapping.keys() if key]
    if options:
        return options
    return list(CSV_OPTION_DEFAULTS.get('contract_type', []))


def _get_stamp_tax_rate_by_contract_type(contract_type: str) -> str:
    key = (contract_type or '').strip()
    if not key:
        return ''
    mapping = _get_stamp_tax_rate_mapping()
    return (mapping.get(key) or '').strip()


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
