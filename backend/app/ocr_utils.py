import base64
import hmac
import json
import re
import time
import zipfile
import requests
import numpy as np
from urllib.parse import urlparse, unquote
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pypdf import PdfReader
from rapidocr_onnxruntime import RapidOCR

def _preview_lines(text: str, limit: int = 6):
    lines = [line.strip() for line in (text or '').splitlines() if line.strip()]
    return lines[:limit]
from flask import current_app
from io import BytesIO
import os

def get_ocr_engine():
    global _OCR_ENGINE
    if '_OCR_ENGINE' not in globals():
        globals()['_OCR_ENGINE'] = RapidOCR()
    return globals()['_OCR_ENGINE']

def extract_pdf_text_via_ocr(pdf_bytes: bytes) -> str:
    import fitz
    from PIL import Image
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    ocr = get_ocr_engine()
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

def extract_ai_content_from_pdf(uploaded_file) -> tuple[str, list[str]]:
    app_id = (current_app.config.get('XUNFEI_APP_ID') or '').strip()
    api_secret = (current_app.config.get('XUNFEI_API_SECRET') or '').strip()
    api_key = (current_app.config.get('XUNFEI_API_KEY') or '').strip()
    api_url = (current_app.config.get('XUNFEI_API_URL') or '').strip()
    if not app_id or not api_secret or not api_key or not api_url:
        raise RuntimeError('讯飞OCR配置不完整，请检查 XUNFEI_APP_ID/XUNFEI_API_KEY/XUNFEI_API_SECRET/XUNFEI_API_URL')
    try:
        uploaded_file.stream.seek(0)
    except Exception:
        pass
    pdf_bytes = uploaded_file.stream.read()
    if not pdf_bytes:
        return '', []
    parsed = urlparse(api_url)
    host = parsed.netloc
    path = parsed.path or '/v1/private/hh_ocr_recognize_doc'
    endpoint = f'{parsed.scheme}://{host}{path}'
    def _build_signed_params():
        date_str = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        request_line = f'POST {path} HTTP/1.1'
        signature_origin = f'host: {host}\ndate: {date_str}\n{request_line}'
        signature_sha = hmac.new(
            api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod='sha256',
        ).digest()
        signature = base64.b64encode(signature_sha).decode('utf-8')
        authorization_origin = (
            f'api_key="{api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        return {
            'host': host,
            'date': date_str,
            'authorization': authorization,
        }
    def _recognize_image(image_bytes: bytes, image_encoding: str = 'png') -> str:
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        payload = {
            'header': {
                'app_id': app_id,
                'status': 3,
            },
            'parameter': {
                'hh_ocr_recognize_doc': {
                    'recognizeDocumentRes': {
                        'encoding': 'utf8',
                        'compress': 'raw',
                        'format': 'json',
                    }
                }
            },
            'payload': {
                'image': {
                    'encoding': image_encoding,
                    'image': image_base64,
                    'status': 3,
                }
            },
        }
        response = requests.post(
            endpoint,
            params=_build_signed_params(),
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        code = ((data.get('header') or {}).get('code'))
        if code != 0:
            message = (data.get('header') or {}).get('message') or '讯飞OCR接口返回失败'
            raise RuntimeError(f'{message}(code={code})')
        text_base64 = (((data.get('payload') or {}).get('recognizeDocumentRes') or {}).get('text') or '')
        if not text_base64:
            return ''
        decoded_json = base64.b64decode(text_base64).decode('utf-8', errors='ignore')
        parsed_text = json.loads(decoded_json) if decoded_json else {}
        whole_text = str(parsed_text.get('whole_text') or '').strip()
        if whole_text:
            return whole_text
        lines = parsed_text.get('lines') or []
        return '\n'.join(str(item.get('text') or '').strip() for item in lines if str(item.get('text') or '').strip())
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    page_texts = []
    max_pages = min(len(doc), 20)
    current_app.logger.info('AI parse: Xunfei OCR enabled, pages=%s (max=%s)', len(doc), max_pages)
    for i in range(max_pages):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image_bytes = pix.tobytes('png')
        text = _recognize_image(image_bytes, image_encoding='png')
        if text:
            page_texts.append(text)
            current_app.logger.info('AI parse: Xunfei OCR page=%s chars=%s', i + 1, len(text))
    final_text = '\n'.join(item for item in page_texts if item).strip()
    return final_text, _preview_lines(final_text)

def extract_pdf_text(uploaded_file):
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
    try:
        xunfei_text, xunfei_preview = extract_ai_content_from_pdf(uploaded_file)
        if xunfei_text:
            return xunfei_text, xunfei_preview
    except Exception as exc:
        current_app.logger.warning('AI parse: Xunfei OCR failed, fallback local OCR: %s', exc)
    ocr_text = extract_pdf_text_via_ocr(pdf_bytes)
    return ocr_text, _preview_lines(ocr_text)

def mineru_auth_headers() -> dict:
    api_key = (current_app.config.get('MINERU_API_KEY') or '').strip()
    if not api_key:
        raise RuntimeError('MINERU_API_KEY 未配置')
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }

def mineru_extract_text_from_uploaded_pdf(uploaded_file) -> tuple[str, list[str]]:
    filename = (uploaded_file.filename or '').strip()
    if not filename:
        raise RuntimeError('empty filename')
    if not filename.lower().endswith('.pdf'):
        raise RuntimeError('仅支持上传PDF文件')
    try:
        uploaded_file.stream.seek(0)
    except Exception:
        pass
    file_bytes = uploaded_file.stream.read()
    if not file_bytes:
        raise RuntimeError('PDF文件内容为空')
    headers = mineru_auth_headers()
    create_resp = requests.post(
        'https://mineru.net/api/v4/file-urls/batch',
        headers=headers,
        json={
            'files': [
                {
                    'name': filename,
                    'is_ocr': True,
                }
            ],
            'model_version': 'vlm',
            'language': 'ch',
            'enable_table': True,
            'enable_formula': True,
        },
        timeout=30,
    )
    create_resp.raise_for_status()
    create_payload = create_resp.json()
    if create_payload.get('code') != 0:
        raise RuntimeError(f"MinerU创建任务失败: {create_payload.get('msg') or '未知错误'}")
    data = create_payload.get('data') or {}
    batch_id = data.get('batch_id')
    file_urls = data.get('file_urls') or []
    if not batch_id or not file_urls:
        raise RuntimeError('MinerU返回任务信息不完整')
    upload_resp = requests.put(
        file_urls[0],
        data=file_bytes,
        timeout=30,
    )
    if upload_resp.status_code not in (200, 201):
        raise RuntimeError(f'MinerU文件上传失败: HTTP {upload_resp.status_code}')
    timeout_seconds = 300
    poll_interval = 2
    deadline = time.time() + timeout_seconds
    last_state = ''
    last_msg = ''
    full_zip_url = ''
    while time.time() < deadline:
        result_resp = requests.get(
            f'https://mineru.net/api/v4/extract-results/batch/{batch_id}',
            headers=headers,
            timeout=30,
        )
        result_resp.raise_for_status()
        result_payload = result_resp.json()
        if result_payload.get('code') != 0:
            raise RuntimeError(f"MinerU查询任务失败: {result_payload.get('msg') or '未知错误'}")
        extract_results = (result_payload.get('data') or {}).get('extract_result') or []
        item = extract_results[0] if extract_results else {}
        state = (item.get('state') or '').strip().lower()
        last_state = state or last_state
        last_msg = item.get('err_msg') or result_payload.get('msg') or ''
        if state == 'done':
            full_zip_url = (item.get('full_zip_url') or '').strip()
            break
        if state == 'failed':
            raise RuntimeError(item.get('err_msg') or 'MinerU OCR任务失败')
        time.sleep(poll_interval)
    if not full_zip_url:
        raise RuntimeError(f'MinerU OCR任务超时或未完成，state={last_state or "unknown"}，message={last_msg or ""}')
    zip_resp = requests.get(full_zip_url, timeout=30)
    zip_resp.raise_for_status()
    zip_bytes = zip_resp.content
    if not zip_bytes:
        raise RuntimeError('MinerU OCR结果为空')
    full_text = ''
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        import hashlib
        ocr_root = os.path.join(current_app.root_path, '..', 'instance', 'ocr')
        os.makedirs(ocr_root, exist_ok=True)
        zip_dir_name = ''
        if full_zip_url:
            base = os.path.basename(full_zip_url)
            if base.lower().endswith('.zip'):
                base = base[:-4]
            zip_dir_name = base
        if not zip_dir_name:
            zip_dir_name = hashlib.md5((full_zip_url or str(time.time())).encode('utf-8')).hexdigest()
        extract_dir = os.path.join(ocr_root, zip_dir_name)
        os.makedirs(extract_dir, exist_ok=True)
        for name in zf.namelist():
            target_path = os.path.join(extract_dir, name)
            if not os.path.abspath(target_path).startswith(os.path.abspath(extract_dir)):
                continue
            if name.endswith('/'):
                os.makedirs(target_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zf.open(name) as src, open(target_path, 'wb') as dst:
                    dst.write(src.read())
        for name in zf.namelist():
            if name.lower().endswith('full.md'):
                with zf.open(name) as f:
                    full_text = f.read().decode('utf-8', errors='ignore').strip()
                break
        if not full_text:
            md_candidates = [name for name in zf.namelist() if name.lower().endswith('.md')]
            if md_candidates:
                with zf.open(md_candidates[0]) as f:
                    full_text = f.read().decode('utf-8', errors='ignore').strip()
    return full_text, _preview_lines(full_text)
