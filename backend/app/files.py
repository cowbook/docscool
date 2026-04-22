import os
import posixpath
from io import BytesIO

from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy import or_

from .auth import require_auth
from .contracts import (
    _build_contract_file_index,
    _build_folder_file_items,
    _build_synology_file_path,
    _clear_contract_file_path_by_relative_path,
    _count_storage_files_recursive,
    _create_storage_folder,
    _delete_storage_file,
    _delete_storage_folder,
    _extract_match_key_from_filename,
    _list_folder_children_nodes,
    _list_storage_entries,
    _load_storage_file_payload,
    _normalize_relative_path,
    _remote_folder_path,
    _rename_storage_file,
    _replace_contract_file_path_by_relative_path,
    _safe_local_folder_path,
    _sanitize_upload_filename,
    _select_best_contract_by_key,
    _storage_root_name,
    _synology_api_post,
    _synology_error_code,
    _synology_error_message,
    _synology_json_array,
    _synology_upload_file,
    _synology_upload_login,
    _next_available_filename,
)
from .extensions import db
from .models import Contract


files_bp = Blueprint('files', __name__, url_prefix='/api')


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
    body = request.get_json(silent=True) or {}
    folder_path = body.get('folder_path') or body.get('folder') or ''

    try:
        normalized = _normalize_relative_path(folder_path)
        _directories, files = _list_storage_entries(normalized)
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError:
        return jsonify({'message': '目录路径非法'}), 400
    except Exception as exc:
        return jsonify({'message': f'读取目录文件失败: {exc}'}), 500

    candidate_contracts = Contract.query.filter(
        Contract.is_archived != '已归档',
        or_(Contract.file_path.is_(None), Contract.file_path == ''),
    ).all()
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

        match_key = _extract_match_key_from_filename(file_name)

        if not match_key:
            results.append({
                'name': file_name,
                'file_path': file_path,
                'status': 'failed',
                'message': '文件名中未找到可用中文关键名称',
            })
            continue

        available_contracts = [row for row in candidate_contracts if row.id not in used_contract_ids]
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

    results = []
    try:
        if current_app.config.get('CONTRACT_STORAGE_MODE') == 'remote':
            remote_folder = _remote_folder_path(normalized)
            for uploaded in valid_uploads:
                filename = _sanitize_upload_filename(uploaded.filename)
                final_name = _synology_upload_file(remote_folder, filename, uploaded)
                results.append({
                    'name': final_name,
                    'file_path': _build_synology_file_path(normalized, final_name),
                })
        else:
            target_folder = _safe_local_folder_path(normalized)
            if not os.path.isdir(target_folder):
                raise FileNotFoundError('目录不存在')

            existing_names = [
                name for name in os.listdir(target_folder)
                if os.path.isfile(os.path.join(target_folder, name))
            ]
            for uploaded in valid_uploads:
                filename = _sanitize_upload_filename(uploaded.filename)
                final_name = _next_available_filename(existing_names, filename)
                existing_names.append(final_name)
                target_path = os.path.join(target_folder, final_name)
                uploaded.save(target_path)
                results.append({
                    'name': final_name,
                    'file_path': _build_synology_file_path(normalized, final_name),
                })
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError:
        return jsonify({'message': '目录路径非法'}), 400
    except Exception as exc:
        return jsonify({'message': f'文件上传失败: {exc}'}), 500

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

    return jsonify({'path': folder_path}), 201


@files_bp.delete('/folders')
@require_auth
def delete_folder():
    body = request.get_json(silent=True) or {}
    folder_path = body.get('path') or request.args.get('path') or ''

    try:
        _delete_storage_folder(folder_path)
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({'message': str(exc)}), 409
    except Exception as exc:
        return jsonify({'message': f'删除文件夹失败: {exc}'}), 500

    return jsonify({'success': True})


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
    file_path = request.args.get('path') or request.args.get('file_path') or ''
    normalized = _normalize_relative_path(file_path)
    if not normalized.lower().endswith('.pdf'):
        return jsonify({'message': '仅支持PDF预览'}), 400

    try:
        content, file_name, _mime = _load_storage_file_payload(normalized)
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
