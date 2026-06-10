import os
import re
from io import BytesIO
from decimal import Decimal

from flask import current_app, g, jsonify, request, send_file
from sqlalchemy import String, cast, func, or_
from werkzeug.datastructures import FileStorage

from .auth import require_auth
from .contracts import contracts_bp
from .ocr_utils import extract_pdf_text, mineru_extract_text_from_uploaded_pdf
from .contracts_core import (
    CONTRACT_FIELD_KEYS,
    EXCEL_ALLOWED_EXTENSIONS,
    _department_dir,
    _build_filestation_path,
    _build_synology_file_path,
    _collect_storage_files,
    _collect_storage_pdf_files,
    _delete_contract_file,
    _find_ai_match_candidates,
    _format_decimal_plain,
    _get_contract_option_sets,
    _get_department_names,
    _get_project_names,
    _has_any_field_value,
    _load_contract_file_payload,
    _minimax_extract_fields,
    _next_available_filename,
    _normalize_contract_file_path,
    _normalize_option_fields,
    _normalize_contract_type_value,
    _normalize_relative_path,
    _parse_date,
    _preview_lines,
    _safe_decimal,
    _get_stamp_tax_rate_by_contract_type,
    _sanitize_upload_filename,
    _select_best_pdf_match,
    _synology_upload_file,
)
from .contracts_routes_contracts_helpers import (
    _IMPORT_ERROR_REPORTS,
    _build_contract_import_template,
    _build_contract_record,
    _build_import_payload_from_row,
    _detect_excel_header,
    _is_excel_row_empty,
    _load_excel_sheets,
    _store_import_error_report,
    _stringify_excel_value,
)
from .files_core_helpers import _load_storage_file_payload
from .extensions import db
from .models import Contract, UserPermission


ROLE_SUPER_ADMIN = 'super_admin'
PERMISSION_ALL = '全部'


def _resolve_current_user_department_scope() -> tuple[bool, list[str]]:
    username = (getattr(g, 'current_user', '') or '').strip()
    if not username:
        return True, []

    permission_row = UserPermission.query.filter_by(login_name=username).first()
    if not permission_row:
        return True, []

    if str(getattr(permission_row, 'role', '') or '').strip() == ROLE_SUPER_ADMIN:
        return True, []

    aggregated = permission_row.get_aggregated_permission()
    departments = [
        item.strip()
        for item in (aggregated.get('departments') or [])
        if item and str(item).strip()
    ]

    if PERMISSION_ALL in departments:
        return True, []

    return False, departments

@contracts_bp.get('/contracts')
@require_auth
def list_contracts():
    department = (request.args.get('handling_department') or request.args.get('department') or '').strip()
    project = (request.args.get('project') or '').strip()
    status = (request.args.get('status') or '').strip()
    keyword = (request.args.get('keyword') or request.args.get('search') or '').strip()
    has_file = (request.args.get('has_file') or '').strip().lower()
    is_archived = (request.args.get('is_archived') or '').strip()

    query = Contract.query
    unrestricted, allowed_departments = _resolve_current_user_department_scope()
    if not unrestricted:
        if not allowed_departments:
            return jsonify([])
        query = query.filter(Contract.department.in_(allowed_departments))

    if department == '__empty__':
        query = query.filter(Contract.department.is_(None))
    elif department:
        query = query.filter(Contract.department == department)
    if project == '__empty__':
        query = query.filter(Contract.project.is_(None))
    elif project:
        query = query.filter(Contract.project == project)
    if status:
        query = query.filter(Contract.status == status)
    if has_file == 'true':
        query = query.filter(Contract.file_path.isnot(None))
    elif has_file == 'false':
        query = query.filter(or_(Contract.file_path.is_(None), Contract.file_path == ''))
    if is_archived:
        query = query.filter(Contract.is_archived == is_archived)
    if keyword:
        pattern = f'%{keyword}%'
        query = query.filter(or_(
            Contract.contract_number.ilike(pattern),
            Contract.contract_name.ilike(pattern),
            Contract.contract_unit.ilike(pattern),
            Contract.currency.ilike(pattern),
            Contract.handler.ilike(pattern),
            Contract.department.ilike(pattern),
            Contract.contract_determination_method.ilike(pattern),
            Contract.contract_type.ilike(pattern),
            Contract.purchase_type.ilike(pattern),
            Contract.stamp_tax_rate.ilike(pattern),
            Contract.pricing_method.ilike(pattern),
            Contract.save_place.ilike(pattern),
            Contract.is_archived.ilike(pattern),
            Contract.project.ilike(pattern),
            Contract.status.ilike(pattern),
            Contract.file_path.ilike(pattern),
            Contract.fullbody.ilike(pattern),
            Contract.created_by.ilike(pattern),
            Contract.updated_by.ilike(pattern),
            cast(Contract.amount, String).ilike(pattern),
            cast(Contract.copy_count, String).ilike(pattern),
            cast(Contract.handling_date, String).ilike(pattern),
            cast(Contract.start_date, String).ilike(pattern),
            cast(Contract.end_date, String).ilike(pattern),
            cast(Contract.created_at, String).ilike(pattern),
            cast(Contract.updated_at, String).ilike(pattern),
        ))

    rows = query.order_by(Contract.updated_at.desc()).all()
    return jsonify([row.to_dict() for row in rows])


@contracts_bp.get('/contracts/statistics')
@require_auth
def get_contract_statistics():
    total_count = Contract.query.count()
    total_amount = db.session.query(func.coalesce(func.sum(Contract.amount), 0)).scalar()

    archived_count = Contract.query.filter(Contract.is_archived == '已归档').count()
    archived_amount = db.session.query(
        func.coalesce(func.sum(Contract.amount), 0)
    ).filter(Contract.is_archived == '已归档').scalar()

    return jsonify({
        'total_count': int(total_count or 0),
        'total_amount': _format_decimal_plain(Decimal(str(total_amount or 0))),
        'archived_count': int(archived_count or 0),
        'archived_amount': _format_decimal_plain(Decimal(str(archived_amount or 0))),
    })


@contracts_bp.get('/contracts/dashboard-charts')
@require_auth
def get_dashboard_charts():
    with_file = Contract.query.filter(Contract.file_path.isnot(None), Contract.file_path != '').count()
    total_contract_count = Contract.query.count()
    contract_file_pie = {
        'with_file': int(with_file),
        'without_file': int(max(total_contract_count - with_file, 0)),
    }

    contract_file_paths = {
        _normalize_contract_file_path(row.file_path)
        for row in Contract.query.filter(Contract.file_path.isnot(None), Contract.file_path != '').all()
        if _normalize_contract_file_path(row.file_path)
    }
    try:
        storage_files = _collect_storage_files()
    except Exception:
        storage_files = []

    storage_paths = {
        _normalize_relative_path(item.get('path') or '')
        for item in storage_files
        if (item.get('path') or '').strip()
    }
    with_contract = len(storage_paths.intersection(contract_file_paths))
    file_contract_pie = {
        'with_contract': int(with_contract),
        'without_contract': int(max(len(storage_paths) - with_contract, 0)),
    }

    departments = _get_department_names()
    contract_counts = []
    file_counts = []
    for name in departments:
        contract_counts.append(Contract.query.filter(Contract.department == name).count())
        file_counts.append(
            Contract.query.filter(
                Contract.department == name,
                Contract.file_path.isnot(None),
                Contract.file_path != '',
            ).count()
        )

    return jsonify({
        'contract_file_pie': contract_file_pie,
        'file_contract_pie': file_contract_pie,
        'dept_bar': {
            'departments': departments,
            'contract_counts': contract_counts,
            'file_counts': file_counts,
        },
    })


@contracts_bp.get('/contracts/<int:contract_id>')
@require_auth
def get_contract(contract_id):
    row = Contract.query.get_or_404(contract_id)
    return jsonify(row.to_dict(include_fullbody=True))


@contracts_bp.post('/contracts/quick-match-files')
@require_auth
def quick_match_contract_files():
    body = request.get_json(silent=True) or {}
    raw_ids = body.get('ids')
    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({'message': 'ids is required'}), 400

    contract_ids = []
    for item in raw_ids:
        try:
            value = int(item)
        except (TypeError, ValueError):
            continue
        if value > 0:
            contract_ids.append(value)

    if not contract_ids:
        return jsonify({'message': 'ids is invalid'}), 400

    try:
        pdf_files = _collect_storage_pdf_files()
    except PermissionError as exc:
        return jsonify({'message': str(exc)}), 401
    except Exception as exc:
        return jsonify({'message': f'读取存储目录失败: {exc}'}), 500

    results = []
    success_count = 0

    for contract_id in contract_ids:
        row = Contract.query.get(contract_id)
        if not row:
            results.append({
                'id': contract_id,
                'status': 'failed',
                'message': '合同不存在',
            })
            continue

        if (row.is_archived or '').strip() == '已归档':
            results.append({
                'id': row.id,
                'contract_number': row.contract_number,
                'contract_name': row.contract_name,
                'status': 'failed',
                'message': '合同已归档，跳过',
            })
            continue

        if _normalize_contract_file_path(row.file_path):
            results.append({
                'id': row.id,
                'contract_number': row.contract_number,
                'contract_name': row.contract_name,
                'status': 'failed',
                'message': '合同已有附件，跳过',
                'file_path': row.file_path,
            })
            continue

        best_match, matched = _select_best_pdf_match(row,pdf_files)
        if not best_match:
            results.append({
                'id': row.id,
                'contract_number': row.contract_number,
                'contract_name': row.contract_name,
                'status': 'failed',
                'message': '未匹配到包含合同名称的PDF文件',
            })
            continue

        row.file_path = best_match['path']
        success_count += 1
        results.append({
            'id': row.id,
            'contract_number': row.contract_number,
            'contract_name': row.contract_name,
            'status': 'success',
            'message': '匹配成功',
            'file_path': best_match['path'],
            'matched_count': len(matched),
            'matched_name': best_match['name'],
            'similarity': round(float(best_match.get('similarity') or 0), 6),
        })

    db.session.commit()

    return jsonify({
        'total': len(contract_ids),
        'success': success_count,
        'failed': len(contract_ids) - success_count,
        'results': results,
    })


@contracts_bp.post('/contracts')
@require_auth
def create_contract():
    body = request.get_json(silent=True) or {}

    record, message, status_code, _ = _build_contract_record(body, g.current_user, update_mode=False)
    if record is None:
        return jsonify({'message': message}), status_code

    db.session.add(record)
    db.session.commit()
    return jsonify(record.to_dict(include_fullbody=True)), 201


@contracts_bp.post('/contracts/import-excel')
@require_auth
def import_contracts_excel():
    if 'file' not in request.files:
        return jsonify({'message': 'file is required'}), 400

    uploaded = request.files['file']
    if uploaded.filename == '':
        return jsonify({'message': 'empty filename'}), 400

    file_ext = os.path.splitext(uploaded.filename)[1].lower()
    if file_ext not in EXCEL_ALLOWED_EXTENSIONS:
        return jsonify({'message': '仅支持上传 xls 或 xlsx 文件'}), 400

    try:
        sheet_payloads = _load_excel_sheets(uploaded)
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({'message': str(exc)}), 500
    except Exception as exc:
        current_app.logger.exception('Excel import failed while reading workbook')
        return jsonify({'message': f'Excel解析失败: {exc}'}), 400

    if not sheet_payloads:
        return jsonify({'message': 'Excel 文件中没有可读取的数据'}), 400

    option_sets = _get_contract_option_sets()
    required_headers = {
        'contract_name': '合同名称',
        'handling_department': '承办部门',
    }
    pending_contract_numbers = set()
    imported_count = 0
    updated_count = 0
    skipped_count = 0
    processed_rows = 0
    errors = []
    failed_rows = []
    source_headers = []
    imported_sheet_names = []
    header_rows = {}
    skipped_sheets = []

    for sheet_name, rows in sheet_payloads:
        if not rows or all(_is_excel_row_empty(row) for row in rows):
            skipped_sheets.append({'sheet_name': sheet_name, 'reason': '工作表为空'})
            continue

        header_index, field_indexes, header_labels = _detect_excel_header(rows)
        if not field_indexes:
            skipped_sheets.append({'sheet_name': sheet_name, 'reason': '未识别到可用表头'})
            continue

        missing_headers = [label for key, label in required_headers.items() if key not in field_indexes]
        if missing_headers:
            skipped_sheets.append({
                'sheet_name': sheet_name,
                'reason': f'缺少必要列: {", ".join(missing_headers)}',
            })
            continue

        if not source_headers:
            source_headers = [_stringify_excel_value(cell) for cell in (rows[header_index] if header_index is not None else [])]

        imported_sheet_names.append(sheet_name)
        header_rows[sheet_name] = header_index + 1

        for excel_row_number, row in enumerate(rows[header_index + 1:], start=header_index + 2):
            if _is_excel_row_empty(row):
                continue

            payload = _build_import_payload_from_row(row, field_indexes, header_labels, option_sets)
            if not any(str(payload.get(key, '')).strip() for key in CONTRACT_FIELD_KEYS):
                continue

            processed_rows += 1
            record, message, status_code, is_update = _build_contract_record(
                payload,
                g.current_user,
                pending_contract_numbers=pending_contract_numbers,
                update_mode=True,
            )
            if record is None:
                skipped_count += 1
                errors.append({
                    'sheet_name': sheet_name,
                    'row': excel_row_number,
                    'status_code': status_code,
                    'message': message,
                })
                failed_rows.append({
                    'sheet_name': sheet_name,
                    'row': excel_row_number,
                    'message': message,
                    'row_values': list(row),
                })
                continue

            db.session.add(record)
            if is_update:
                updated_count += 1
            else:
                imported_count += 1
            if record.contract_number:
                pending_contract_numbers.add(record.contract_number)

    if not imported_sheet_names:
        return jsonify({
            'message': '未识别到可导入工作表，请确认每个工作表都包含合同名称、承办部门等列',
            'skipped_sheets': skipped_sheets,
        }), 400

    if processed_rows == 0:
        return jsonify({
            'message': '已识别工作表，但没有可导入的数据行',
            'sheet_names': imported_sheet_names,
            'skipped_sheets': skipped_sheets,
        }), 400

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Excel import failed while saving rows')
        return jsonify({'message': f'Excel导入保存失败: {exc}'}), 500

    report_sheet_name = imported_sheet_names[0] if len(imported_sheet_names) == 1 else '多个工作表'
    error_report_token, error_report_filename = _store_import_error_report(report_sheet_name, source_headers, failed_rows)

    return jsonify({
        'sheet_name': report_sheet_name,
        'sheet_names': imported_sheet_names,
        'header_row': header_rows.get(imported_sheet_names[0], 1),
        'header_rows': header_rows,
        'total_sheets': len(sheet_payloads),
        'imported_sheets': len(imported_sheet_names),
        'skipped_sheets': skipped_sheets,
        'total_rows': processed_rows,
        'imported_count': imported_count,
        'updated_count': updated_count,
        'skipped_count': skipped_count,
        'errors': errors[:50],
        'error_report_token': error_report_token,
        'error_report_filename': error_report_filename,
    })


@contracts_bp.get('/contracts/import-template')
@require_auth
def download_contract_import_template():
    try:
        output = _build_contract_import_template()
    except Exception as exc:
        current_app.logger.exception('Failed to build contract import template')
        return jsonify({'message': f'导入模板生成失败: {exc}'}), 500

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='合同导入模板.xlsx',
    )


@contracts_bp.get('/contracts/import-error-report/<token>')
@require_auth
def download_contract_import_error_report(token):
    payload = _IMPORT_ERROR_REPORTS.pop(token, None)
    if not payload:
        return jsonify({'message': '导入失败明细不存在或已失效，请重新导入后再下载'}), 404

    return send_file(
        BytesIO(payload['content']),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=payload['filename'],
    )


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



    if 'contract_amount' in body:
        contract_amount_text = str(body.get('contract_amount') or '').strip()
        if contract_amount_text:
            amount = _safe_decimal(contract_amount_text)
            if amount is None:
                return jsonify({'message': 'contract_amount is invalid'}), 400
            record.amount = amount
        else:
            record.amount = None
        current_app.logger.info('调试: contract_amount=%s, amount=%s', body.get('contract_amount'), record.amount)
        
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
        record.contract_type = _normalize_contract_type_value(body.get('contract_type')) or None
        if 'stamp_tax_rate' not in body:
            record.stamp_tax_rate = _get_stamp_tax_rate_by_contract_type(record.contract_type) or None
    if 'purchase_type' in body:
        record.purchase_type = (body.get('purchase_type') or '').strip() or None
    if 'stamp_tax_rate' in body:
        record.stamp_tax_rate = (body.get('stamp_tax_rate') or '').strip() or None
    if 'pricing_method' in body:
        record.pricing_method = (body.get('pricing_method') or '').strip() or None
    if 'copy_count' in body:
        copy_count_text = str(body.get('copy_count') or '').strip()
        if copy_count_text:
            if not re.fullmatch(r'\d+', copy_count_text):
                return jsonify({'message': 'copy_count is invalid'}), 400
            record.copy_count = int(copy_count_text)
        else:
            record.copy_count = None
    if 'save_place' in body:
        save_place = (body.get('save_place') or '').strip()
        if len(save_place) > 50:
            return jsonify({'message': 'save_place is too long (max 50)'}), 400
        record.save_place = save_place or None
    if 'is_archived' in body:
        record.is_archived = (body.get('is_archived') or '').strip() or None
    if 'project' in body:
        project = (body.get('project') or '').strip() or None
        if project:
            allowed_projects = _get_project_names()
            if project not in allowed_projects:
                return jsonify({'message': 'project is not in configured project settings'}), 400
        record.project = project
    if 'fullbody' in body:
        record.fullbody = (body.get('fullbody') or '').strip() or None
    if 'file_path' in body:
        normalized_file_path = _normalize_contract_file_path(body.get('file_path'))
        record.file_path = normalized_file_path or None
    if 'start_date' in body:
        record.start_date = _parse_date(body.get('start_date'))
    if 'end_date' in body:
        record.end_date = _parse_date(body.get('end_date'))
    if 'status' in body:
        record.status = (body.get('status') or '').strip() or record.status

    record.updated_by = (getattr(g, 'current_user', '') or '').strip() or None

    db.session.commit()
    return jsonify(record.to_dict(include_fullbody=True))


@contracts_bp.delete('/contracts/<int:contract_id>')
@require_auth
def delete_contract(contract_id):
    record = Contract.query.get_or_404(contract_id)

    try:
        _delete_contract_file(record)
    except ValueError:
        return jsonify({'message': 'file_path 非法'}), 400
    except Exception as exc:
        return jsonify({'message': f'删除文件失败: {exc}'}), 500

    db.session.delete(record)
    db.session.commit()
    return jsonify({'success': True})


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


def parse_contract_pdf_bak():
    body = request.get_json(silent=True) or {}
    incoming_fullbody = str(body.get('fullbody') or '').strip()
    use_fullbody_directly = len(incoming_fullbody) > 20

    if use_fullbody_directly:
        pdf_text = incoming_fullbody
        preview_lines = _preview_lines(pdf_text)
        current_app.logger.info(
            'AI parse: direct-fullbody mode user=%s chars=%s content_length=%s',
            g.current_user,
            len(pdf_text),
            request.content_length,
        )
    else:
        if 'file' not in request.files:
            return jsonify({'message': 'file is required（或提供长度超过20的fullbody）'}), 400

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
            pdf_text, preview_lines = extract_pdf_text(uploaded)
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

    match_candidates = _find_ai_match_candidates(fields)
    current_app.logger.info('AI parse: matched existing contracts=%s', len(match_candidates))

    current_app.logger.info('AI parse: success extracted fields=%s', fields)

    return jsonify({
        'fields': fields,
        'fullbody': pdf_text,
        'match_candidates': match_candidates,
    })


@contracts_bp.post('/contracts/ai-parse')
@require_auth
def parse_contract_pdf():
    body = request.get_json(silent=True) or {}
    incoming_fullbody = str(body.get('fullbody') or '').strip()
    incoming_url = str(body.get('url') or body.get('file_path') or request.form.get('url') or '').strip()
    use_fullbody_directly = len(incoming_fullbody) > 20

    if use_fullbody_directly:
        pdf_text = incoming_fullbody
        preview_lines = _preview_lines(pdf_text)
        current_app.logger.info(
            'AI parse: direct-fullbody mode user=%s chars=%s content_length=%s',
            g.current_user,
            len(pdf_text),
            request.content_length,
        )
    elif 'file' in request.files:
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
            pdf_text, preview_lines = mineru_extract_text_from_uploaded_pdf(uploaded)
        except Exception as exc:
            current_app.logger.exception('AI parse: PDF extraction failed')
            return jsonify({'message': f'PDF解析失败: {exc}'}), 400
    elif incoming_url:
        normalized_path = _normalize_relative_path(incoming_url)
        if not normalized_path:
            return jsonify({'message': 'url is invalid'}), 400
        if not normalized_path.lower().endswith('.pdf'):
            return jsonify({'message': 'url 对应文件必须是PDF'}), 400

        try:
            content, file_name, _mime = _load_storage_file_payload(normalized_path)
        except PermissionError as exc:
            return jsonify({'message': str(exc)}), 401
        except FileNotFoundError as exc:
            return jsonify({'message': str(exc)}), 404
        except ValueError:
            return jsonify({'message': 'url is invalid'}), 400
        except Exception as exc:
            return jsonify({'message': f'读取存储文件失败: {exc}'}), 500

        effective_name = str(file_name or os.path.basename(normalized_path) or 'upload.pdf')
        if not effective_name.lower().endswith('.pdf'):
            effective_name = f'{effective_name}.pdf'

        current_app.logger.info(
            'AI parse: url mode user=%s path=%s bytes=%s',
            g.current_user,
            normalized_path,
            len(content or b''),
        )

        uploaded = FileStorage(
            stream=BytesIO(content),
            filename=effective_name,
            content_type='application/pdf',
        )

        try:
            pdf_text, preview_lines = mineru_extract_text_from_uploaded_pdf(uploaded, source_file_path=normalized_path)
        except Exception as exc:
            current_app.logger.exception('AI parse: PDF extraction failed')
            return jsonify({'message': f'PDF解析失败: {exc}'}), 400
    else:
        return jsonify({'message': 'file is required（或提供长度超过20的fullbody，或提供url）'}), 400

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

    match_candidates = _find_ai_match_candidates(fields)
    current_app.logger.info('AI parse: matched existing contracts=%s', len(match_candidates))

    current_app.logger.info('AI parse: success extracted fields=%s', fields)

    return jsonify({
        'fields': fields,
        'fullbody': pdf_text,
        'match_candidates': match_candidates,
    })


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
