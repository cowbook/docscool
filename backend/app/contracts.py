import os
import posixpath
import re
import json
from io import BytesIO
from urllib.parse import unquote
from datetime import date
from decimal import Decimal, InvalidOperation

import requests
from pypdf import PdfReader
import fitz
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
from flask import Blueprint, current_app, g, jsonify, request, send_file
from .auth import get_cached_user_password, require_auth
from .extensions import db
from .models import Contract, Department, ProjectOption


contracts_bp = Blueprint('contracts', __name__, url_prefix='/api')
_OCR_ENGINE = None


CONTRACT_FIELD_KEYS = [
    'contract_name',
    'contract_number',
    'contract_unit',
    'contract_amount_wan',
    'approval_status',
    'handler',
    'handling_department',
    'contract_determination_method',
    'handling_date',
    'contract_type',
    'invoice_type',
    'tax_rate',
    'pricing_method',
    'is_archived',
    'project',
]

OPTION_FIELD_DEFAULTS = {
    'project': '无',
    'approval_status': '归档',
    'contract_determination_method': '单一来源',
    'is_archived': '已归档',
}


CSV_OPTION_DEFAULTS = {
    'approval_status': ['作废', '合同订立', '归档', '结束', '编辑', '部门会签'],
    'contract_determination_method': ['公开招标', '公开询价', '协商性谈判', '单一来源', '竞争性谈判', '续签', '补充合同', '议标', '询价', '邀请招标'],
    'contract_type': ['工程类', '服务类', '采购类'],
    'invoice_type': ['其他发票', '增值税专用发票', '增值税普通发票'],
    'pricing_method': ['单价合同', '总价合同'],
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
    account = current_app.config.get('SYNOLOGY_UPLOAD_ACCOUNT', '').strip()
    password = current_app.config.get('SYNOLOGY_UPLOAD_PASSWORD', '')
    session_name = current_app.config.get('SYNOLOGY_UPLOAD_SESSION', 'FileStation')

    if not base_url or not account or not password:
        raise RuntimeError('Missing SYNOLOGY_BASE_URL or upload credentials in .env')

    params = {
        'api': 'SYNO.API.Auth',
        'version': '7',
        'method': 'login',
        'account': account,
        'passwd': password,
        'session': session_name,
        'format': 'sid',
    }

    response = requests.get(
        f"{base_url}/webapi/auth.cgi",
        params=params,
        timeout=10,
        verify=current_app.config.get('SYNOLOGY_VERIFY_SSL', False),
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get('success'):
        raise RuntimeError(f"Synology 登录失败: {_synology_error_message(payload, 'auth')}")

    return payload.get('data', {}).get('sid', '')


def _synology_user_login(account: str, password: str, session_name: str = 'DocsCoolDownload') -> str:
    base_url = current_app.config.get('SYNOLOGY_BASE_URL', '').rstrip('/')
    if not base_url or not account or not password:
        raise RuntimeError('Missing Synology login parameters')

    params = {
        'api': 'SYNO.API.Auth',
        'version': '7',
        'method': 'login',
        'account': account,
        'passwd': password,
        'session': session_name,
        'format': 'sid',
    }

    response = requests.get(
        f"{base_url}/webapi/auth.cgi",
        params=params,
        timeout=10,
        verify=current_app.config.get('SYNOLOGY_VERIFY_SSL', False),
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get('success'):
        raise RuntimeError(f"Synology 登录失败: {_synology_error_message(payload, 'auth')}")
    return payload.get('data', {}).get('sid', '')


def _synology_api_get(sid: str, params: dict) -> dict:
    base_url = current_app.config.get('SYNOLOGY_BASE_URL', '').rstrip('/')
    endpoint = f"{base_url}/webapi/entry.cgi"
    merged = dict(params)
    merged['_sid'] = sid

    response = requests.get(
        endpoint,
        params=merged,
        timeout=30,
        verify=current_app.config.get('SYNOLOGY_VERIFY_SSL', False),
    )
    response.raise_for_status()
    return response.json()


def _synology_api_post(sid: str, params: dict, data: dict = None, files: dict = None) -> dict:
    base_url = current_app.config.get('SYNOLOGY_BASE_URL', '').rstrip('/')
    endpoint = f"{base_url}/webapi/entry.cgi"
    merged = dict(params)
    merged['_sid'] = sid

    response = requests.post(
        endpoint,
        params=merged,
        data=data,
        files=files,
        timeout=60,
        verify=current_app.config.get('SYNOLOGY_VERIFY_SSL', False),
    )
    response.raise_for_status()
    return response.json()


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
            'folder_path': parent,
            'name': leaf,
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
        sid = _synology_user_login(g.current_user, password)
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
                timeout=60,
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
            file_name = os.path.basename(normalized_file_path) or f'contract_{record.id}.bin'

        mime = response.headers.get('Content-Type') or 'application/octet-stream'
        return response.content, file_name, mime

    local_file_path = _safe_local_file_path(normalized_file_path)
    if not os.path.isfile(local_file_path):
        raise FileNotFoundError('文件不存在或已被移动')

    file_name = os.path.basename(local_file_path)
    mime = 'application/pdf' if file_name.lower().endswith('.pdf') else 'application/octet-stream'
    with open(local_file_path, 'rb') as f:
        return f.read(), file_name, mime


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


def _preview_lines(text: str, limit: int = 6):
    lines = [line.strip() for line in (text or '').splitlines() if line.strip()]
    return lines[:limit]


def _extract_pdf_text(uploaded_file):
    try:
        uploaded_file.stream.seek(0)
    except Exception:
        pass

    pdf_bytes = uploaded_file.stream.read()
    if not pdf_bytes:
        current_app.logger.warning('AI parse: uploaded PDF is empty')
        return '', []

    current_app.logger.info('AI parse: PDF bytes=%s', len(pdf_bytes))

    text_from_pdf = ''
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        chunks = []
        for page in reader.pages:
            chunks.append((page.extract_text() or '').strip())
        text_from_pdf = '\n'.join(item for item in chunks if item).strip()
        current_app.logger.info(
            'AI parse: direct PDF text pages=%s chars=%s',
            len(reader.pages),
            len(text_from_pdf),
        )
    except Exception:
        current_app.logger.exception('AI parse: direct PDF text extraction failed')
        text_from_pdf = ''

    if text_from_pdf:
        return text_from_pdf, _preview_lines(text_from_pdf)

    ocr_text = _extract_pdf_text_via_ocr(pdf_bytes)
    return ocr_text, _preview_lines(ocr_text)


def _get_ocr_engine():
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def _extract_pdf_text_via_ocr(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    ocr = _get_ocr_engine()

    all_text = []
    max_pages = min(len(doc), 20)
    current_app.logger.info('AI parse: OCR fallback enabled, pages=%s (max=%s)', len(doc), max_pages)
    for i in range(max_pages):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        img_array = np.array(image)
        result, _ = ocr(img_array)
        if not result:
            current_app.logger.info('AI parse: OCR page=%s no text detected', i + 1)
            continue

        line_text = []
        for item in result:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                text = item[1]
                if isinstance(text, str) and text.strip():
                    line_text.append(text.strip())
        if line_text:
            all_text.append('\n'.join(line_text))
            current_app.logger.info('AI parse: OCR page=%s lines=%s', i + 1, len(line_text))

    ocr_text = '\n'.join(all_text).strip()
    current_app.logger.info('AI parse: OCR total chars=%s', len(ocr_text))
    return ocr_text
def _extract_ai_content(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ''

    output_text = payload.get('output_text')
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    reply = payload.get('reply')
    if isinstance(reply, str):
        return reply

    if isinstance(payload.get('message'), str):
        return payload.get('message')

    choices = payload.get('choices')
    if isinstance(choices, list) and choices:
        message = choices[0].get('message') if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            content = message.get('content')
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and isinstance(item.get('text'), str):
                        text_parts.append(item.get('text'))
                if text_parts:
                    return '\n'.join(text_parts)
        text = choices[0].get('text') if isinstance(choices[0], dict) else None
        if isinstance(text, str) and text.strip():
            return text

    data = payload.get('data')
    if isinstance(data, dict) and isinstance(data.get('reply'), str):
        return data.get('reply')

    if isinstance(data, dict):
        nested_choices = data.get('choices')
        if isinstance(nested_choices, list) and nested_choices:
            nested_msg = nested_choices[0].get('message') if isinstance(nested_choices[0], dict) else None
            if isinstance(nested_msg, dict):
                nested_content = nested_msg.get('content')
                if isinstance(nested_content, str) and nested_content.strip():
                    return nested_content

    result = payload.get('result')
    if isinstance(result, str) and result.strip():
        return result

    return ''


def _extract_json_object(text: str) -> dict:
    if not text:
        return {}

    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = stripped.find('{')
    end = stripped.rfind('}')
    if start >= 0 and end > start:
        candidate = stripped[start:end + 1]
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    return {}


def _normalize_date_value(value: str) -> str:
    text = (value or '').strip()
    if not text:
        return ''

    match = re.search(r'(20\d{2})[-/.年\s]+(\d{1,2})[-/.月\s]+(\d{1,2})', text)
    if not match:
        return text

    year, month, day = match.groups()
    return f'{year}-{int(month):02d}-{int(day):02d}'


def _find_contract_number(pdf_text: str, fallback: str) -> str:
    text = (pdf_text or '').replace(' ', '')
    patterns = [
        r'合同编号[:：]?([A-Za-z]{1,4}\d{2,8}-\d{1,4})',
        r'\b([A-Za-z]{1,4}\d{2,8}-\d{1,4})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()

    cleaned = re.sub(r'[^A-Za-z0-9-]', '', (fallback or '').upper())
    return cleaned


def _find_amount_wan(pdf_text: str, fallback: str) -> str:
    text = (pdf_text or '').replace(',', '')
    patterns = [
        r'([0-9]+(?:\.[0-9]+)?)\s*万元',
        r'金额[（(]?万元[）)]?[^0-9]*([0-9]+(?:\.[0-9]+)?)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    cleaned = re.sub(r'[^0-9.]', '', (fallback or '').strip())
    if cleaned.count('.') > 1:
        first_dot = cleaned.find('.')
        cleaned = cleaned[:first_dot + 1] + cleaned[first_dot + 1:].replace('.', '')
    return cleaned


def _find_tax_rate(pdf_text: str, fallback: str) -> str:
    text = (pdf_text or '').replace(' ', '')
    match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*%', text)
    if match:
        return f"{match.group(1)}%"
    cleaned = re.sub(r'[^0-9.%]', '', (fallback or '').strip())
    if cleaned and not cleaned.endswith('%') and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', cleaned):
        return f'{cleaned}%'
    return cleaned


def _normalize_company_name(value: str) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    return re.sub(r'[^\w\u4e00-\u9fff]+', '', text).lower()


def _exclude_my_company(contract_unit: str) -> str:
    my_comp = current_app.config.get('MY_COMP', '')
    if not my_comp:
        return (contract_unit or '').strip()

    parts = [
        part.strip()
        for part in re.split(r'[、,，;；/\\\n]+', contract_unit or '')
        if part and part.strip()
    ]
    if not parts:
        return ''

    my_comp_norm = _normalize_company_name(my_comp)
    kept = [part for part in parts if _normalize_company_name(part) != my_comp_norm]

    if not kept:
        return ''
    return '、'.join(kept)


def _normalize_ai_fields(raw: dict, pdf_text: str = '') -> dict:
    normalized = {}
    for key in CONTRACT_FIELD_KEYS:
        value = raw.get(key) if isinstance(raw, dict) else None
        if value is None:
            normalized[key] = ''
        elif isinstance(value, (int, float)):
            normalized[key] = str(value)
        else:
            normalized[key] = str(value).strip()

    normalized['contract_number'] = _find_contract_number(pdf_text, normalized.get('contract_number', ''))
    normalized['contract_unit'] = _exclude_my_company(normalized.get('contract_unit', ''))
    normalized['contract_amount_wan'] = _find_amount_wan(pdf_text, normalized.get('contract_amount_wan', ''))
    normalized['handling_date'] = _normalize_date_value(normalized.get('handling_date', ''))
    normalized['tax_rate'] = _find_tax_rate(pdf_text, normalized.get('tax_rate', ''))
    return normalized


def _normalize_option_text(value: str) -> str:
    text = (value or '').strip().lower()
    return re.sub(r'[^\w\u4e00-\u9fff]+', '', text)


def _match_option_value(value: str, options, default: str = '') -> str:
    candidates = [item for item in (options or []) if str(item).strip()]
    if not candidates:
        return default

    raw = (value or '').strip()
    if not raw:
        return default

    if raw in candidates:
        return raw

    norm_raw = _normalize_option_text(raw)
    if not norm_raw:
        return default

    for item in candidates:
        if _normalize_option_text(item) == norm_raw:
            return item

    best = ''
    best_score = 0
    for item in candidates:
        norm_item = _normalize_option_text(item)
        if not norm_item:
            continue
        if norm_item in norm_raw or norm_raw in norm_item:
            score = min(len(norm_item), len(norm_raw))
            if score > best_score:
                best = item
                best_score = score

    if best:
        return best
    return default


def _get_contract_option_sets() -> dict:
    contract_rows = Contract.query.all()
    db_values = {
        'approval_status': [row.approval_status for row in contract_rows if row.approval_status],
        'contract_determination_method': [row.contract_determination_method for row in contract_rows if row.contract_determination_method],
        'contract_type': [row.contract_type for row in contract_rows if row.contract_type],
        'invoice_type': [row.invoice_type for row in contract_rows if row.invoice_type],
        'pricing_method': [row.pricing_method for row in contract_rows if row.pricing_method],
        'is_archived': [row.is_archived for row in contract_rows if row.is_archived],
        'project': [row.project for row in contract_rows if row.project],
    }

    option_sets = {
        key: _merge_options(CSV_OPTION_DEFAULTS.get(key, []), db_values.get(key, []))
        for key in CSV_OPTION_DEFAULTS.keys()
    }
    option_sets['handling_department'] = _get_department_names()
    option_sets['project'] = _merge_options(_get_project_names() + [OPTION_FIELD_DEFAULTS['project']], db_values.get('project', []))
    return option_sets


def _normalize_option_fields(fields: dict) -> dict:
    option_sets = _get_contract_option_sets()
    normalized = dict(fields or {})

    normalized['handling_department'] = _match_option_value(
        normalized.get('handling_department', ''),
        option_sets.get('handling_department', []),
        '',
    )
    normalized['project'] = _match_option_value(
        normalized.get('project', ''),
        option_sets.get('project', []),
        OPTION_FIELD_DEFAULTS['project'],
    )
    normalized['approval_status'] = _match_option_value(
        normalized.get('approval_status', ''),
        option_sets.get('approval_status', []),
        OPTION_FIELD_DEFAULTS['approval_status'],
    )
    normalized['contract_determination_method'] = _match_option_value(
        normalized.get('contract_determination_method', ''),
        option_sets.get('contract_determination_method', []),
        OPTION_FIELD_DEFAULTS['contract_determination_method'],
    )
    normalized['contract_type'] = _match_option_value(
        normalized.get('contract_type', ''),
        option_sets.get('contract_type', []),
        '',
    )
    normalized['pricing_method'] = _match_option_value(
        normalized.get('pricing_method', ''),
        option_sets.get('pricing_method', []),
        '',
    )
    normalized['invoice_type'] = _match_option_value(
        normalized.get('invoice_type', ''),
        option_sets.get('invoice_type', []),
        '',
    )
    normalized['is_archived'] = _match_option_value(
        normalized.get('is_archived', ''),
        option_sets.get('is_archived', []),
        OPTION_FIELD_DEFAULTS['is_archived'],
    )
    return normalized


def _has_any_field_value(fields: dict) -> bool:
    if not isinstance(fields, dict):
        return False
    return any(str(fields.get(key, '')).strip() for key in CONTRACT_FIELD_KEYS)


def _minimax_extract_fields(pdf_text: str) -> dict:
    api_key = (current_app.config.get('MINIMAX_API_KEY') or '').strip()
    if not api_key:
        raise RuntimeError('MINIMAX_API_KEY 未配置')

    api_url = (current_app.config.get('MINIMAX_API_URL') or '').strip()
    model = (current_app.config.get('MINIMAX_MODEL') or '').strip()

    prompt = (
        '你是合同结构化抽取助手。请从给定PDF文本中抽取合同字段，只返回JSON对象，不要输出任何解释。\\n'
        'JSON键必须严格使用以下字段：'
        + ','.join(CONTRACT_FIELD_KEYS)
        + '\\n'
        '如果某字段不存在，请返回空字符串。handling_date 格式为 YYYY-MM-DD。contract_amount_wan 只保留数字。\\n'
        '以下是PDF文本：\\n'
        + pdf_text[:20000]
    )

    payload = {
        'model': model,
        'messages': [
            {
                'role': 'system',
                'content': '你是合同结构化抽取助手，只返回合法JSON对象，不输出解释。在抽取contract_unit时，指的是对方的公司，因此不能返回我方公司名称“' + (current_app.config.get('MY_COMP') or '') + '”及其常见变体。' + \
                    '项目project请尽量从标题或是其它文本中识别出项目相关信息，选取如下列表中意思能对应的标题或文本 ，必须返回如下的项目名称，否则请返回空""：'+ ','.join(_get_project_names()) + ',\n' + \
                    'handling_department必须返回如下的部门名称之一（如果能从标题或是其它文本中识别出部门相关信息的话），否则请返回空""：' + ','.join(_get_department_names()) + ',\n' + \
                    'contract_name 可能有多行请合并回车空格等字符，如果无法识别则返回空""。'
            },
            {
                'role': 'user',
                'content': prompt,
            },
        ],
        'temperature': 0.2,
        'max_tokens': 1024,
        'stream': False,
    }

    current_app.logger.info(
        'AI parse: Minimax request model=%s text_chars=%s prompt_chars=%s',
        model,
        len(pdf_text),
        len(prompt),
    )

    response = requests.post(
        api_url,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json=payload,
        timeout=60,
    )
    current_app.logger.info('AI parse: Minimax response status=%s', response.status_code)
    response.raise_for_status()

    response_payload = response.json()
    current_app.logger.info('AI parse: Minimax payload keys=%s', sorted(list(response_payload.keys())))
    base_resp = response_payload.get('base_resp')
    if isinstance(base_resp, dict):
        current_app.logger.info('AI parse: Minimax base_resp=%s', base_resp)
        status_code = base_resp.get('status_code')
        if status_code not in (0, None):
            raise RuntimeError(f"Minimax接口错误: {base_resp.get('status_msg') or status_code}")

    content = _extract_ai_content(response_payload)
    current_app.logger.info('AI parse: Minimax content chars=%s snippet=%s', len(content), (content or '')[:200])
    if not content.strip():
        raise RuntimeError('Minimax返回成功但无可用文本内容')

    parsed = _extract_json_object(content)
    current_app.logger.info('AI parse: Minimax parsed keys=%s', sorted(list(parsed.keys())) if isinstance(parsed, dict) else [])
    return _normalize_ai_fields(parsed, pdf_text)


@contracts_bp.get('/departments')
@require_auth
def list_departments():
    return jsonify(_get_department_names())


@contracts_bp.get('/settings/departments')
@require_auth
def list_department_settings():
    rows = Department.query.order_by(Department.name.asc()).all()
    return jsonify([row.to_dict() for row in rows])


@contracts_bp.get('/settings/projects')
@require_auth
def list_project_settings():
    rows = ProjectOption.query.order_by(ProjectOption.name.asc()).all()
    return jsonify([row.to_dict() for row in rows])


@contracts_bp.post('/settings/projects')
@require_auth
def create_project_setting():
    body = request.get_json(silent=True) or {}
    name = (body.get('name') or '').strip()

    if not name:
        return jsonify({'message': 'name is required'}), 400
    if len(name) > 255:
        return jsonify({'message': '项目名称最多255个字符'}), 400
    if ProjectOption.query.filter_by(name=name).first():
        return jsonify({'message': '项目已存在'}), 409

    row = ProjectOption(name=name)
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict()), 201


@contracts_bp.delete('/settings/projects/<int:project_id>')
@require_auth
def delete_project_setting(project_id):
    row = ProjectOption.query.get_or_404(project_id)

    in_use = Contract.query.filter(Contract.project == row.name).first()
    if in_use:
        return jsonify({'message': '该项目下已有合同，无法删除'}), 409

    db.session.delete(row)
    db.session.commit()
    return jsonify({'success': True})


@contracts_bp.get('/options/contract-fields')
@require_auth
def contract_field_options():
    contract_rows = Contract.query.all()

    db_values = {
        'approval_status': [row.approval_status for row in contract_rows if row.approval_status],
        'contract_determination_method': [row.contract_determination_method for row in contract_rows if row.contract_determination_method],
        'contract_type': [row.contract_type for row in contract_rows if row.contract_type],
        'invoice_type': [row.invoice_type for row in contract_rows if row.invoice_type],
        'pricing_method': [row.pricing_method for row in contract_rows if row.pricing_method],
        'is_archived': [row.is_archived for row in contract_rows if row.is_archived],
    }

    payload = {
        key: _merge_options(CSV_OPTION_DEFAULTS[key], db_values.get(key, []))
        for key in CSV_OPTION_DEFAULTS.keys()
    }
    payload['project'] = _merge_options(_get_project_names(), [row.project for row in contract_rows if row.project])
    return jsonify(payload)


@contracts_bp.post('/settings/departments')
@require_auth
def create_department_setting():
    body = request.get_json(silent=True) or {}
    name = (body.get('name') or '').strip()

    if not name:
        return jsonify({'message': 'name is required'}), 400
    if len(name) > 50:
        return jsonify({'message': '部门名称最多50个字符'}), 400
    if Department.query.filter_by(name=name).first():
        return jsonify({'message': '部门已存在'}), 409

    row = Department(name=name)
    db.session.add(row)
    db.session.commit()

    _department_dir(name)
    return jsonify(row.to_dict()), 201


@contracts_bp.delete('/settings/departments/<int:department_id>')
@require_auth
def delete_department_setting(department_id):
    row = Department.query.get_or_404(department_id)

    in_use = Contract.query.filter(Contract.department == row.name).first()
    if in_use:
        return jsonify({'message': '该部门下已有合同，无法删除'}), 409

    db.session.delete(row)
    db.session.commit()
    return jsonify({'success': True})


@contracts_bp.get('/contracts')
@require_auth
def list_contracts():
    department = (request.args.get('handling_department') or request.args.get('department') or '').strip()
    status = (request.args.get('approval_status') or request.args.get('status') or '').strip()

    query = Contract.query
    if department:
        query = query.filter(Contract.department == department)
    if status:
        query = query.filter(Contract.approval_status == status)

    rows = query.order_by(Contract.updated_at.desc()).all()
    return jsonify([row.to_dict() for row in rows])


@contracts_bp.post('/contracts')
@require_auth
def create_contract():
    body = request.get_json(silent=True) or {}

    required = ['contract_name', 'contract_amount_wan', 'handling_department']
    missing = [key for key in required if not str(body.get(key, '')).strip()]
    if missing:
        return jsonify({'message': f'Missing required fields: {", ".join(missing)}'}), 400

    amount = _safe_decimal(body.get('contract_amount_wan'))
    if amount is None:
        return jsonify({'message': 'contract_amount_wan is invalid'}), 400

    contract_number = (body.get('contract_number') or '').strip()
    if contract_number and Contract.query.filter_by(contract_number=contract_number).first():
        return jsonify({'message': 'contract_number already exists'}), 409

    department = body['handling_department'].strip()
    allowed_departments = _get_department_names()
    if department not in allowed_departments:
        return jsonify({'message': 'handling_department is not in configured department settings'}), 400
    _department_dir(department)

    project = (body.get('project') or '').strip() or None
    if project:
        allowed_projects = _get_project_names()
        if project not in allowed_projects:
            return jsonify({'message': 'project is not in configured project settings'}), 400

    record = Contract(
        contract_number=contract_number or None,
        contract_name=body['contract_name'].strip(),
        contract_unit=(body.get('contract_unit') or '').strip() or None,
        amount=amount,
        currency='CNY',
        approval_status=(body.get('approval_status') or '').strip() or None,
        handler=(body.get('handler') or '').strip() or None,
        department=department,
        contract_determination_method=(body.get('contract_determination_method') or '').strip() or None,
        handling_date=_parse_date(body.get('handling_date')),
        contract_type=(body.get('contract_type') or '').strip() or None,
        invoice_type=(body.get('invoice_type') or '').strip() or None,
        tax_rate=(body.get('tax_rate') or '').strip() or None,
        pricing_method=(body.get('pricing_method') or '').strip() or None,
        is_archived=(body.get('is_archived') or '').strip() or None,
        project=project,
        start_date=_parse_date(body.get('start_date')),
        end_date=_parse_date(body.get('end_date')),
        status=(body.get('approval_status') or '').strip() or (body.get('status') or 'active').strip() or 'active',
        created_by=g.current_user,
    )

    db.session.add(record)
    db.session.commit()
    return jsonify(record.to_dict()), 201


@contracts_bp.put('/contracts/<int:contract_id>')
@require_auth
def update_contract(contract_id):
    body = request.get_json(silent=True) or {}
    record = Contract.query.get_or_404(contract_id)

    if 'contract_number' in body:
        candidate = (body.get('contract_number') or '').strip()
        if candidate:
            duplicate = Contract.query.filter(
                Contract.contract_number == candidate,
                Contract.id != record.id,
            ).first()
            if duplicate:
                return jsonify({'message': 'contract_number already exists'}), 409
            record.contract_number = candidate
        else:
            record.contract_number = None
    if 'contract_name' in body:
        record.contract_name = (body.get('contract_name') or '').strip() or record.contract_name
    if 'contract_unit' in body:
        record.contract_unit = (body.get('contract_unit') or '').strip() or None
    if 'contract_amount_wan' in body:
        amount = _safe_decimal(body.get('contract_amount_wan'))
        if amount is None:
            return jsonify({'message': 'contract_amount_wan is invalid'}), 400
        record.amount = amount
    if 'approval_status' in body:
        record.approval_status = (body.get('approval_status') or '').strip() or None
        record.status = record.approval_status or record.status
    if 'handler' in body:
        record.handler = (body.get('handler') or '').strip() or None
    if 'handling_department' in body:
        department = (body.get('handling_department') or '').strip()
        if department:
            allowed_departments = _get_department_names()
            if department not in allowed_departments:
                return jsonify({'message': 'handling_department is not in configured department settings'}), 400
            _department_dir(department)
            record.department = department
    if 'contract_determination_method' in body:
        record.contract_determination_method = (body.get('contract_determination_method') or '').strip() or None
    if 'handling_date' in body:
        record.handling_date = _parse_date(body.get('handling_date'))
    if 'contract_type' in body:
        record.contract_type = (body.get('contract_type') or '').strip() or None
    if 'invoice_type' in body:
        record.invoice_type = (body.get('invoice_type') or '').strip() or None
    if 'tax_rate' in body:
        record.tax_rate = (body.get('tax_rate') or '').strip() or None
    if 'pricing_method' in body:
        record.pricing_method = (body.get('pricing_method') or '').strip() or None
    if 'is_archived' in body:
        record.is_archived = (body.get('is_archived') or '').strip() or None
    if 'project' in body:
        project = (body.get('project') or '').strip() or None
        if project:
            allowed_projects = _get_project_names()
            if project not in allowed_projects:
                return jsonify({'message': 'project is not in configured project settings'}), 400
        record.project = project
    if 'start_date' in body:
        record.start_date = _parse_date(body.get('start_date'))
    if 'end_date' in body:
        record.end_date = _parse_date(body.get('end_date'))
    if 'status' in body:
        record.status = (body.get('status') or '').strip() or record.status

    db.session.commit()
    return jsonify(record.to_dict())


@contracts_bp.post('/contracts/<int:contract_id>/upload')
@require_auth
def upload_contract_file(contract_id):
    record = Contract.query.get_or_404(contract_id)
    if 'file' not in request.files:
        return jsonify({'message': 'file is required'}), 400

    uploaded = request.files['file']
    if uploaded.filename == '':
        return jsonify({'message': 'empty filename'}), 400

    filename = _sanitize_upload_filename(uploaded.filename)

    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        remote_folder = _build_filestation_path(record.department)
        try:
            final_name = _synology_upload_file(remote_folder, filename, uploaded)
        except Exception as exc:
            return jsonify({'message': f'远程上传失败: {exc}'}), 500
    else:
        dept_dir = _department_dir(record.department)
        existing_names = [name for name in os.listdir(dept_dir) if os.path.isfile(os.path.join(dept_dir, name))]
        final_name = _next_available_filename(existing_names, filename)
        target_path = os.path.join(dept_dir, final_name)
        uploaded.save(target_path)

    record.file_path = _build_synology_file_path(record.department, final_name)
    db.session.commit()

    return jsonify({'file_path': record.file_path})


@contracts_bp.post('/contracts/ai-parse')
@require_auth
def parse_contract_pdf():
    if 'file' not in request.files:
        return jsonify({'message': 'file is required'}), 400

    uploaded = request.files['file']
    if uploaded.filename == '':
        return jsonify({'message': 'empty filename'}), 400

    current_app.logger.info(
        'AI parse: request user=%s filename=%s mimetype=%s content_length=%s',
        g.current_user,
        uploaded.filename,
        uploaded.mimetype,
        request.content_length,
    )

    filename = (uploaded.filename or '').lower()
    if not filename.endswith('.pdf'):
        return jsonify({'message': '仅支持上传PDF文件'}), 400

    try:
        pdf_text, preview_lines = _extract_pdf_text(uploaded)
    except Exception as exc:
        current_app.logger.exception('AI parse: PDF extraction failed')
        return jsonify({'message': f'PDF解析失败: {exc}'}), 400

    if not pdf_text:
        current_app.logger.warning('AI parse: no text extracted, preview_lines=%s', preview_lines)
        return jsonify({
            'message': 'PDF未解析到可用文本，请确认扫描件清晰度/方向或是否含可读文字',
            'ocr_preview_lines': preview_lines,
        }), 400

    try:
        raw_fields = _minimax_extract_fields(pdf_text)
    except Exception as exc:
        current_app.logger.exception('AI parse: Minimax extraction failed')
        return jsonify({'message': f'AI解析失败: {exc}'}), 500

    if not _has_any_field_value(raw_fields):
        current_app.logger.warning('AI parse: extracted fields are all empty')
        return jsonify({
            'message': 'AI返回结果为空，无法自动提取字段，请查看OCR预览并检查PDF清晰度',
            'ocr_preview_lines': preview_lines,
        }), 422

    fields = _normalize_option_fields(raw_fields)
    current_app.logger.info('AI parse: option-normalized fields=%s', fields)

    current_app.logger.info('AI parse: success extracted fields=%s', fields)

    return jsonify({'fields': fields})


@contracts_bp.get('/contracts/<int:contract_id>/download')
@require_auth
def download_contract_file(contract_id):
    record = Contract.query.get_or_404(contract_id)
    try:
        content, file_name, mime = _load_contract_file_payload(record)
    except PermissionError as exc:
        return jsonify({'message': str(exc)}), 401
    except ValueError:
        return jsonify({'message': 'file_path 非法'}), 400
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except Exception as exc:
        return jsonify({'message': f'文件下载失败: {exc}'}), 500

    return send_file(
        BytesIO(content),
        mimetype=mime,
        as_attachment=True,
        download_name=file_name,
    )


@contracts_bp.get('/contracts/<int:contract_id>/preview')
@require_auth
def preview_contract_file(contract_id):
    record = Contract.query.get_or_404(contract_id)
    normalized_file_path = _normalize_contract_file_path(record.file_path)
    if not normalized_file_path:
        return jsonify({'message': '该合同未上传文件'}), 404

    file_name = os.path.basename(normalized_file_path)
    if not file_name.lower().endswith('.pdf'):
        return jsonify({'message': '仅支持PDF预览'}), 400

    try:
        content, payload_name, _mime = _load_contract_file_payload(record)
    except PermissionError as exc:
        return jsonify({'message': str(exc)}), 401
    except ValueError:
        return jsonify({'message': 'file_path 非法'}), 400
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except Exception as exc:
        return jsonify({'message': f'文件预览失败: {exc}'}), 500

    final_name = payload_name or file_name or f'contract_{record.id}.pdf'
    return send_file(
        BytesIO(content),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=final_name,
    )
