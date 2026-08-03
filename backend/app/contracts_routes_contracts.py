import os
import re
from io import BytesIO
from decimal import Decimal
from datetime import date, datetime
from typing import Any

import requests
from flask import current_app, g, jsonify, request, send_file
from sqlalchemy import String, cast, func, or_
from requests.exceptions import RequestException
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
    _get_all_department_names,
    _get_department_names,
    _resolve_current_management_department_name,
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
    _rename_contract_file_to_contract_identity,
    _safe_decimal,
    _get_stamp_tax_rate_by_contract_type,
    _sanitize_upload_filename,
    _select_best_pdf_match,
    _synology_upload_file,
)
from .contracts_routes_contracts_helpers import (
    _IMPORT_ERROR_REPORTS,
    _build_completeness_value,
    _build_contract_import_template,
    _build_contract_record,
    _build_group_report_excel,
    _build_import_payload_from_row,
    _detect_excel_header,
    _is_excel_row_empty,
    _load_excel_sheets,
    _store_import_error_report,
    _stringify_excel_value,
)
from .files_core_helpers import _load_storage_file_payload
from .extensions import db
from .models import Contract, Department, UserLog, UserPermission


ROLE_SUPER_ADMIN = 'super_admin'
ROLE_SYNOLOGY_SUPER_ADMIN = 'synology_super_admin'
PERMISSION_ALL = '全部'
CONTRACT_LOG_MODULE = '合同记录'
COLOR_FLAG_OPTIONS = {'红旗', '橙旗', '黄旗', '绿旗', '蓝旗'}
COMPLETENESS_OPTIONS = {'是', '否'}


CONTRACT_LOG_FIELDS = {
    'contract_number': '合同编号',
    'contract_name': '合同名称',
    'contract_unit': '合同单位',
    'amount': '合同金额',
    'currency': '币种',
    'handler': '承办人',
    'department': '承办部门',
    'current_management_department': '现管部门',
    'contract_form': '合同形式',
    'original_contract_id': '原合同ID',
    'contract_determination_method': '定标方式',
    'handling_date': '承办日期',
    'contract_type': '合同类型',
    'purchase_type': '采购类型',
    'contract_execution_status': '合同执行状态',
    'stamp_tax_rate': '印花税率',
    'pricing_method': '计价方式',
    'copy_count': '份数',
    'save_place': '存档位置',
    'is_archived': '是否归档',
    'color_flag': '颜色标记',
    'completeness': '完整性',
    'project': '项目',
    'fullbody': '正文',
    'file_path': '文件路径',
    'start_date': '开始日期',
    'end_date': '结束日期',
    'status': '状态',
}

HT_DETAIL_PAYMENT_FIELDS = [
    'FPYZ_NAM',
    'VEN_NO',
    'FKSP_STA',
    'FKLX_NO',
    'YSM_ID',
    'FPYZ_AMT',
    'BCZF_AMT',
    'YHYZF_AMT',
    'CWFK_ID',
    'JSFS_TYP',
    'FPYZ_NO',
    'YWLX_TYP',
    'CN_QTY',
    'JBUSR_ID',
    'JBRQ_DTM',
    'JHFK_DTM',
]


def _serialize_log_value(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, Decimal):
        return format(value, 'f')
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value).strip()


def _snapshot_contract_log_fields(row: Contract) -> dict[str, str]:
    return {
        key: _serialize_log_value(getattr(row, key, None))
        for key in CONTRACT_LOG_FIELDS
    }


def _resolve_current_user_id() -> int | None:
    username = (getattr(g, 'current_user', '') or '').strip()
    if not username:
        return None

    permission_row = UserPermission.query.filter_by(login_name=username).first()
    return permission_row.id if permission_row else None


def _add_user_log(operation_type: str, operation_target: str, detail: str) -> None:
    db.session.add(UserLog(
        user_id=_resolve_current_user_id(),
        operation_module=CONTRACT_LOG_MODULE,
        operation_target=operation_target or '-',
        operation_type=operation_type,
        detail=detail or '',
    ))


def _write_contract_user_log(operation_type: str, operation_target: str, detail: str) -> None:
    try:
        _add_user_log(operation_type, operation_target, detail)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning('contract operation log write skipped: %s', exc)


def _write_ai_recognition_log(operation_target: str, detail: str, *, is_failure: bool = False) -> None:
    _write_contract_user_log(
        operation_type='AI识别失败' if is_failure else 'AI识别',
        operation_target=operation_target,
        detail=detail,
    )


def _build_contract_update_detail(before: dict[str, str], after: dict[str, str]) -> str:
    changes = []
    for key, label in CONTRACT_LOG_FIELDS.items():
        old_value = before.get(key, '')
        new_value = after.get(key, '')
        if old_value == new_value:
            continue
        changes.append(f'{label}: [{old_value}] -> [{new_value}]')

    if not changes:
        return '更新合同，但字段值无变化'
    return '更新字段：' + '; '.join(changes)

def _normalize_external_payment_items(payload: Any) -> list[dict[str, str]]:
    if not isinstance(payload, list):
        return []

    normalized = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        normalized_row = {
            field: str(row.get(field) or '').strip()
            for field in HT_DETAIL_PAYMENT_FIELDS
        }
        normalized.append(normalized_row)
    return normalized


def _request_external_contract_detail(htno: str) -> dict[str, Any]:
    api_url = (current_app.config.get('HT_DETAIL_API_URL') or '').strip()
    api_username = (current_app.config.get('HT_DETAIL_API_USERNAME') or '').strip()
    api_password = (current_app.config.get('HT_DETAIL_API_PASSWORD') or '').strip()
    timeout_seconds = int(current_app.config.get('HT_DETAIL_API_TIMEOUT_SECONDS') or 15)

    if not api_url:
        raise RuntimeError('未配置 HT_DETAIL_API_URL')
    if not api_username or not api_password:
        raise RuntimeError('未配置合同详情接口认证信息，请设置 HT_DETAIL_API_USERNAME/HT_DETAIL_API_PASSWORD')

    try:
        response = requests.get(
            api_url,
            params={'htno': htno},
            auth=(api_username, api_password),
            timeout=max(timeout_seconds, 5),
        )
        response.raise_for_status()
    except RequestException as exc:
        raise RuntimeError(f'调用 GetHtDetail 接口失败: {exc}') from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError('GetHtDetail 接口返回的不是合法 JSON') from exc

    if not isinstance(data, dict):
        raise RuntimeError('GetHtDetail 接口返回格式异常')
    return data


def _resolve_current_user_department_scope() -> tuple[bool, list[str]]:
    username = (getattr(g, 'current_user', '') or '').strip()
    if not username:
        return True, []

    permission_row = UserPermission.query.filter_by(login_name=username).first()
    if not permission_row:
        return True, []

    if str(getattr(permission_row, 'role', '') or '').strip() in {ROLE_SUPER_ADMIN, ROLE_SYNOLOGY_SUPER_ADMIN}:
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


def _current_user_role() -> str:
    username = (getattr(g, 'current_user', '') or '').strip()
    if not username:
        return ''

    permission_row = UserPermission.query.filter_by(login_name=username).first()
    if not permission_row:
        return ''

    return str(getattr(permission_row, 'role', '') or '').strip()


def _is_super_role(role: str) -> bool:
    return str(role or '').strip() in {ROLE_SUPER_ADMIN, ROLE_SYNOLOGY_SUPER_ADMIN}


def _is_current_user_super_role() -> bool:
    return _is_super_role(_current_user_role())


def _is_archived_contract(record: Contract) -> bool:
    return (getattr(record, 'is_archived', '') or '').strip() == '已归档'


def _ensure_archived_contract_editable(record: Contract):
    if not _is_archived_contract(record):
        return None

    if _is_super_role(_current_user_role()):
        return None

    return jsonify({'message': '已归档合同仅超管或群晖超管可修改'}), 403

@contracts_bp.get('/contracts')
@require_auth
def list_contracts():
    department = (request.args.get('handling_department') or request.args.get('department') or '').strip()
    project = (request.args.get('project') or '').strip()
    status = (request.args.get('status') or '').strip()
    keyword = (request.args.get('keyword') or request.args.get('search') or '').strip()
    has_file = (request.args.get('has_file') or '').strip().lower()
    is_archived = (request.args.get('is_archived') or '').strip()
    color_flag = (request.args.get('color_flag') or '').strip()
    completeness = (request.args.get('completeness') or '').strip()
    current_management_department = (request.args.get('current_management_department') or '').strip()

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
    if current_management_department == '__empty__':
        query = query.filter(Contract.current_management_department.is_(None))
    elif current_management_department:
        query = query.filter(Contract.current_management_department == current_management_department)
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
    if color_flag:
        query = query.filter(Contract.color_flag == color_flag)
    if completeness:
        query = query.filter(Contract.completeness == completeness)
    if keyword:
        pattern = f'%{keyword}%'
        query = query.filter(or_(
            Contract.contract_number.ilike(pattern),
            Contract.contract_name.ilike(pattern),
            Contract.contract_unit.ilike(pattern),
            Contract.currency.ilike(pattern),
            Contract.handler.ilike(pattern),
            Contract.department.ilike(pattern),
            Contract.current_management_department.ilike(pattern),
            Contract.contract_determination_method.ilike(pattern),
            Contract.contract_type.ilike(pattern),
            Contract.purchase_type.ilike(pattern),
            Contract.stamp_tax_rate.ilike(pattern),
            Contract.pricing_method.ilike(pattern),
            Contract.save_place.ilike(pattern),
            Contract.is_archived.ilike(pattern),
            Contract.color_flag.ilike(pattern),
            Contract.completeness.ilike(pattern),
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


@contracts_bp.get('/contracts/export-excel')
@require_auth
def export_contracts_excel():
    department = (request.args.get('handling_department') or request.args.get('department') or '').strip()
    project = (request.args.get('project') or '').strip()
    status = (request.args.get('status') or '').strip()
    keyword = (request.args.get('keyword') or request.args.get('search') or '').strip()
    has_file = (request.args.get('has_file') or '').strip().lower()
    is_archived = (request.args.get('is_archived') or '').strip()
    color_flag = (request.args.get('color_flag') or '').strip()
    completeness = (request.args.get('completeness') or '').strip()
    current_management_department = (request.args.get('current_management_department') or '').strip()

    query = Contract.query
    unrestricted, allowed_departments = _resolve_current_user_department_scope()
    if not unrestricted:
        if not allowed_departments:
            return jsonify({'message': '无可导出数据'}), 403
        query = query.filter(Contract.department.in_(allowed_departments))

    if department == '__empty__':
        query = query.filter(Contract.department.is_(None))
    elif department:
        query = query.filter(Contract.department == department)
    if current_management_department == '__empty__':
        query = query.filter(Contract.current_management_department.is_(None))
    elif current_management_department:
        query = query.filter(Contract.current_management_department == current_management_department)
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
    if color_flag:
        query = query.filter(Contract.color_flag == color_flag)
    if completeness:
        query = query.filter(Contract.completeness == completeness)
    if keyword:
        pattern = f'%{keyword}%'
        query = query.filter(or_(
            Contract.contract_number.ilike(pattern),
            Contract.contract_name.ilike(pattern),
            Contract.contract_unit.ilike(pattern),
            Contract.currency.ilike(pattern),
            Contract.handler.ilike(pattern),
            Contract.department.ilike(pattern),
            Contract.current_management_department.ilike(pattern),
            Contract.contract_determination_method.ilike(pattern),
            Contract.contract_type.ilike(pattern),
            Contract.purchase_type.ilike(pattern),
            Contract.stamp_tax_rate.ilike(pattern),
            Contract.pricing_method.ilike(pattern),
            Contract.save_place.ilike(pattern),
            Contract.is_archived.ilike(pattern),
            Contract.color_flag.ilike(pattern),
            Contract.completeness.ilike(pattern),
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

    try:
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = '合同信息'

        headers = [
            '合同编号', '合同名称', '合同单位', '合同执行状态', '合同金额', '币种', '承办人', '承办部门', '现管部门',
            '定标方式', '承办日期', '合同类型', '采购类型', '印花税率', '计价方式',
            '份数', '存档位置', '是否归档', '颜色标记', '完整性', '项目', '全文', '开始日期', '结束日期',
            '状态', '文件路径', '创建人', '修改人', '创建时间', '修改时间',
        ]
        sheet.append(headers)

        for row in rows:
            payload = row.to_dict(include_fullbody=True)
            sheet.append([
                payload.get('contract_number') or '',
                payload.get('contract_name') or '',
                payload.get('contract_unit') or '',
                payload.get('contract_execution_status') or '',
                payload.get('contract_amount') or '',
                payload.get('currency') or '',
                payload.get('handler') or '',
                payload.get('handling_department') or '',
                payload.get('current_management_department') or '',
                payload.get('contract_determination_method') or '',
                payload.get('handling_date') or '',
                payload.get('contract_type') or '',
                payload.get('purchase_type') or '',
                payload.get('stamp_tax_rate') or '',
                payload.get('pricing_method') or '',
                payload.get('copy_count') or '',
                payload.get('save_place') or '',
                payload.get('is_archived') or '',
                payload.get('color_flag') or '',
                payload.get('completeness') or '',
                payload.get('project') or '',
                payload.get('fullbody') or '',
                payload.get('start_date') or '',
                payload.get('end_date') or '',
                payload.get('status') or '',
                payload.get('file_path') or '',
                payload.get('created_by') or '',
                payload.get('updated_by') or '',
                payload.get('created_at') or '',
                payload.get('updated_at') or '',
            ])

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
    except Exception as exc:
        current_app.logger.exception('Contract export failed')
        return jsonify({'message': f'导出EXCEL失败: {exc}'}), 500

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='合同信息导出.xlsx',
    )


@contracts_bp.get('/contracts/export-group-report-excel')
@require_auth
def export_group_report_excel():
    year_param = (request.args.get('year') or '').strip()
    if year_param:
        try:
            report_year = int(year_param)
        except ValueError:
            return jsonify({'message': 'year 参数无效'}), 400
    else:
        report_year = date.today().year
    current_management_department = (request.args.get('current_management_department') or '').strip()

    if report_year < 2025 or report_year > date.today().year:
        return jsonify({'message': 'year 参数超出允许范围'}), 400

    department = (request.args.get('handling_department') or request.args.get('department') or '').strip()
    project = (request.args.get('project') or '').strip()
    status = (request.args.get('status') or '').strip()
    keyword = (request.args.get('keyword') or request.args.get('search') or '').strip()
    has_file = (request.args.get('has_file') or '').strip().lower()
    is_archived = (request.args.get('is_archived') or '').strip()
    color_flag = (request.args.get('color_flag') or '').strip()
    completeness = (request.args.get('completeness') or '').strip()
    if current_management_department == '__empty__':
        query = query.filter(Contract.current_management_department.is_(None))
    elif current_management_department:
        query = query.filter(Contract.current_management_department == current_management_department)

    query = Contract.query
    unrestricted, allowed_departments = _resolve_current_user_department_scope()
    if not unrestricted:
        if not allowed_departments:
            return jsonify({'message': '无可导出数据'}), 403
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
    if color_flag:
        query = query.filter(Contract.color_flag == color_flag)
    if completeness:
        query = query.filter(Contract.completeness == completeness)
    query = query.filter(or_(
        Contract.contract_determination_method.is_(None),
        Contract.contract_determination_method != '非采购类',
    ))
    if keyword:
        pattern = f'%{keyword}%'
        query = query.filter(or_(
            Contract.contract_number.ilike(pattern),
            Contract.contract_name.ilike(pattern),
            Contract.contract_unit.ilike(pattern),
            Contract.currency.ilike(pattern),
            Contract.handler.ilike(pattern),
            Contract.department.ilike(pattern),
            Contract.current_management_department.ilike(pattern),
            Contract.contract_determination_method.ilike(pattern),
            Contract.contract_type.ilike(pattern),
            Contract.purchase_type.ilike(pattern),
            Contract.stamp_tax_rate.ilike(pattern),
            Contract.pricing_method.ilike(pattern),
            Contract.save_place.ilike(pattern),
            Contract.is_archived.ilike(pattern),
            Contract.color_flag.ilike(pattern),
            Contract.completeness.ilike(pattern),
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

    year_start = date(report_year, 1, 1)
    next_year_start = date(report_year + 1, 1, 1)
    rows = query.filter(
        Contract.handling_date.isnot(None),
        Contract.handling_date >= year_start,
        Contract.handling_date < next_year_start,
    ).order_by(Contract.handling_date.asc(), Contract.updated_at.asc()).all()

    try:
        output = _build_group_report_excel(rows, current_app.config.get('MY_COMP', ''), report_year)
    except Exception as exc:
        current_app.logger.exception('Group report export failed')
        return jsonify({'message': f'集团上报EXCEL导出失败: {exc}'}), 500

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'集团上报EXCEL_{report_year}.xlsx',
    )


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

    def _extract_department_from_path(path_text: str) -> str:
        normalized = _normalize_relative_path(path_text or '')
        if not normalized:
            return ''
        parts = [part.strip() for part in normalized.split('/') if part.strip()]
        return parts[0] if parts else ''

    departments = _get_department_names()
    department_rows = Department.query.all()

    handler_login_by_department = {}
    for row in department_rows:
        name = str(getattr(row, 'name', '') or '').strip()
        handler_login = str(getattr(row, 'handler_login_name', '') or '').strip()
        if name and handler_login:
            handler_login_by_department[name] = handler_login

    # 对于“现管部门”，允许从历史部门映射里兜底拿到经办人。
    for row in department_rows:
        is_existing = bool(getattr(row, 'is_existing', True))
        if is_existing:
            continue
        mapped_name = str(getattr(row, 'current_department_name', '') or '').strip()
        handler_login = str(getattr(row, 'handler_login_name', '') or '').strip()
        if mapped_name and handler_login and mapped_name not in handler_login_by_department:
            handler_login_by_department[mapped_name] = handler_login

    handler_logins = {
        login_name
        for login_name in handler_login_by_department.values()
        if login_name
    }
    handler_desc_by_login = {}
    if handler_logins:
        for row in UserPermission.query.filter(UserPermission.login_name.in_(handler_logins)).all():
            login_name = str(getattr(row, 'login_name', '') or '').strip()
            description = str(getattr(row, 'description', '') or '').strip()
            if login_name:
                handler_desc_by_login[login_name] = description

    contract_counts = []
    file_counts = []
    contracts_by_current_department = {name: [] for name in departments}
    for row in Contract.query.all():
        current_department = (getattr(row, 'current_management_department', '') or '').strip()
        if current_department in contracts_by_current_department:
            contracts_by_current_department[current_department].append(row)

    for name in departments:
        contract_counts.append(Contract.query.filter(Contract.department == name).count())
        file_counts.append(
            Contract.query.filter(
                Contract.department == name,
                Contract.file_path.isnot(None),
                Contract.file_path != '',
            ).count()
        )

    current_year = datetime.now().year
    total_counts = []
    organized_counts = []
    current_year_counts = []
    handler_descriptions = []

    for name in departments:
        rows = contracts_by_current_department.get(name, [])
        total_counts.append(len(rows))
        organized_counts.append(sum(1 for row in rows if (getattr(row, 'completeness', '') or '').strip() == '是'))
        current_year_counts.append(sum(
            1
            for row in rows
            if getattr(row, 'handling_date', None) is not None and row.handling_date.year == current_year
        ))

        handler_login_name = str(handler_login_by_department.get(name, '') or '').strip()
        handler_description = str(handler_desc_by_login.get(handler_login_name, '') or '').strip()
        handler_descriptions.append(handler_description)

    storage_pdf_paths = {
        _normalize_relative_path(item.get('path') or '')
        for item in storage_files
        if (item.get('path') or '').strip() and _normalize_relative_path(item.get('path') or '').lower().endswith('.pdf')
    }
    contract_pdf_paths = {
        _normalize_contract_file_path(getattr(row, 'file_path', '') or '')
        for row in Contract.query.filter(Contract.file_path.isnot(None), Contract.file_path != '').all()
        if _normalize_contract_file_path(getattr(row, 'file_path', '') or '')
    }

    no_main_file_counts = []
    for name in departments:
        dept_storage_pdf_paths = {
            path
            for path in storage_pdf_paths
            if _extract_department_from_path(path) == name
        }
        no_main_file_counts.append(len(dept_storage_pdf_paths - contract_pdf_paths))

    return jsonify({
        'contract_file_pie': contract_file_pie,
        'file_contract_pie': file_contract_pie,
        'dept_bar': {
            'departments': departments,
            'contract_counts': contract_counts,
            'file_counts': file_counts,
        },
        'dept_current_management_bar': {
            'departments': departments,
            'handler_descriptions': handler_descriptions,
            'total_counts': total_counts,
            'organized_counts': organized_counts,
            'no_main_file_counts': no_main_file_counts,
            'current_year_counts': current_year_counts,
        },
    })


@contracts_bp.get('/contracts/<int:contract_id>')
@require_auth
def get_contract(contract_id):
    row = Contract.query.get_or_404(contract_id)
    return jsonify(row.to_dict(include_fullbody=True))


@contracts_bp.get('/contracts/<int:contract_id>/payment-flows')
@require_auth
def get_contract_payment_flows(contract_id):
    row = Contract.query.get_or_404(contract_id)
    current_user = (getattr(g, 'current_user', '') or '').strip()
    contract_number = (row.contract_number or '').strip()
    if not contract_number:
        return jsonify({
            'contract_id': row.id,
            'contract_number': '',
            'payments': [],
            'message': '当前合同没有合同编号，无法查询支付流水',
        })

    try:
        detail_payload = _request_external_contract_detail(contract_number)
    except RuntimeError as exc:
        current_app.logger.warning(
            'payment-flow query failed contract_id=%s contract_number=%s user=%s message=%s',
            row.id,
            contract_number,
            current_user or '-',
            str(exc),
        )
        return jsonify({'message': str(exc)}), 502

    payments = _normalize_external_payment_items(detail_payload.get('payment'))
    current_app.logger.info(
        'payment-flow query success contract_id=%s contract_number=%s user=%s payment_count=%s payments=%s',
        row.id,
        contract_number,
        current_user or '-',
        len(payments),
        payments,
    )
    return jsonify({
        'contract_id': row.id,
        'contract_number': contract_number,
        'payments': payments,
    })


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
    is_super_user = _is_current_user_super_role()

    color_flag = (body.get('color_flag') or '').strip()
    if color_flag and color_flag not in COLOR_FLAG_OPTIONS:
        return jsonify({'message': 'color_flag is invalid'}), 400

    execution_status = (body.get('contract_execution_status') or '').strip()
    if not execution_status:
        return jsonify({'message': 'contract_execution_status is required'}), 400
    if execution_status not in {'正在执行', '正常终止', '变更终止', '解除终止'}:
        return jsonify({'message': 'contract_execution_status is invalid'}), 400

    requested_completeness = (body.get('completeness') or '').strip()

    record, message, status_code, _ = _build_contract_record(body, g.current_user, update_mode=False)
    if record is None:
        return jsonify({'message': message}), status_code
    record.contract_execution_status = execution_status

    db.session.add(record)
    try:
        renamed_file_path = _rename_contract_file_to_contract_identity(record)
    except FileNotFoundError as exc:
        db.session.rollback()
        return jsonify({'message': str(exc)}), 404
    except ValueError:
        db.session.rollback()
        return jsonify({'message': 'file_path 非法'}), 400
    except Exception as exc:
        db.session.rollback()
        return jsonify({'message': f'附件重命名失败: {exc}'}), 500

    if renamed_file_path:
        record.file_path = renamed_file_path

    # 仅当超管明确传入“是”时允许手工置为“是”，其余情况统一走系统规则。
    if requested_completeness == '是' and is_super_user:
        record.completeness = '是'
    else:
        record.completeness = _build_completeness_value(
            record.file_path,
            record.contract_determination_method,
            record.purchase_type,
            record.contract_execution_status,
        )

    db.session.flush()
    operation_target = (record.contract_number or '').strip() or f'ID:{record.id or "-"}'
    _add_user_log(
        operation_type='新建',
        operation_target=operation_target,
        detail=(
            f'新建合同：合同名称={record.contract_name or ""}; '
            f'承办部门={record.department or ""}; 文件路径={record.file_path or ""}'
        ),
    )

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
        'contract_execution_status': '合同执行状态',
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
    snapshot_before = _snapshot_contract_log_fields(record)
    is_super_user = _is_current_user_super_role()

    denied = _ensure_archived_contract_editable(record)

    if denied:
        return denied

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
    if 'contract_form' in body:
        record.contract_form = (body.get('contract_form') or '').strip() or None
    if 'contract_execution_status' in body:
        execution_status = (body.get('contract_execution_status') or '').strip()
        if not execution_status:
            return jsonify({'message': 'contract_execution_status is required'}), 400
        if execution_status not in {'正在执行', '正常终止', '变更终止', '解除终止'}:
            return jsonify({'message': 'contract_execution_status is invalid'}), 400
        record.contract_execution_status = execution_status
    if 'handling_department' in body:
        department = (body.get('handling_department') or '').strip()
        if department:
            allowed_departments = _get_all_department_names()
            current_department = (record.department or '').strip()
            if department not in allowed_departments and department != current_department:
                return jsonify({'message': 'handling_department is not in configured department settings'}), 400
            _department_dir(department)
            record.department = department
            if 'current_management_department' not in body:
                record.current_management_department = _resolve_current_management_department_name(department) or None
    if 'current_management_department' in body:
        record.current_management_department = (body.get('current_management_department') or '').strip() or None
    if 'original_contract_id' in body:
        original_contract_id_text = str(body.get('original_contract_id') or '').strip()
        if original_contract_id_text:
            if not re.fullmatch(r'\d+', original_contract_id_text):
                return jsonify({'message': 'original_contract_id is invalid'}), 400
            original_contract_id = int(original_contract_id_text)
            if original_contract_id == record.id:
                return jsonify({'message': 'original_contract_id cannot reference self'}), 400
            original_contract = Contract.query.get(original_contract_id)
            if not original_contract:
                return jsonify({'message': 'original_contract_id not found'}), 404
            record.original_contract_id = original_contract_id
        else:
            record.original_contract_id = None
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
    if 'color_flag' in body:
        color_flag = (body.get('color_flag') or '').strip()
        if color_flag and color_flag not in COLOR_FLAG_OPTIONS:
            return jsonify({'message': 'color_flag is invalid'}), 400
        record.color_flag = color_flag or None

    requested_completeness = (body.get('completeness') or '').strip() if 'completeness' in body else ''
        
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

    try:
        renamed_file_path = _rename_contract_file_to_contract_identity(record)
    except FileNotFoundError as exc:
        return jsonify({'message': str(exc)}), 404
    except ValueError:
        return jsonify({'message': 'file_path 非法'}), 400
    except Exception as exc:
        return jsonify({'message': f'附件重命名失败: {exc}'}), 500

    if renamed_file_path:
        record.file_path = renamed_file_path

    # 仅当超管明确传入“是”时允许手工置为“是”，其余情况统一走系统规则。
    if requested_completeness == '是' and is_super_user:
        record.completeness = '是'
    else:
        record.completeness = _build_completeness_value(
            record.file_path,
            record.contract_determination_method,
            record.purchase_type,
            record.contract_execution_status,
        )

    record.updated_by = (getattr(g, 'current_user', '') or '').strip() or None

    snapshot_after = _snapshot_contract_log_fields(record)
    operation_target = (record.contract_number or '').strip() or f'ID:{record.id}'
    _add_user_log(
        operation_type='更新',
        operation_target=operation_target,
        detail=_build_contract_update_detail(snapshot_before, snapshot_after),
    )

    db.session.commit()
    return jsonify(record.to_dict(include_fullbody=True))


@contracts_bp.delete('/contracts/<int:contract_id>')
@require_auth
def delete_contract(contract_id):
    record = Contract.query.get_or_404(contract_id)

    denied = _ensure_archived_contract_editable(record)
    if denied:
        return denied

    try:
        _delete_contract_file(record)
    except ValueError:
        return jsonify({'message': 'file_path 非法'}), 400
    except Exception as exc:
        return jsonify({'message': f'删除文件失败: {exc}'}), 500

    operation_target = (record.contract_number or '').strip() or f'ID:{record.id}'
    _add_user_log(
        operation_type='删除',
        operation_target=operation_target,
        detail=f'删除合同：合同名称={record.contract_name or ""}; 承办部门={record.department or ""}',
    )

    db.session.delete(record)
    db.session.commit()
    return jsonify({'success': True})


@contracts_bp.post('/contracts/<int:contract_id>/upload')
@require_auth
def upload_contract_file(contract_id):
    record = Contract.query.get_or_404(contract_id)

    denied = _ensure_archived_contract_editable(record)
    if denied:
        return denied

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

    try:
        renamed_file_path = _rename_contract_file_to_contract_identity(record)
    except FileNotFoundError as exc:
        db.session.rollback()
        return jsonify({'message': str(exc)}), 404
    except ValueError:
        db.session.rollback()
        return jsonify({'message': 'file_path 非法'}), 400
    except Exception as exc:
        db.session.rollback()
        return jsonify({'message': f'附件重命名失败: {exc}'}), 500

    if renamed_file_path:
        record.file_path = renamed_file_path

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


def _update_contract_fullbody_by_file_path(file_path: str, fullbody: str) -> tuple[int, int]:
    normalized_path = _normalize_relative_path(file_path)
    normalized_fullbody = str(fullbody or '').strip()
    if not normalized_path or not normalized_fullbody:
        return 0, 0

    rows = Contract.query.filter(
        Contract.file_path.isnot(None),
        func.lower(Contract.file_path) == normalized_path.lower(),
    ).all()
    if not rows:
        return 0, 0

    can_edit_archived = _is_super_role(_current_user_role())
    current_user = (getattr(g, 'current_user', '') or '').strip() or None
    updated_count = 0
    blocked_archived_count = 0
    for row in rows:
        if _is_archived_contract(row) and not can_edit_archived:
            blocked_archived_count += 1
            continue
        row.fullbody = normalized_fullbody
        row.updated_by = current_user
        updated_count += 1

    if updated_count > 0:
        db.session.commit()

    return updated_count, blocked_archived_count


@contracts_bp.post('/contracts/ai-parse')
@require_auth
def parse_contract_pdf():
    body = request.get_json(silent=True) or {}
    incoming_fullbody = str(body.get('fullbody') or '').strip()
    incoming_url = str(body.get('url') or body.get('file_path') or request.form.get('url') or '').strip()
    normalized_storage_path = ''
    use_fullbody_directly = len(incoming_fullbody) > 20
    ai_log_target = 'direct-fullbody'
    updated_rows = 0
    blocked_archived_rows = 0

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

        ai_log_target = str(uploaded.filename or '').strip() or 'uploaded-pdf'

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
            _write_ai_recognition_log(ai_log_target, f'AI识别失败：PDF解析失败，原因={exc}', is_failure=True)
            current_app.logger.exception('AI parse: PDF extraction failed')
            return jsonify({'message': f'PDF解析失败: {exc}'}), 400
    elif incoming_url:
        normalized_storage_path = _normalize_relative_path(incoming_url)
        if not normalized_storage_path:
            return jsonify({'message': 'url is invalid'}), 400
        if not normalized_storage_path.lower().endswith('.pdf'):
            return jsonify({'message': 'url 对应文件必须是PDF'}), 400
        ai_log_target = normalized_storage_path

        try:
            content, file_name, _mime = _load_storage_file_payload(normalized_storage_path)
        except PermissionError as exc:
            _write_ai_recognition_log(ai_log_target, f'AI识别失败：读取存储文件未授权，原因={exc}', is_failure=True)
            return jsonify({'message': str(exc)}), 401
        except FileNotFoundError as exc:
            _write_ai_recognition_log(ai_log_target, f'AI识别失败：存储文件不存在，原因={exc}', is_failure=True)
            return jsonify({'message': str(exc)}), 404
        except ValueError:
            _write_ai_recognition_log(ai_log_target, 'AI识别失败：url 非法', is_failure=True)
            return jsonify({'message': 'url is invalid'}), 400
        except Exception as exc:
            _write_ai_recognition_log(ai_log_target, f'AI识别失败：读取存储文件失败，原因={exc}', is_failure=True)
            return jsonify({'message': f'读取存储文件失败: {exc}'}), 500

        effective_name = str(file_name or os.path.basename(normalized_storage_path) or 'upload.pdf')
        if not effective_name.lower().endswith('.pdf'):
            effective_name = f'{effective_name}.pdf'

        current_app.logger.info(
            'AI parse: url mode user=%s path=%s bytes=%s',
            g.current_user,
            normalized_storage_path,
            len(content or b''),
        )

        uploaded = FileStorage(
            stream=BytesIO(content),
            filename=effective_name,
            content_type='application/pdf',
        )

        try:
            pdf_text, preview_lines = mineru_extract_text_from_uploaded_pdf(uploaded, source_file_path=normalized_storage_path)
        except Exception as exc:
            _write_ai_recognition_log(ai_log_target, f'AI识别失败：PDF解析失败，原因={exc}', is_failure=True)
            current_app.logger.exception('AI parse: PDF extraction failed')
            return jsonify({'message': f'PDF解析失败: {exc}'}), 400
    else:
        return jsonify({'message': 'file is required（或提供长度超过20的fullbody，或提供url）'}), 400

    _write_ai_recognition_log(ai_log_target, f'执行AI识别：目标={ai_log_target}')

    if not pdf_text:
        _write_ai_recognition_log(ai_log_target, 'AI识别失败：未解析到可用文本', is_failure=True)
        current_app.logger.warning('AI parse: no text extracted, preview_lines=%s', preview_lines)
        return jsonify({
            'message': 'PDF未解析到可用文本，请确认扫描件清晰度/方向或是否含可读文字',
            'ocr_preview_lines': preview_lines,
        }), 400

    if normalized_storage_path:
        try:
            updated_rows, blocked_archived_rows = _update_contract_fullbody_by_file_path(normalized_storage_path, pdf_text)
        except Exception as exc:
            db.session.rollback()
            _write_ai_recognition_log(ai_log_target, f'AI识别失败：更新合同全文失败，原因={exc}', is_failure=True)
            current_app.logger.exception('AI parse: failed to persist fullbody by file_path=%s', normalized_storage_path)
            return jsonify({'message': f'更新合同全文失败: {exc}'}), 500

        if blocked_archived_rows > 0 and updated_rows == 0:
            _write_ai_recognition_log(ai_log_target, 'AI识别失败：目标合同已归档，当前用户无权更新', is_failure=True)
            current_app.logger.warning(
                'AI parse: blocked archived fullbody update by file_path=%s blocked_rows=%s',
                normalized_storage_path,
                blocked_archived_rows,
            )
            return jsonify({'message': '已归档合同仅超管或群晖超管可修改'}), 403

        current_app.logger.info(
            'AI parse: persisted fullbody by file_path=%s matched_rows=%s blocked_archived_rows=%s chars=%s',
            normalized_storage_path,
            updated_rows,
            blocked_archived_rows,
            len(pdf_text),
        )

    try:
        raw_fields = _minimax_extract_fields(pdf_text)
    except Exception as exc:
        _write_ai_recognition_log(ai_log_target, f'AI识别失败：AI字段抽取失败，原因={exc}', is_failure=True)
        current_app.logger.exception('AI parse: Minimax extraction failed')
        return jsonify({'message': f'AI解析失败: {exc}'}), 500

    if not _has_any_field_value(raw_fields):
        _write_ai_recognition_log(ai_log_target, 'AI识别失败：AI返回结果为空，无法提取字段', is_failure=True)
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
