import os
import posixpath
import hashlib
import re
import json
import mimetypes
import html as html_lib
import textwrap
from io import BytesIO
from urllib.parse import quote

import fitz
from PIL import Image, ImageDraw
from flask import Blueprint, current_app, g, jsonify, request, send_file, send_from_directory
from sqlalchemy import func, or_

from .auth import require_auth, decode_token
from .contracts_core import (
    _collect_storage_pdf_files,
    _build_synology_file_path,
    _coerce_unix_timestamp,
    _list_storage_entries,
    _normalize_relative_path,
    _next_available_filename,
    _remote_folder_path,
    _safe_local_folder_path,
    _sanitize_upload_filename,
    _storage_root_name,
    _synology_api_get,
    _synology_api_post,
    _synology_error_code,
    _synology_error_message,
    _synology_get_filestation_client_by_sid,
    _synology_json_array,
    _synology_upload_file,
)
from .files_core_helpers import (
    _build_contract_file_index,
    _build_folder_file_items,
    _clear_contract_file_path_by_relative_folder_path,
    _clear_contract_file_path_by_relative_path,
    _count_storage_files_recursive,
    _create_storage_folder,
    _delete_storage_file,
    _delete_storage_folder,
    _extract_match_key_from_filename,
    _list_folder_children_nodes,
    _load_storage_file_payload,
    _move_storage_file,
    _rename_storage_file,
    _replace_contract_file_path_by_relative_path,
    _select_best_contract_by_key,
    _synology_upload_login,
)
from .extensions import db
from .models import Contract, UserLog, UserPermission


files_bp = Blueprint('files', __name__, url_prefix='/api')

THUMB_WIDTH = 210
THUMB_HEIGHT = 290
LATEST_UPLOAD_LIMIT = 12
ROLE_SUPER_ADMIN = 'super_admin'
ROLE_SYNOLOGY_SUPER_ADMIN = 'synology_super_admin'
PERMISSION_ALL = '全部'
FILE_LOG_MODULE = '文件档案'
THUMB_KEY_PATTERN = re.compile(r'^[0-9a-f]{2}/[0-9a-f]{40}\.jpg$')
STORAGE_SOURCE_DEFAULT = 'storage'
STORAGE_SOURCE_SCAN = 'scan'


def _resolve_current_user_id() -> int | None:
    username = (getattr(g, 'current_user', '') or '').strip()
    if not username:
        return None

    row = UserPermission.query.filter_by(login_name=username).first()
    return row.id if row else None


def _write_file_operation_log(operation_type: str, operation_target: str, detail: str) -> None:
    try:
        db.session.add(UserLog(
            user_id=_resolve_current_user_id(),
            operation_module=FILE_LOG_MODULE,
            operation_target=str(operation_target or '-').strip() or '-',
            operation_type=str(operation_type or '').strip() or '操作',
            detail=str(detail or '').strip(),
        ))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning('file operation log write skipped: %s', exc)


class _InMemoryUpload:
    def __init__(self, content: bytes, mimetype: str):
        self.stream = BytesIO(content)
        self.mimetype = mimetype or 'application/octet-stream'


def _render_markdown_body_html(markdown_text: str) -> str:
    normalized_markdown = textwrap.dedent((markdown_text or '').replace('\r\n', '\n')).lstrip('\ufeff')

    # Prefer the standard markdown package for rich rendering.
    try:
        import markdown as markdown_lib  # type: ignore

        body_html = markdown_lib.markdown(
            normalized_markdown,
            extensions=['extra', 'tables', 'fenced_code'],
        )

        # OCR markdown can contain irregular leading indentation per line.
        # If it was parsed as one giant code block, strip left padding and parse again.
        if body_html.strip().startswith('<pre>') and '</pre>' in body_html:
            flattened_markdown = '\n'.join(line.lstrip() for line in normalized_markdown.split('\n'))
            retry_html = markdown_lib.markdown(
                flattened_markdown,
                extensions=['extra', 'tables', 'fenced_code'],
            )
            if not retry_html.strip().startswith('<pre>'):
                body_html = retry_html
    except Exception:
        escaped = html_lib.escape(normalized_markdown)
        body_html = f'<pre>{escaped}</pre>'

    return body_html


def _markdown_to_html_document(markdown_text: str, title: str) -> str:
    safe_title = html_lib.escape(title or 'Markdown Preview')
    body_html = _render_markdown_body_html(markdown_text)

    return f"""<!doctype html>
<html lang=\"zh-CN\">
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>{safe_title}</title>
        <style>
            :root {{
                color-scheme: light;
            }}
            body {{
                margin: 0;
                background: #f6f8fa;
                color: #24292f;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
                font-size: 16px;
            }}
            .page {{
                max-width: 1012px;
                margin: 24px auto;
                padding: 0 16px;
            }}
            .markdown-body {{
                box-sizing: border-box;
                background: #ffffff;
                border: 1px solid #d0d7de;
                border-radius: 10px;
                padding: 32px;
                line-height: 1.6;
                word-wrap: break-word;
            }}
            .markdown-body h1,
            .markdown-body h2,
            .markdown-body h3,
            .markdown-body h4,
            .markdown-body h5,
            .markdown-body h6 {{
                margin-top: 24px;
                margin-bottom: 16px;
                line-height: 1.25;
                font-weight: 600;
            }}
            .markdown-body h1,
            .markdown-body h2 {{
                border-bottom: 1px solid #d8dee4;
                padding-bottom: 0.3em;
            }}
            .markdown-body p,
            .markdown-body ul,
            .markdown-body ol,
            .markdown-body blockquote,
            .markdown-body table,
            .markdown-body pre {{
                margin-top: 0;
                margin-bottom: 16px;
            }}
            .markdown-body a {{
                color: #0969da;
                text-decoration: none;
            }}
            .markdown-body a:hover {{
                text-decoration: underline;
            }}
            .markdown-body code {{
                font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace;
                font-size: 85%;
                background: rgba(175, 184, 193, 0.2);
                border-radius: 6px;
                padding: 0.2em 0.4em;
            }}
            .markdown-body pre {{
                background: #f6f8fa;
                border-radius: 8px;
                padding: 16px;
                overflow: auto;
                line-height: 1.45;
            }}
            .markdown-body pre code {{
                background: transparent;
                padding: 0;
            }}
            .markdown-body blockquote {{
                margin-left: 0;
                padding: 0 1em;
                color: #57606a;
                border-left: 0.25em solid #d0d7de;
            }}
            .markdown-body table {{
                width: max-content;
                max-width: 100%;
                border-collapse: collapse;
            }}
            .markdown-body th,
            .markdown-body td {{
                border: 1px solid #d0d7de;
                padding: 6px 13px;
            }}
            .markdown-body tr:nth-child(2n) {{
                background: #f6f8fa;
            }}
            .markdown-body hr {{
                border: 0;
                height: 0.25em;
                padding: 0;
                margin: 24px 0;
                background: #d0d7de;
            }}
            @media (max-width: 768px) {{
                .markdown-body {{
                    padding: 16px;
                }}
            }}
        </style>
    </head>
    <body>
        <main class=\"page\">
            <article class=\"markdown-body\">{body_html}</article>
        </main>
    </body>
</html>
"""


def _markdown_to_split_preview_document(markdown_text: str, title: str, pdf_preview_url: str = '') -> str:
    safe_title = html_lib.escape(title or 'Markdown Preview')
    body_html = _render_markdown_body_html(markdown_text)
    safe_pdf_preview_url = html_lib.escape(pdf_preview_url or '')
    has_pdf_preview = bool(pdf_preview_url)
    markdown_json = json.dumps(markdown_text or '', ensure_ascii=False)
    preview_html = (
        f'<iframe class="pdf-frame" src="{safe_pdf_preview_url}" title="PDF预览"></iframe>'
        if has_pdf_preview else '<div class="pdf-placeholder">暂无可预览PDF</div>'
    )

    return f"""<!doctype html>
<html lang=\"zh-CN\">
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>{safe_title}</title>
        <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/@toast-ui/editor@3.2.2/dist/toastui-editor.min.css\" />
        <style>
            :root {{
                color-scheme: light;
            }}
            html,
            body {{
                margin: 0;
                width: 100%;
                height: 100%;
                background: #f6f8fa;
                color: #24292f;
                font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", \"Noto Sans\", Helvetica, Arial, sans-serif;
            }}
            .split-page {{
                width: 100%;
                height: 100vh;
                display: grid;
                grid-template-columns: 4fr 6fr;
                gap: 12px;
                padding: 12px;
                box-sizing: border-box;
            }}
            .left-pane,
            .right-pane {{
                min-width: 0;
                min-height: 0;
                border: 1px solid #d0d7de;
                border-radius: 10px;
                background: #ffffff;
                overflow: hidden;
            }}
            .left-pane {{
                display: flex;
                flex-direction: column;
            }}
            .right-pane {{
                display: flex;
                flex-direction: column;
            }}
            .pane-title {{
                padding: 10px 12px;
                border-bottom: 1px solid #e5e7eb;
                font-size: 13px;
                font-weight: 600;
                color: #374151;
                background: #f8fafc;
            }}
            .pdf-frame {{
                width: 100%;
                height: 100%;
                border: none;
                background: #ffffff;
                flex: 1;
            }}
            .pdf-placeholder {{
                height: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #6b7280;
                font-size: 13px;
                padding: 12px;
                box-sizing: border-box;
                flex: 1;
            }}
            .right-toolbar {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                padding: 10px 12px;
                border-bottom: 1px solid #e5e7eb;
                background: #f8fafc;
            }}
            .toolbar-group {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
            }}
            .toolbar-btn {{
                border: 1px solid #d1d5db;
                background: #ffffff;
                color: #1f2937;
                font-size: 13px;
                line-height: 1;
                border-radius: 8px;
                padding: 8px 12px;
                cursor: pointer;
            }}
            .toolbar-btn:hover {{
                border-color: #93c5fd;
                color: #1d4ed8;
            }}
            .toolbar-btn.is-primary {{
                border-color: #2563eb;
                color: #ffffff;
                background: #2563eb;
            }}
            .toolbar-btn:disabled {{
                opacity: 0.55;
                cursor: not-allowed;
            }}
            .toolbar-status {{
                color: #6b7280;
                font-size: 12px;
                white-space: nowrap;
            }}
            .markdown-view-wrap,
            .markdown-editor-wrap {{
                flex: 1;
                min-height: 0;
            }}
            .markdown-editor-wrap {{
                display: none;
                overflow: hidden;
                background: #ffffff;
            }}
            .markdown-editor-wrap.is-active {{
                display: block;
            }}
            .markdown-view-wrap.is-hidden {{
                display: none;
            }}
            .markdown-scroll {{
                width: 100%;
                height: 100%;
                overflow: auto;
                box-sizing: border-box;
                padding: 18px;
            }}
            #markdown-editor-host {{
                height: 100%;
            }}
            .toastui-editor-defaultUI {{
                border: none !important;
            }}
            .markdown-body {{
                box-sizing: border-box;
                line-height: 1.6;
                word-wrap: break-word;
            }}
            .markdown-body h1,
            .markdown-body h2,
            .markdown-body h3,
            .markdown-body h4,
            .markdown-body h5,
            .markdown-body h6 {{
                margin-top: 24px;
                margin-bottom: 16px;
                line-height: 1.25;
                font-weight: 600;
            }}
            .markdown-body h1,
            .markdown-body h2 {{
                border-bottom: 1px solid #d8dee4;
                padding-bottom: 0.3em;
            }}
            .markdown-body p,
            .markdown-body ul,
            .markdown-body ol,
            .markdown-body blockquote,
            .markdown-body table,
            .markdown-body pre {{
                margin-top: 0;
                margin-bottom: 16px;
            }}
            .markdown-body a {{
                color: #0969da;
                text-decoration: none;
            }}
            .markdown-body a:hover {{
                text-decoration: underline;
            }}
            .markdown-body code {{
                font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace;
                font-size: 85%;
                background: rgba(175, 184, 193, 0.2);
                border-radius: 6px;
                padding: 0.2em 0.4em;
            }}
            .markdown-body pre {{
                background: #f6f8fa;
                border-radius: 8px;
                padding: 16px;
                overflow: auto;
                line-height: 1.45;
            }}
            .markdown-body pre code {{
                background: transparent;
                padding: 0;
            }}
            .markdown-body blockquote {{
                margin-left: 0;
                padding: 0 1em;
                color: #57606a;
                border-left: 0.25em solid #d0d7de;
            }}
            .markdown-body table {{
                width: max-content;
                max-width: 100%;
                border-collapse: collapse;
            }}
            .markdown-body th,
            .markdown-body td {{
                border: 1px solid #d0d7de;
                padding: 6px 13px;
            }}
            .markdown-body tr:nth-child(2n) {{
                background: #f6f8fa;
            }}
            .markdown-body hr {{
                border: 0;
                height: 0.25em;
                padding: 0;
                margin: 24px 0;
                background: #d0d7de;
            }}
            @media (max-width: 1100px) {{
                .split-page {{
                    grid-template-columns: 1fr;
                    grid-template-rows: 48vh auto;
                }}
                .right-toolbar {{
                    flex-wrap: wrap;
                }}
            }}
        </style>
    </head>
    <body>
        <main class=\"split-page\">
            <section class=\"left-pane\">
                <div class=\"pane-title\">PDF预览</div>
                {preview_html}
            </section>
            <section class=\"right-pane\">
                <div class=\"right-toolbar\">
                    <div class=\"toolbar-group\">
                        <button id=\"btn-view\" class=\"toolbar-btn is-primary\" type=\"button\">查看</button>
                        <button id=\"btn-edit\" class=\"toolbar-btn\" type=\"button\">编辑</button>
                        <button id=\"btn-save\" class=\"toolbar-btn\" type=\"button\" disabled>保存</button>
                        <button id=\"btn-cancel\" class=\"toolbar-btn\" type=\"button\" disabled>取消</button>
                    </div>
                    <div id=\"editor-status\" class=\"toolbar-status\">查看模式</div>
                </div>
                <div id=\"markdown-view-wrap\" class=\"markdown-view-wrap\">
                    <div class=\"markdown-scroll\">
                        <article class=\"markdown-body\">{body_html}</article>
                    </div>
                </div>
                <div id=\"markdown-editor-wrap\" class=\"markdown-editor-wrap\">
                    <div id=\"markdown-editor-host\"></div>
                </div>
            </section>
        </main>
        <script src=\"https://cdn.jsdelivr.net/npm/@toast-ui/editor@3.2.2/dist/toastui-editor-all.min.js\"></script>
        <script>
            (() => {{
                const initialMarkdown = {markdown_json};
                const viewWrap = document.getElementById('markdown-view-wrap');
                const editorWrap = document.getElementById('markdown-editor-wrap');
                const statusEl = document.getElementById('editor-status');
                const btnView = document.getElementById('btn-view');
                const btnEdit = document.getElementById('btn-edit');
                const btnSave = document.getElementById('btn-save');
                const btnCancel = document.getElementById('btn-cancel');
                const saveUrl = window.location.pathname;
                const relativePath = window.location.pathname.split('/api/html/')[1] || '';
                const uploadUrl = `/api/html-upload-image/${{relativePath}}`;

                let editor = null;
                let editing = false;
                let currentMarkdown = initialMarkdown;

                const setStatus = (text) => {{
                    if (statusEl) {{
                        statusEl.textContent = text;
                    }}
                }};

                const toggleButtons = () => {{
                    btnView.classList.toggle('is-primary', !editing);
                    btnEdit.classList.toggle('is-primary', editing);
                    btnSave.disabled = !editing;
                    btnCancel.disabled = !editing;
                }};

                const enterEdit = () => {{
                    if (editing) {{
                        return;
                    }}
                    if (!window.toastui || !window.toastui.Editor) {{
                        setStatus('编辑器加载失败（CDN不可用）');
                        return;
                    }}

                    if (!editor) {{
                        editor = new window.toastui.Editor({{
                            el: document.getElementById('markdown-editor-host'),
                            height: '100%',
                            initialEditType: 'wysiwyg',
                            previewStyle: 'vertical',
                            initialValue: currentMarkdown,
                            usageStatistics: false,
                            toolbarItems: [
                                ['heading', 'bold', 'italic', 'strike'],
                                ['hr', 'quote'],
                                ['ul', 'ol', 'task', 'indent', 'outdent'],
                                ['table', 'image', 'link'],
                                ['code', 'codeblock'],
                            ],
                        }});

                        editor.removeHook('addImageBlobHook');
                        editor.addHook('addImageBlobHook', async (blob, callback) => {{
                            try {{
                                const fd = new FormData();
                                fd.append('image', blob, blob.name || 'pasted-image.png');

                                const resp = await fetch(uploadUrl, {{
                                    method: 'POST',
                                    body: fd,
                                    credentials: 'same-origin',
                                }});
                                const data = await resp.json();
                                if (!resp.ok || !data?.url) {{
                                    throw new Error(data?.message || '图片上传失败');
                                }}

                                callback(data.url, data.alt || 'image');
                                setStatus('图片已插入');
                            }} catch (err) {{
                                setStatus(err?.message || '图片上传失败');
                            }}
                        }});
                    }} else {{
                        editor.setMarkdown(currentMarkdown || '');
                    }}

                    editing = true;
                    viewWrap.classList.add('is-hidden');
                    editorWrap.classList.add('is-active');
                    toggleButtons();
                    setStatus('编辑模式：支持标题、表格、复制粘贴图片');
                }};

                const exitEdit = () => {{
                    if (!editing) {{
                        return;
                    }}
                    if (editor) {{
                        editor.setMarkdown(currentMarkdown || '');
                    }}
                    editing = false;
                    viewWrap.classList.remove('is-hidden');
                    editorWrap.classList.remove('is-active');
                    toggleButtons();
                    setStatus('查看模式');
                }};

                const saveMarkdown = async () => {{
                    if (!editing || !editor) {{
                        return;
                    }}

                    const nextMarkdown = editor.getMarkdown();
                    setStatus('保存中...');
                    try {{
                        const resp = await fetch(saveUrl, {{
                            method: 'PUT',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ markdown: nextMarkdown }}),
                            credentials: 'same-origin',
                        }});
                        const data = await resp.json();
                        if (!resp.ok) {{
                            throw new Error(data?.message || '保存失败');
                        }}

                        currentMarkdown = nextMarkdown;
                        setStatus('保存成功，正在刷新...');
                        window.location.reload();
                    }} catch (err) {{
                        setStatus(err?.message || '保存失败');
                    }}
                }};

                btnView?.addEventListener('click', exitEdit);
                btnEdit?.addEventListener('click', enterEdit);
                btnSave?.addEventListener('click', saveMarkdown);
                btnCancel?.addEventListener('click', exitEdit);

                toggleButtons();
            }})();
        </script>
    </body>
</html>
"""


def _find_origin_pdf_relative_path(ocr_root: str, md_relative_path: str) -> str:
    normalized = posixpath.normpath(str(md_relative_path or '').replace('\\', '/')).lstrip('/')
    if not normalized or normalized in {'.', '..'}:
        return ''
    if not normalized.lower().endswith('/full.md') and normalized.lower() != 'full.md':
        return ''

    md_abs_path = os.path.realpath(os.path.join(ocr_root, normalized))
    if not (md_abs_path == ocr_root or md_abs_path.startswith(ocr_root + os.sep)):
        return ''
    folder_abs = os.path.dirname(md_abs_path)
    if not os.path.isdir(folder_abs):
        return ''

    try:
        entries = sorted(os.listdir(folder_abs))
    except Exception:
        return ''

    strict_pattern = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}_origin\.pdf$')

    strict_matches = [
        name for name in entries
        if strict_pattern.fullmatch(name) and os.path.isfile(os.path.join(folder_abs, name))
    ]
    if strict_matches:
        selected = strict_matches[0]
    else:
        fallback_matches = [
            name for name in entries
            if name.lower().endswith('_origin.pdf') and os.path.isfile(os.path.join(folder_abs, name))
        ]
        if not fallback_matches:
            return ''
        selected = fallback_matches[0]

    relative_folder = posixpath.dirname(normalized)
    if relative_folder in {'', '.'}:
        return selected
    return posixpath.join(relative_folder, selected)


def _find_storage_pdf_relative_path_from_md(md_relative_path: str) -> str:
    normalized = posixpath.normpath(str(md_relative_path or '').replace('\\', '/')).lstrip('/')
    if not normalized or normalized in {'.', '..'}:
        return ''
    if not normalized.lower().endswith('/full.md') and normalized.lower() != 'full.md':
        return ''

    ocr_doc_dir = posixpath.dirname(normalized)
    if ocr_doc_dir in {'', '.'}:
        return ''

    file_stem = posixpath.basename(ocr_doc_dir).strip()
    parent_dir = posixpath.dirname(ocr_doc_dir)
    if not file_stem:
        return ''

    guessed_path = posixpath.join(parent_dir, f'{file_stem}.pdf') if parent_dir not in {'', '.'} else f'{file_stem}.pdf'
    guessed_path = _normalize_relative_path(guessed_path)
    if not guessed_path:
        return ''

    exact_contract = Contract.query.filter_by(file_path=guessed_path).first()
    if exact_contract and (exact_contract.file_path or '').strip():
        return _normalize_relative_path(exact_contract.file_path)

    lower_guess = guessed_path.lower()
    case_insensitive_contract = Contract.query.filter(
        Contract.file_path.isnot(None),
        func.lower(Contract.file_path) == lower_guess,
    ).first()
    if case_insensitive_contract and (case_insensitive_contract.file_path or '').strip():
        return _normalize_relative_path(case_insensitive_contract.file_path)

    return guessed_path


def _update_contract_fullbody_by_storage_path(storage_pdf_path: str, markdown_text: str) -> int:
    normalized_path = _normalize_relative_path(storage_pdf_path)
    normalized_fullbody = str(markdown_text or '').strip()
    if not normalized_path or not normalized_fullbody:
        return 0

    rows = Contract.query.filter(
        Contract.file_path.isnot(None),
        func.lower(Contract.file_path) == normalized_path.lower(),
    ).all()
    if not rows:
        return 0

    current_user = (getattr(g, 'current_user', '') or '').strip() or None
    for row in rows:
        row.fullbody = normalized_fullbody
        row.updated_by = current_user

    db.session.commit()
    return len(rows)


def _resolve_current_user_folder_scope() -> tuple[bool, set[str]]:
    username = (getattr(g, 'current_user', '') or '').strip()
    if not username:
        return False, set()

    row = UserPermission.query.filter_by(login_name=username).first()
    if not row:
        return False, set()

    if str(getattr(row, 'role', '') or '').strip() in {ROLE_SUPER_ADMIN, ROLE_SYNOLOGY_SUPER_ADMIN}:
        return True, set()

    aggregated = row.get_aggregated_permission()
    allowed_folders = {
        str(item).strip()
        for item in (aggregated.get('folders') or [])
        if item and item.strip()
    }
    if PERMISSION_ALL in allowed_folders:
        return True, set()

    return False, allowed_folders


def _thumbs_root_dir() -> str:
    backend_root = os.path.abspath(os.path.join(current_app.root_path, '..'))
    thumbs_root = os.path.join(backend_root, 'instance', 'thumbs')
    os.makedirs(thumbs_root, exist_ok=True)
    return thumbs_root


def _resolve_thumb_abs_path_from_key(raw_key: str) -> str:
    normalized = posixpath.normpath(str(raw_key or '').replace('\\', '/')).lstrip('/')
    if not normalized or normalized in {'.', '..'}:
        raise ValueError('thumbnail_key is required')
    if not THUMB_KEY_PATTERN.fullmatch(normalized):
        raise ValueError('thumbnail_key is invalid')

    abs_path = os.path.realpath(os.path.join(_thumbs_root_dir(), normalized))
    thumbs_root = os.path.realpath(_thumbs_root_dir())
    if not (abs_path == thumbs_root or abs_path.startswith(thumbs_root + os.sep)):
        raise ValueError('thumbnail_key is invalid')
    return abs_path


def _has_valid_request_auth() -> bool:
    token = ''

    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header.replace('Bearer ', '', 1).strip()

    if not token:
        token = (request.args.get('token') or '').strip()

    if not token:
        return False

    try:
        payload = decode_token(token)
    except Exception:
        return False

    username = (payload or {}).get('sub')
    if username:
        g.current_user = username
        return True

    return False


def _normalize_storage_source(source: str) -> str:
    normalized = str(source or '').strip().lower()
    if normalized == STORAGE_SOURCE_SCAN:
        return STORAGE_SOURCE_SCAN
    return STORAGE_SOURCE_DEFAULT


def _scan_remote_root() -> str:
    root = (current_app.config.get('SYNOLOGY_FILESTATION_SCAN') or '').replace('\\', '/').rstrip('/')
    if not root:
        raise ValueError('未配置 SYNOLOGY_FILESTATION_SCAN')
    return root


def _scan_local_root() -> str:
    root = os.path.abspath((current_app.config.get('SYNOLOGY_FILESTATION_SCAN') or '').strip())
    if not root:
        raise ValueError('未配置 SYNOLOGY_FILESTATION_SCAN')
    return root


def _source_root_name(source: str) -> str:
    normalized_source = _normalize_storage_source(source)
    if normalized_source == STORAGE_SOURCE_SCAN:
        if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
            root = _scan_remote_root()
        else:
            root = _scan_local_root().replace('\\', '/').rstrip('/')
        return os.path.basename(root) or root or '/'
    return _storage_root_name()


def _build_source_remote_path(source: str, *parts: str) -> str:
    normalized_source = _normalize_storage_source(source)
    if normalized_source == STORAGE_SOURCE_SCAN:
        root = _scan_remote_root()
        clean_parts = [str(part).strip('/').replace('\\', '/') for part in parts if str(part).strip('/')]
        if clean_parts:
            return f'{root}/{posixpath.join(*clean_parts)}'
        return root
    return _remote_folder_path(posixpath.join(*[str(part).strip('/').replace('\\', '/') for part in parts if str(part).strip('/')]))


def _safe_local_file_path_for_source(source: str, relative_path: str) -> str:
    normalized_source = _normalize_storage_source(source)
    if normalized_source != STORAGE_SOURCE_SCAN:
        raise ValueError('unsupported source')

    root = _scan_local_root()
    normalized = _normalize_relative_path(relative_path)
    resolved = os.path.abspath(os.path.join(root, normalized.replace('/', os.sep)))
    if os.path.commonpath([root, resolved]) != root:
        raise ValueError('invalid path')
    return resolved


def _list_remote_entries_for_source(source: str, relative_path: str, sid: str = ''):
    normalized_source = _normalize_storage_source(source)
    if normalized_source != STORAGE_SOURCE_SCAN:
        return _list_storage_entries(relative_path)

    resolved_sid = sid or _synology_upload_login()
    folder_path = _build_source_remote_path(normalized_source, relative_path)
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


def _load_file_payload_for_source(source: str, relative_file_path: str):
    normalized_source = _normalize_storage_source(source)
    normalized = _normalize_relative_path(relative_file_path)
    if not normalized:
        raise ValueError('file_path is required')

    if normalized_source != STORAGE_SOURCE_SCAN:
        return _load_storage_file_payload(normalized)

    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        sid = _synology_upload_login()
        client = _synology_get_filestation_client_by_sid(sid)
        remote_file_path = _build_source_remote_path(normalized_source, normalized)
        try:
            content_stream = client.get_file(
                path=remote_file_path,
                mode='serve',
                verify=bool(current_app.config.get('SYNOLOGY_VERIFY_SSL', False)),
            )
        except Exception as exc:
            from .contracts_core import _synology_sdk_error_payload
            payload = _synology_sdk_error_payload(exc)
            code = _synology_error_code(payload)
            if code in {404, 415}:
                raise FileNotFoundError('文件不存在或路径无效')
            raise RuntimeError(_synology_error_message(payload, 'filestation'))

        if content_stream is None:
            raise FileNotFoundError('文件不存在或路径无效')
        if isinstance(content_stream, str):
            raise RuntimeError(content_stream)

        file_name = os.path.basename(normalized) or 'download.bin'
        mime = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
        return content_stream.read(), file_name, mime

    local_file_path = _safe_local_file_path_for_source(normalized_source, normalized)
    if not os.path.isfile(local_file_path):
        raise FileNotFoundError('文件不存在或已被移动')

    file_name = os.path.basename(local_file_path)
    mime = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
    with open(local_file_path, 'rb') as f:
        return f.read(), file_name, mime


def _collect_pdf_files_for_source(source: str) -> list:
    normalized_source = _normalize_storage_source(source)
    if normalized_source != STORAGE_SOURCE_SCAN:
        return _collect_storage_pdf_files()

    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        sid = _synology_upload_login()
        stack = ['']
        result = []
        while stack:
            current_path = stack.pop()
            directories, files = _list_remote_entries_for_source(normalized_source, current_path, sid=sid)
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

    root = _scan_local_root()
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
                'modified_by': '-',
            })
    return result


def _import_scan_file_to_contract_storage(relative_file_path: str, target_folder_path: str) -> tuple[str, str]:
    normalized_source_path = _normalize_relative_path(relative_file_path)
    normalized_target_folder = _normalize_relative_path(target_folder_path)
    if not normalized_source_path:
        raise ValueError('file_path is required')
    if not normalized_target_folder:
        raise ValueError('target_folder_path is required')

    content, file_name, mime = _load_file_payload_for_source(STORAGE_SOURCE_SCAN, normalized_source_path)
    safe_name = _sanitize_upload_filename(file_name)

    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        remote_folder = _remote_folder_path(normalized_target_folder)
        upload = _InMemoryUpload(content, mime)
        resolved_name = _synology_upload_file(remote_folder, safe_name, upload)
        return _build_synology_file_path(normalized_target_folder, resolved_name), resolved_name

    target_dir = _safe_local_folder_path(normalized_target_folder)
    os.makedirs(target_dir, exist_ok=True)
    existing_names = [entry for entry in os.listdir(target_dir) if os.path.isfile(os.path.join(target_dir, entry))]
    resolved_name = _next_available_filename(existing_names, safe_name)
    target_abs_path = os.path.join(target_dir, resolved_name)
    with open(target_abs_path, 'wb') as f:
        f.write(content)
    return _build_synology_file_path(normalized_target_folder, resolved_name), resolved_name


def _delete_file_for_source(source: str, relative_file_path: str) -> str:
    normalized_source = _normalize_storage_source(source)
    normalized = _normalize_relative_path(relative_file_path)
    if not normalized:
        raise ValueError('file_path is required')

    if normalized_source != STORAGE_SOURCE_SCAN:
        return _delete_storage_file(normalized)

    if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
        remote_file_path = _build_source_remote_path(normalized_source, normalized)
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

    local_file_path = _safe_local_file_path_for_source(normalized_source, normalized)
    if not os.path.isfile(local_file_path):
        raise FileNotFoundError('文件不存在')

    os.remove(local_file_path)
    return normalized


def _build_thumb_rel_path(relative_file_path: str, mtime: int, source: str = STORAGE_SOURCE_DEFAULT) -> str:
    normalized = _normalize_relative_path(relative_file_path)
    normalized_source = _normalize_storage_source(source)
    key = hashlib.sha1(
        f'{normalized_source}|{normalized}|{int(mtime or 0)}|{THUMB_WIDTH}x{THUMB_HEIGHT}'.encode('utf-8')
    ).hexdigest()
    return os.path.join(key[:2], f'{key}.jpg')


def _render_pdf_thumbnail(content: bytes) -> Image.Image:
    with fitz.open(stream=content, filetype='pdf') as doc:
        if doc.page_count <= 0:
            raise ValueError('PDF empty')
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        source = Image.open(BytesIO(pix.tobytes('png'))).convert('RGB')

    canvas = Image.new('RGB', (THUMB_WIDTH, THUMB_HEIGHT), (240, 244, 252))
    source_ratio = source.width / max(source.height, 1)
    canvas_ratio = THUMB_WIDTH / THUMB_HEIGHT

    if source_ratio > canvas_ratio:
        resized_height = THUMB_HEIGHT
        resized_width = int(resized_height * source_ratio)
    else:
        resized_width = THUMB_WIDTH
        resized_height = int(resized_width / max(source_ratio, 1e-6))

    resized = source.resize((max(resized_width, 1), max(resized_height, 1)), Image.Resampling.LANCZOS)
    left = max((resized.width - THUMB_WIDTH) // 2, 0)
    top = max((resized.height - THUMB_HEIGHT) // 2, 0)
    crop = resized.crop((left, top, left + THUMB_WIDTH, top + THUMB_HEIGHT))
    canvas.paste(crop, (0, 0))
    return canvas


def _render_fallback_thumbnail(file_name: str) -> Image.Image:
    image = Image.new('RGB', (THUMB_WIDTH, THUMB_HEIGHT), (236, 242, 255))
    draw = ImageDraw.Draw(image)
    title = 'DOC'
    ext = os.path.splitext(file_name)[1].upper().replace('.', '')
    if ext:
        title = ext[:6]
    draw.rectangle((24, 20, THUMB_WIDTH - 24, THUMB_HEIGHT - 20), outline=(141, 171, 226), width=3)
    draw.text((36, 68), title, fill=(56, 92, 163))
    return image


def _ensure_thumbnail_file(relative_file_path: str, mtime: int, source: str = STORAGE_SOURCE_DEFAULT) -> tuple[str, str]:
    normalized = _normalize_relative_path(relative_file_path)
    if not normalized:
        raise ValueError('file_path is required')

    thumb_rel_path = _build_thumb_rel_path(normalized, mtime, source=source)
    thumb_abs_path = os.path.join(_thumbs_root_dir(), thumb_rel_path)

    if os.path.isfile(thumb_abs_path):
        return thumb_rel_path, thumb_abs_path

    os.makedirs(os.path.dirname(thumb_abs_path), exist_ok=True)

    content, file_name, _mime = _load_file_payload_for_source(source, normalized)
    if normalized.lower().endswith('.pdf'):
        thumbnail = _render_pdf_thumbnail(content)
    else:
        thumbnail = _render_fallback_thumbnail(file_name)

    thumbnail.save(thumb_abs_path, format='JPEG', quality=82, optimize=True)
    return thumb_rel_path, thumb_abs_path


def _safe_limit(value: str, default: int = LATEST_UPLOAD_LIMIT, minimum: int = 1, maximum: int = 5000) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


@files_bp.get('/folders/tree')
@require_auth
def get_folders_tree():
    try:
        root = {
            'name': _storage_root_name(),
            'path': '',
        }
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError:
        return jsonify({'message': '目录路径非法'}), 400
    except Exception as exc:
        return jsonify({'message': f'读取目录树失败: {exc}'}), 500

    return jsonify({
        'storage_mode': current_app.config.get('CONTRACT_STORAGE_MODE') or 'local',
        'root': root,
    })


@files_bp.get('/folders/children')
@require_auth
def list_folder_children():
    parent_path = request.args.get('parent_path') or request.args.get('path') or ''
    try:
        normalized = _normalize_relative_path(parent_path)
        children = _list_folder_children_nodes(normalized)
    except PermissionError as exc:
        return jsonify({'message': str(exc)}), 401
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError:
        return jsonify({'message': '目录路径非法'}), 400
    except Exception as exc:
        return jsonify({'message': f'读取子目录失败: {exc}'}), 500

    return jsonify({
        'parent_path': normalized,
        'children': children,
    })


@files_bp.get('/folders/files')
@require_auth
def list_folder_files():
    folder_path = request.args.get('folder_path') or request.args.get('folder') or ''
    try:
        normalized = _normalize_relative_path(folder_path)
        rows = _build_folder_file_items(normalized)
    except PermissionError as exc:
        return jsonify({'message': str(exc)}), 401
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError:
        return jsonify({'message': '目录路径非法'}), 400
    except Exception as exc:
        return jsonify({'message': f'读取目录文件失败: {exc}'}), 500

    return jsonify({
        'folder_path': normalized,
        'files': rows,
    })


@files_bp.get('/folders/file-count')
@require_auth
def count_folder_files_recursive():
    folder_path = request.args.get('folder_path') or request.args.get('folder') or ''
    try:
        normalized = _normalize_relative_path(folder_path)
        total = _count_storage_files_recursive(normalized)
    except PermissionError as exc:
        return jsonify({'message': str(exc)}), 401
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError:
        return jsonify({'message': '目录路径非法'}), 400
    except Exception as exc:
        return jsonify({'message': f'统计目录文件失败: {exc}'}), 500

    return jsonify({
        'folder_path': normalized,
        'total_files': total,
    })


@files_bp.post('/folders/batch-match')
@require_auth
def batch_match_folder_files():

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
            return None, None

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

        return None, None

    def _load_candidate_contracts(folder_value: str):
        query = Contract.query.filter(
            Contract.is_archived != '已归档',
            or_(Contract.file_path.is_(None), Contract.file_path == ''),
        )

        match_year1, match_year2 = _extract_path_year_range(folder_value)
        if match_year1 and match_year2:
            query = query.filter(
                or_(
                    Contract.contract_date_year.is_(None),
                    Contract.contract_date_year.between(match_year1, match_year2),
                )
            )

        folder_parts = [segment.strip() for segment in str(folder_value or '').split('/') if segment.strip()]
        match_dept = folder_parts[0] if folder_parts else None
        if match_dept:
            query = query.filter(Contract.department == match_dept)

        return query.all()

    body = request.get_json(silent=True) or {}
    folder_path = body.get('folder_path') or body.get('folder') or ''

    try:
        normalized = _normalize_relative_path(folder_path)
        _directories, files = _list_storage_entries(normalized)
    except PermissionError as exc:
        return jsonify({'message': str(exc)}), 401
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError:
        return jsonify({'message': '目录路径非法'}), 400
    except Exception as exc:
        return jsonify({'message': f'读取目录文件失败: {exc}'}), 500

    candidate_contracts = _load_candidate_contracts(normalized)
    contract_index = _build_contract_file_index()

    used_contract_ids = set()
    results = []
    success_count = 0

    for item in files:
        file_name = item.get('name') or ''
        file_path = item.get('path') or ''

        linked_contract = contract_index.get(file_path)
        if linked_contract:
            results.append({
                'name': file_name,
                'file_path': file_path,
                'status': 'skipped',
                'message': '文件已有关联合同，跳过',
                'matched_contract_id': linked_contract.id,
                'matched_contract_name': linked_contract.contract_name,
            })
            continue

        available_contracts = [row for row in candidate_contracts if row.id not in used_contract_ids]

        # 文件名中出现明确合同编号时优先按合同编号直连，避免名称模糊匹配误绑。
        contract_number_in_name = re.search(r'([A-Za-z0-9\-]{5,})', file_name)
        if contract_number_in_name:
            contract_number = contract_number_in_name.group(1)
            matched_contract = next(
                (row for row in available_contracts if (row.contract_number or '') == contract_number),
                None,
            )
            if matched_contract:
                matched_contract.file_path = file_path
                used_contract_ids.add(matched_contract.id)
                success_count += 1
                results.append({
                    'name': file_name,
                    'file_path': file_path,
                    'match_key': contract_number,
                    'status': 'success',
                    'message': '匹配成功（合同编号优先）',
                    'matched_contract_id': matched_contract.id,
                    'matched_contract_name': matched_contract.contract_name,
                    'match_method': '文件名包含合同编号',
                    'candidate_count': 1,
                })
                continue


        match_key = _extract_match_key_from_filename(file_name)

        if not match_key:
            results.append({
                'name': file_name,
                'file_path': file_path,
                'status': 'failed',
                'message': '文件名中未找到可用中文关键名称',
            })
            continue

        best_contract, match_method, matched_rows = _select_best_contract_by_key(match_key, available_contracts)

        if not best_contract:
            results.append({
                'name': file_name,
                'file_path': file_path,
                'match_key': match_key,
                'status': 'failed',
                'message': '未匹配到候选合同',
            })
            continue

        best_contract.file_path = file_path
        used_contract_ids.add(best_contract.id)
        success_count += 1
        results.append({
            'name': file_name,
            'file_path': file_path,
            'match_key': match_key,
            'status': 'success',
            'message': '匹配成功',
            'matched_contract_id': best_contract.id,
            'matched_contract_name': best_contract.contract_name,
            'match_method': match_method,
            'candidate_count': len(matched_rows),
        })

    db.session.commit()

    _write_file_operation_log(
        operation_type='更新',
        operation_target=normalized,
        detail=f'批量匹配文件：总数={len(files)}，成功={success_count}，失败={len(files) - success_count}',
    )

    return jsonify({
        'folder_path': normalized,
        'total': len(files),
        'success': success_count,
        'failed': len(files) - success_count,
        'results': results,
    })


@files_bp.post('/folders/upload')
@require_auth
def upload_folder_files():
    folder_path = request.form.get('folder_path') or request.form.get('folder') or ''
    try:
        normalized = _normalize_relative_path(folder_path)
    except ValueError:
        return jsonify({'message': '目录路径非法'}), 400

    uploads = request.files.getlist('files')
    if not uploads and 'file' in request.files:
        uploads = request.files.getlist('file')

    valid_uploads = [item for item in uploads if item and (item.filename or '').strip()]
    if not valid_uploads:
        return jsonify({'message': 'files is required'}), 400

    raw_relative_paths = request.form.getlist('relative_paths')
    relative_paths = [str(item or '') for item in raw_relative_paths]

    def _resolve_upload_target(index: int, uploaded_file):
        raw_relative = relative_paths[index] if index < len(relative_paths) else ''
        normalized_relative = _normalize_relative_path(raw_relative) if raw_relative else ''
        relative_dir = posixpath.dirname(normalized_relative) if normalized_relative else ''
        target_folder = _build_synology_file_path(normalized, relative_dir)
        filename_hint = posixpath.basename(normalized_relative) if normalized_relative else ''
        filename = _sanitize_upload_filename(filename_hint or uploaded_file.filename)
        return target_folder, filename

    def _ensure_storage_folder_exists(relative_folder_path: str, cache: set | None = None):
        normalized_folder = _normalize_relative_path(relative_folder_path)
        if not normalized_folder:
            return

        current = ''
        for segment in [part for part in normalized_folder.split('/') if part]:
            parent = current
            current = _build_synology_file_path(current, segment)
            if cache is not None and current in cache:
                continue
            try:
                _create_storage_folder(parent, segment)
            except FileExistsError:
                pass
            if cache is not None:
                cache.add(current)

    results = []
    try:
        if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
            for index, uploaded in enumerate(valid_uploads):
                target_folder, filename = _resolve_upload_target(index, uploaded)
                remote_folder = _remote_folder_path(target_folder)
                final_name = _synology_upload_file(remote_folder, filename, uploaded)
                results.append({
                    'name': final_name,
                    'file_path': _build_synology_file_path(target_folder, final_name),
                })
        else:
            base_folder = _safe_local_folder_path(normalized)
            if not os.path.isdir(base_folder):
                raise FileNotFoundError('目录不存在')

            created_dirs = set()
            existing_names_by_folder = {}
            for index, uploaded in enumerate(valid_uploads):
                target_folder, filename = _resolve_upload_target(index, uploaded)
                _ensure_storage_folder_exists(target_folder, cache=created_dirs)
                target_folder_abs = _safe_local_folder_path(target_folder)
                if not os.path.isdir(target_folder_abs):
                    raise FileNotFoundError('目录不存在')

                existing_names = existing_names_by_folder.get(target_folder)
                if existing_names is None:
                    existing_names = [
                        name for name in os.listdir(target_folder_abs)
                        if os.path.isfile(os.path.join(target_folder_abs, name))
                    ]
                    existing_names_by_folder[target_folder] = existing_names

                final_name = _next_available_filename(existing_names, filename)
                existing_names.append(final_name)
                target_path = os.path.join(target_folder_abs, final_name)
                uploaded.save(target_path)
                results.append({
                    'name': final_name,
                    'file_path': _build_synology_file_path(target_folder, final_name),
                })
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError:
        return jsonify({'message': '目录路径非法'}), 400
    except Exception as exc:
        return jsonify({'message': f'文件上传失败: {exc}'}), 500

    _write_file_operation_log(
        operation_type='新建',
        operation_target=normalized,
        detail=f'上传文件：目录={normalized or "/"}，上传数量={len(results)}',
    )

    return jsonify({
        'folder_path': normalized,
        'uploaded_count': len(results),
        'uploaded': results,
    })


@files_bp.post('/folders')
@require_auth
def create_folder():
    body = request.get_json(silent=True) or {}
    parent_path = body.get('parent_path') or body.get('parent') or ''
    name = body.get('name') or ''

    try:
        folder_path = _create_storage_folder(parent_path, name)
    except FileExistsError as exc:
        return jsonify({'message': str(exc)}), 409
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
    except Exception as exc:
        return jsonify({'message': f'新建文件夹失败: {exc}'}), 500

    _write_file_operation_log(
        operation_type='新建',
        operation_target=folder_path,
        detail=f'新建文件夹：父目录={_normalize_relative_path(parent_path) if parent_path else "/"}',
    )

    return jsonify({'path': folder_path}), 201


@files_bp.delete('/folders')
@require_auth
def delete_folder():
    body = request.get_json(silent=True) or {}
    folder_path = body.get('path') or request.args.get('path') or ''
    raw_force = (body.get('force') if isinstance(body, dict) else request.args.get('force')) or ''
    force_text = str(raw_force).strip().lower()
    force_delete = force_text in {'1', 'true', 'yes', 'y'}

    try:
        affected_ids = []
        if force_delete:
            affected_ids = _clear_contract_file_path_by_relative_folder_path(folder_path)
        _delete_storage_folder(folder_path, force=force_delete)
        if force_delete:
            db.session.commit()
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError as exc:
        db.session.rollback()
        return jsonify({'message': str(exc)}), 400
    except RuntimeError as exc:
        db.session.rollback()
        return jsonify({'message': str(exc)}), 409
    except Exception as exc:
        db.session.rollback()
        return jsonify({'message': f'删除文件夹失败: {exc}'}), 500

    _write_file_operation_log(
        operation_type='删除',
        operation_target=_normalize_relative_path(folder_path),
        detail=(
            f'删除文件夹：force={bool(force_delete)}，'
            f'受影响合同数={len(affected_ids) if force_delete else 0}'
        ),
    )

    return jsonify({
        'success': True,
        'force': bool(force_delete),
        'affected_contract_count': len(affected_ids) if force_delete else 0,
        'affected_contract_ids': affected_ids if force_delete else [],
    })


@files_bp.put('/folders')
@require_auth
def rename_folder():
    body = request.get_json(silent=True) or {}
    folder_path = body.get('path') or ''
    new_name = body.get('name') or ''

    if not folder_path:
        return jsonify({'message': 'path is required'}), 400
    if not new_name:
        return jsonify({'message': 'name is required'}), 400

    try:
        normalized_path = _normalize_relative_path(folder_path)
        if not normalized_path:
            return jsonify({'message': '不允许重命名根目录'}), 400

        name = (new_name or '').strip()
        if not name:
            return jsonify({'message': '文件夹名称不能为空'}), 400
        if '/' in name or '\\' in name:
            return jsonify({'message': '文件夹名称不能包含斜杠'}), 400

        parent_path = posixpath.dirname(normalized_path)
        if parent_path == '.':
            parent_path = ''

        new_relative_path = _build_synology_file_path(parent_path, name)

        if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
            sid = _synology_upload_login()
            old_remote_path = _remote_folder_path(normalized_path)

            payload = _synology_api_post(
                sid,
                {
                    'api': 'SYNO.FileStation.Rename',
                    'version': '2',
                    'method': 'rename',
                },
                data={
                    'path': f'["{old_remote_path}"]',
                    'name': _synology_json_array(name),
                },
            )
            if not payload.get('success'):
                code = _synology_error_code(payload)
                if code in {404, 415}:
                    return jsonify({'message': '目录不存在'}), 404
                raise RuntimeError(_synology_error_message(payload, 'filestation'))
        else:
            old_local_path = _safe_local_folder_path(normalized_path)
            if not os.path.isdir(old_local_path):
                return jsonify({'message': '目录不存在'}), 404

            new_local_path = _safe_local_folder_path(new_relative_path)
            if os.path.exists(new_local_path):
                return jsonify({'message': '文件夹已存在'}), 409

            os.rename(old_local_path, new_local_path)

    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
    except FileExistsError as exc:
        return jsonify({'message': str(exc)}), 409
    except Exception as exc:
        return jsonify({'message': f'重命名文件夹失败: {exc}'}), 500

    _write_file_operation_log(
        operation_type='更新',
        operation_target=new_relative_path,
        detail=f'重命名文件夹：{normalized_path} -> {new_relative_path}',
    )

    return jsonify({'path': new_relative_path})


@files_bp.delete('/folders/file')
@require_auth
def delete_folder_file():
    body = request.get_json(silent=True) or {}
    file_path = body.get('path') or request.args.get('path') or request.args.get('file_path') or ''

    try:
        normalized_path = _delete_storage_file(file_path)
        affected_ids = _clear_contract_file_path_by_relative_path(normalized_path)
        db.session.commit()
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({'message': str(exc)}), 409
    except Exception as exc:
        db.session.rollback()
        return jsonify({'message': f'删除文件失败: {exc}'}), 500

    _write_file_operation_log(
        operation_type='删除',
        operation_target=normalized_path,
        detail=f'删除文件：受影响合同数={len(affected_ids)}',
    )

    return jsonify({
        'success': True,
        'path': normalized_path,
        'affected_contract_count': len(affected_ids),
        'affected_contract_ids': affected_ids,
    })


@files_bp.put('/folders/file')
@require_auth
def rename_folder_file():
    body = request.get_json(silent=True) or {}
    file_path = body.get('path') or body.get('file_path') or ''
    new_name = body.get('name') or body.get('new_name') or ''

    try:
        old_path, new_path = _rename_storage_file(file_path, new_name)
        affected_ids = _replace_contract_file_path_by_relative_path(old_path, new_path)
        db.session.commit()
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
    except FileExistsError as exc:
        return jsonify({'message': str(exc)}), 409
    except RuntimeError as exc:
        return jsonify({'message': str(exc)}), 409
    except Exception as exc:
        db.session.rollback()
        return jsonify({'message': f'重命名文件失败: {exc}'}), 500

    _write_file_operation_log(
        operation_type='更新',
        operation_target=new_path,
        detail=f'重命名文件：{old_path} -> {new_path}，受影响合同数={len(affected_ids)}',
    )

    return jsonify({
        'success': True,
        'old_path': old_path,
        'path': new_path,
        'affected_contract_count': len(affected_ids),
        'affected_contract_ids': affected_ids,
    })


@files_bp.put('/folders/file/move')
@require_auth
def move_folder_file():
    body = request.get_json(silent=True) or {}
    file_path = body.get('path') or body.get('file_path') or ''
    target_folder_path = body.get('target_folder_path') or body.get('target_path') or ''

    try:
        old_path, new_path = _move_storage_file(file_path, target_folder_path)
        affected_ids = []
        if old_path != new_path:
            affected_ids = _replace_contract_file_path_by_relative_path(old_path, new_path)
        db.session.commit()
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
    except FileExistsError as exc:
        return jsonify({'message': str(exc)}), 409
    except RuntimeError as exc:
        return jsonify({'message': str(exc)}), 409
    except Exception as exc:
        db.session.rollback()
        return jsonify({'message': f'移动文件失败: {exc}'}), 500

    _write_file_operation_log(
        operation_type='更新',
        operation_target=new_path,
        detail=f'移动文件：{old_path} -> {new_path}，受影响合同数={len(affected_ids)}',
    )

    return jsonify({
        'success': True,
        'old_path': old_path,
        'path': new_path,
        'affected_contract_count': len(affected_ids),
        'affected_contract_ids': affected_ids,
    })


@files_bp.get('/folders/file-download')
@require_auth
def download_storage_file():
    file_path = request.args.get('path') or request.args.get('file_path') or ''
    try:
        content, file_name, mime = _load_storage_file_payload(file_path)
    except PermissionError as exc:
        return jsonify({'message': str(exc)}), 401
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
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


@files_bp.get('/folders/file-preview')
@require_auth
def preview_storage_file():
    source = _normalize_storage_source(request.args.get('source'))
    file_path = request.args.get('path') or request.args.get('file_path') or ''
    normalized = _normalize_relative_path(file_path)
    if not normalized.lower().endswith('.pdf'):
        return jsonify({'message': '仅支持PDF预览'}), 400

    try:
        content, file_name, _mime = _load_file_payload_for_source(source, normalized)
    except PermissionError as exc:
        return jsonify({'message': str(exc)}), 401
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except Exception as exc:
        return jsonify({'message': f'文件预览失败: {exc}'}), 500

    return send_file(
        BytesIO(content),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=file_name,
    )


@files_bp.get('/folders/latest-uploads')
@require_auth
def latest_uploaded_files():
    raw_limit = request.args.get('limit')
    limit = None if raw_limit in {None, ''} else _safe_limit(raw_limit)

    try:
        all_files = _collect_storage_pdf_files()
    except PermissionError as exc:
        return jsonify({'message': str(exc)}), 401
    except Exception as exc:
        return jsonify({'message': f'读取最新文件失败: {exc}'}), 500

    unrestricted, allowed_folders = _resolve_current_user_folder_scope()

    def _is_allowed_file_path(path: str) -> bool:
        if unrestricted:
            return True
        normalized = _normalize_relative_path(path)
        if not normalized or not allowed_folders:
            return False
        top_folder = normalized.split('/', 1)[0].strip()
        return bool(top_folder) and top_folder in allowed_folders

    sorted_files = sorted(
        [
            {
                'name': item.get('name') or '',
                'path': _normalize_relative_path(item.get('path') or ''),
                'mtime': _coerce_unix_timestamp(item.get('mtime')),
                'uploaded_at': _coerce_unix_timestamp(item.get('uploaded_at')) or _coerce_unix_timestamp(item.get('mtime')),
                'modified_by': (item.get('modified_by') or '').strip() or '-',
            }
            for item in all_files
            if (item.get('path') or '').strip() and _is_allowed_file_path(item.get('path') or '')
        ],
        key=lambda row: (row['uploaded_at'] or 0, row['name']),
        reverse=True,
    )

    latest = sorted_files if limit is None else sorted_files[:limit]
    payload = []
    contract_file_index = _build_contract_file_index()

    for item in latest:
        normalized_path = item['path']
        matched_contract = contract_file_index.get(normalized_path)

        try:
            thumb_rel_path, _thumb_abs = _ensure_thumbnail_file(normalized_path, item['mtime'], source=STORAGE_SOURCE_DEFAULT)
        except Exception:
            thumb_rel_path = ''

        payload.append({
            'name': item['name'],
            'file_path': normalized_path,
            'mtime': item['mtime'],
            'uploaded_at': item['uploaded_at'],
            'modified_by': item['modified_by'],
            'thumbnail_key': thumb_rel_path,
            'has_contract_binding': bool(matched_contract),
            'contract_id': matched_contract.id if matched_contract else None,
            'matched_contract_id': matched_contract.id if matched_contract else None,
        })

    return jsonify({'files': payload, 'total': len(payload)})


@files_bp.get('/folders/scan-files')
@require_auth
def scan_files():
    raw_limit = request.args.get('limit')
    limit = None if raw_limit in {None, ''} else _safe_limit(raw_limit)

    try:
        all_files = _collect_pdf_files_for_source(STORAGE_SOURCE_SCAN)
    except PermissionError as exc:
        return jsonify({'message': str(exc)}), 401
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
    except Exception as exc:
        return jsonify({'message': f'读取扫描文件失败: {exc}'}), 500

    sorted_files = sorted(
        [
            {
                'name': item.get('name') or '',
                'path': _normalize_relative_path(item.get('path') or ''),
                'mtime': _coerce_unix_timestamp(item.get('mtime')),
                'uploaded_at': _coerce_unix_timestamp(item.get('uploaded_at')) or _coerce_unix_timestamp(item.get('mtime')),
                'modified_by': (item.get('modified_by') or '').strip() or '-',
            }
            for item in all_files
            if (item.get('path') or '').strip()
        ],
        key=lambda row: (row['uploaded_at'] or 0, row['name']),
        reverse=True,
    )

    rows = sorted_files if limit is None else sorted_files[:limit]
    payload = []
    for item in rows:
        try:
            thumb_rel_path, _thumb_abs = _ensure_thumbnail_file(item['path'], item['mtime'], source=STORAGE_SOURCE_SCAN)
        except Exception:
            thumb_rel_path = ''

        payload.append({
            'name': item['name'],
            'file_path': item['path'],
            'mtime': item['mtime'],
            'uploaded_at': item['uploaded_at'],
            'modified_by': item['modified_by'],
            'thumbnail_key': thumb_rel_path,
            'source': STORAGE_SOURCE_SCAN,
        })

    return jsonify({
        'files': payload,
        'total': len(payload),
        'root_name': _source_root_name(STORAGE_SOURCE_SCAN),
    })


@files_bp.post('/folders/scan-import')
@require_auth
def import_scan_file():
    body = request.get_json(silent=True) or {}
    file_path = body.get('file_path') or body.get('path') or ''
    target_folder_path = body.get('target_folder_path') or body.get('folder_path') or ''

    try:
        imported_path, imported_name = _import_scan_file_to_contract_storage(file_path, target_folder_path)
    except PermissionError as exc:
        return jsonify({'message': str(exc)}), 401
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({'message': str(exc)}), 400
    except Exception as exc:
        return jsonify({'message': f'导入扫描文件失败: {exc}'}), 500

    _write_file_operation_log(
        operation_type='新建',
        operation_target=imported_path,
        detail=f'扫描文件导入：来源={_normalize_relative_path(file_path)}，目标目录={_normalize_relative_path(target_folder_path)}',
    )

    return jsonify({
        'file_path': imported_path,
        'name': imported_name,
    })


@files_bp.delete('/folders/scan-file')
@require_auth
def delete_scan_file():
    body = request.get_json(silent=True) or {}
    file_path = body.get('path') or body.get('file_path') or request.args.get('path') or request.args.get('file_path') or ''

    try:
        normalized_path = _delete_file_for_source(STORAGE_SOURCE_SCAN, file_path)
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({'message': str(exc)}), 409
    except Exception as exc:
        return jsonify({'message': f'删除扫描文件失败: {exc}'}), 500

    _write_file_operation_log(
        operation_type='删除',
        operation_target=normalized_path,
        detail='删除扫描目录文件',
    )

    return jsonify({
        'success': True,
        'path': normalized_path,
        'source': STORAGE_SOURCE_SCAN,
    })


@files_bp.get('/folders/file-thumbnail')
def get_file_thumbnail():
    source = _normalize_storage_source(request.args.get('source'))
    thumb_key = request.args.get('key') or request.args.get('thumbnail_key') or ''
    if thumb_key:
        try:
            thumb_abs_path = _resolve_thumb_abs_path_from_key(thumb_key)
            if not os.path.isfile(thumb_abs_path):
                return jsonify({'message': '缩略图不存在'}), 404
        except ValueError as exc:
            return jsonify({'message': str(exc)}), 400

        response = send_file(
            thumb_abs_path,
            mimetype='image/jpeg',
            as_attachment=False,
            max_age=31536000,
        )
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response

    if not _has_valid_request_auth():
        return jsonify({'message': 'Missing token'}), 401

    file_path = request.args.get('path') or request.args.get('file_path') or ''
    mtime = _safe_limit(request.args.get('mtime'), default=0, minimum=0, maximum=2_147_483_647)

    try:
        _thumb_rel_path, thumb_abs_path = _ensure_thumbnail_file(file_path, mtime, source=source)
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except Exception as exc:
        return jsonify({'message': f'缩略图生成失败: {exc}'}), 500

    response = send_file(
        thumb_abs_path,
        mimetype='image/jpeg',
        as_attachment=False,
        max_age=31536000,
    )
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


@files_bp.route('/html/', defaults={'relative_path': ''}, methods=['GET'])
@files_bp.route('/html/<path:relative_path>', methods=['GET', 'PUT'])
def serve_ocr_html_assets(relative_path):
    ocr_root = os.path.realpath(os.path.join(current_app.instance_path, 'ocr'))
    relative = posixpath.normpath(str(relative_path or '').replace('\\', '/')).lstrip('/')

    if relative in ('', '.'):
        index_abs = os.path.join(ocr_root, 'index.html')
        if os.path.isfile(index_abs):
            return send_from_directory(ocr_root, 'index.html', as_attachment=False)
        return jsonify({
            'message': 'OCR HTML root is available',
            'root': '/api/html/',
        })

    if relative == '..' or relative.startswith('../'):
        return jsonify({'message': '非法路径'}), 400

    target_abs = os.path.realpath(os.path.join(ocr_root, relative))
    if not (target_abs == ocr_root or target_abs.startswith(ocr_root + os.sep)):
        return jsonify({'message': '非法路径'}), 400

    if request.method == 'PUT':
        if not relative.lower().endswith('.md'):
            return jsonify({'message': '仅支持保存 Markdown 文件'}), 400

        body = request.get_json(silent=True) or {}
        markdown_text = body.get('markdown')
        if not isinstance(markdown_text, str):
            return jsonify({'message': 'markdown is required'}), 400

        try:
            with open(target_abs, 'w', encoding='utf-8') as fp:
                fp.write(markdown_text)
        except Exception as exc:
            return jsonify({'message': f'保存 Markdown 失败: {exc}'}), 500

        updated_rows = 0
        # When saving OCR full.md, also persist markdown into matching contract fullbody.
        if relative.lower().endswith('/full.md') or relative.lower() == 'full.md':
            storage_pdf_path = _find_storage_pdf_relative_path_from_md(relative)
            if storage_pdf_path:
                try:
                    updated_rows = _update_contract_fullbody_by_storage_path(storage_pdf_path, markdown_text)
                except Exception as exc:
                    db.session.rollback()
                    return jsonify({'message': f'保存 Markdown 成功，但更新合同全文失败: {exc}'}), 500

        _write_file_operation_log(
            operation_type='更新',
            operation_target=relative,
            detail=f'保存OCR Markdown：path={relative}，同步更新合同行数={int(updated_rows)}',
        )

        return jsonify({'success': True, 'path': relative, 'updated_contract_rows': int(updated_rows)})

    if os.path.isdir(target_abs):
        directory_index_abs = os.path.join(target_abs, 'index.html')
        if not os.path.isfile(directory_index_abs):
            return jsonify({'message': '目录下不存在 index.html'}), 404
        relative = posixpath.join(relative.rstrip('/'), 'index.html')

    if not os.path.exists(target_abs):
        return jsonify({'message': '文件不存在'}), 404

    return send_from_directory(ocr_root, relative, as_attachment=False)


@files_bp.get('/html-meta/<path:relative_path>')
def get_ocr_html_meta(relative_path):
    ocr_root = os.path.realpath(os.path.join(current_app.instance_path, 'ocr'))
    relative = posixpath.normpath(str(relative_path or '').replace('\\', '/')).lstrip('/')

    if not relative or relative in {'.', '..'}:
        return jsonify({'message': '非法路径'}), 400
    if not relative.lower().endswith('.md'):
        return jsonify({'message': '仅支持 Markdown 路径'}), 400

    md_abs = os.path.realpath(os.path.join(ocr_root, relative))
    if not (md_abs == ocr_root or md_abs.startswith(ocr_root + os.sep)):
        return jsonify({'message': '非法路径'}), 400
    markdown_exists = os.path.exists(md_abs)

    pdf_relative_path = _find_origin_pdf_relative_path(ocr_root, relative) if markdown_exists else ''
    pdf_preview_url = ''
    script_root = (request.script_root or '').rstrip('/')

    if pdf_relative_path:
        encoded_pdf_path = quote(pdf_relative_path, safe='/')
        pdf_preview_url = f'{script_root}/api/html/{encoded_pdf_path}'
    else:
        storage_pdf_path = _find_storage_pdf_relative_path_from_md(relative)
        if storage_pdf_path:
            encoded_storage_pdf_path = quote(storage_pdf_path, safe='/')
            pdf_preview_url = f'{script_root}/api/folders/file-preview?path={encoded_storage_pdf_path}'

    return jsonify({
        'path': relative,
        'markdown_exists': bool(markdown_exists),
        'pdf_preview_url': pdf_preview_url,
    })


@files_bp.post('/html-upload-image/<path:relative_path>')
def upload_ocr_markdown_image(relative_path):
    ocr_root = os.path.realpath(os.path.join(current_app.instance_path, 'ocr'))
    relative = posixpath.normpath(str(relative_path or '').replace('\\', '/')).lstrip('/')
    if not relative or relative in {'.', '..'}:
        return jsonify({'message': '非法路径'}), 400
    if not relative.lower().endswith('.md'):
        return jsonify({'message': '仅支持 Markdown 路径'}), 400

    md_abs = os.path.realpath(os.path.join(ocr_root, relative))
    if not (md_abs == ocr_root or md_abs.startswith(ocr_root + os.sep)):
        return jsonify({'message': '非法路径'}), 400
    if not os.path.exists(md_abs):
        return jsonify({'message': 'Markdown 文件不存在'}), 404

    uploaded = request.files.get('image') or request.files.get('file')
    if not uploaded or not (uploaded.filename or '').strip():
        return jsonify({'message': 'image is required'}), 400

    image_bytes = uploaded.read()
    if not image_bytes:
        return jsonify({'message': '图片内容为空'}), 400
    if len(image_bytes) > 20 * 1024 * 1024:
        return jsonify({'message': '图片大小不能超过20MB'}), 400

    source_name = _sanitize_upload_filename(uploaded.filename or 'pasted-image.png')
    ext = os.path.splitext(source_name)[1].lower()
    if ext not in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}:
        ext = '.png'

    digest = hashlib.sha1(image_bytes).hexdigest()[:12]
    file_name = f'img_{digest}{ext}'

    md_dir_abs = os.path.dirname(md_abs)
    images_abs = os.path.join(md_dir_abs, 'images')
    os.makedirs(images_abs, exist_ok=True)
    target_abs = os.path.join(images_abs, file_name)

    if not os.path.exists(target_abs):
        with open(target_abs, 'wb') as fp:
            fp.write(image_bytes)

    relative_dir = posixpath.dirname(relative)
    image_relative_path = posixpath.join(relative_dir, 'images', file_name) if relative_dir else posixpath.join('images', file_name)
    _write_file_operation_log(
        operation_type='新建',
        operation_target=image_relative_path,
        detail=f'上传OCR编辑图片：markdown={relative}，图片路径={image_relative_path}',
    )
    image_url = f"/api/html/{quote(image_relative_path, safe='/')}"
    return jsonify({'url': image_url, 'alt': os.path.splitext(file_name)[0]})
