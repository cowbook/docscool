import json

from flask import current_app, g, jsonify, request

from .auth import require_auth
from .contracts import contracts_bp
from .contracts_core import (
    CSV_OPTION_DEFAULTS,
    DEFAULT_DEPARTMENT_NAME,
    STAMP_TAX_RATE_BY_CONTRACT_TYPE,
    _department_dir,
    _get_department_names,
    _get_project_names,
    _synology_api_get,
    _synology_api_post,
    _synology_error_code,
    _synology_error_message,
    _synology_upload_login,
)
from .extensions import db
from .models import Contract, Department, ProjectOption, UserPermission


DOCSCOOL_GROUP_NAME = 'docscool'
ADMIN_GROUP_NAME = 'administrators'
PERMISSION_SUPER_ADMIN = 'super_admin'
PERMISSION_EDIT = 'edit'
PERMISSION_VIEW = 'view'
PERMISSION_VALUES = {PERMISSION_SUPER_ADMIN, PERMISSION_EDIT, PERMISSION_VIEW}


def _format_department_text(values) -> str:
    if isinstance(values, str):
        items = values.split(',')
    elif isinstance(values, list):
        items = values
    else:
        items = []

    normalized = []
    seen = set()
    for item in items:
        value = (item or '').strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)

    return ','.join(normalized)


def _department_option_values():
    fixed = {(row.name or '').strip() for row in Department.query.order_by(Department.name.asc()).all()}

    contract_rows = (
        db.session.query(Contract.department)
        .filter(Contract.department.isnot(None), Contract.department != '')
        .distinct()
        .all()
    )
    dynamic = {(row[0] or '').strip() for row in contract_rows}

    values = [item for item in (fixed | dynamic) if item]
    values.sort()
    return values


def _sync_row_from_synology(row: UserPermission, sid: str, warnings: list[str]) -> bool:
    info = _synology_get_user_info(sid, row.login_name)
    if not info.get('exists'):
        warnings.append(f'用户 {row.login_name} 不存在于群晖，描述未更新')
        return False

    if (row.description or '') != info.get('description', ''):
        row.description = info.get('description', '')
    return True


def _synology_get_user_info(sid: str, username: str):
    payload = _synology_api_get(
        sid,
        {
            'api': 'SYNO.Core.User',
            'version': '1',
            'method': 'get',
            'name': username,
            'additional': '["description","groups"]',
        },
    )
    if not payload.get('success'):
        return {
            'exists': False,
            'description': '',
            'groups': [],
            'raw': payload,
        }

    users = ((payload.get('data') or {}).get('users') or [])
    if not users:
        return {
            'exists': False,
            'description': '',
            'groups': [],
            'raw': payload,
        }

    target = users[0] or {}
    group_rows = target.get('groups') or []
    groups = []
    for item in group_rows:
        if isinstance(item, str):
            value = item.strip()
        else:
            value = (item.get('name') or '').strip()
        if value:
            groups.append(value)

    return {
        'exists': True,
        'description': (target.get('description') or '').strip(),
        'groups': groups,
        'raw': payload,
    }


def _synology_get_group(sid: str, group_name: str):
    payload = _synology_api_get(
        sid,
        {
            'api': 'SYNO.Core.Group',
            'version': '1',
            'method': 'get',
            'name': group_name,
            'additional': '["users","description"]',
        },
    )

    if not payload.get('success'):
        return {'exists': False, 'users': [], 'payload': payload}

    groups = ((payload.get('data') or {}).get('groups') or [])
    if not groups:
        return {'exists': False, 'users': [], 'payload': payload}

    group_row = groups[0] or {}
    users = []
    for item in group_row.get('users') or []:
        if isinstance(item, str):
            value = item.strip()
        else:
            value = (item.get('name') or '').strip()
        if value:
            users.append(value)

    return {'exists': True, 'users': users, 'payload': payload}


def _synology_create_group(sid: str, group_name: str) -> None:
    payload = _synology_api_post(
        sid,
        {
            'api': 'SYNO.Core.Group',
            'version': '1',
            'method': 'create',
        },
        data={
            'name': group_name,
            'description': 'DocsCool 系统用户权限组',
        },
    )
    if payload.get('success'):
        return
    raise RuntimeError(_synology_error_message(payload, 'auth'))


def _synology_set_group_users(sid: str, group_name: str, usernames: list[str]) -> None:
    normalized = sorted({(item or '').strip() for item in usernames if (item or '').strip()})
    payload = _synology_api_post(
        sid,
        {
            'api': 'SYNO.Core.Group',
            'version': '1',
            'method': 'set',
        },
        data={
            'name': group_name,
            'users': json.dumps(normalized, ensure_ascii=False),
        },
    )
    if payload.get('success'):
        return

    payload_add = _synology_api_post(
        sid,
        {
            'api': 'SYNO.Core.Group',
            'version': '1',
            'method': 'set',
        },
        data={
            'name': group_name,
            'add_users': json.dumps(normalized, ensure_ascii=False),
        },
    )
    if payload_add.get('success'):
        return
    raise RuntimeError(_synology_error_message(payload_add, 'auth'))


def _ensure_docscool_group_and_permissions(sid: str, warnings: list[str]) -> list[str]:
    group_info = _synology_get_group(sid, DOCSCOOL_GROUP_NAME)
    if not group_info.get('exists'):
        _synology_create_group(sid, DOCSCOOL_GROUP_NAME)
        _try_grant_storage_root_edit_permission(sid, DOCSCOOL_GROUP_NAME, warnings)
        group_info = _synology_get_group(sid, DOCSCOOL_GROUP_NAME)

    return list(group_info.get('users') or [])


def _try_grant_storage_root_edit_permission(sid: str, group_name: str, warnings: list[str]) -> None:
    # Best-effort ACL assignment for DSM shared folder. Some DSM builds may not expose this API.
    storage_root = (current_app.config.get('CONTRACT_STORAGE_ROOT') or '').replace('\\', '/').strip('/')
    share_name = storage_root.split('/')[-1] if storage_root else ''
    if not share_name:
        warnings.append('无法从 CONTRACT_STORAGE_ROOT 解析共享目录名，已跳过授权')
        return

    payload = _synology_api_post(
        sid,
        {
            'api': 'SYNO.Core.Share',
            'version': '1',
            'method': 'set',
        },
        data={
            'name': share_name,
            'add_privilege': json.dumps([
                {
                    'name': group_name,
                    'rw': True,
                }
            ], ensure_ascii=False),
        },
    )
    if payload.get('success'):
        return

    code = _synology_error_code(payload)
    warnings.append(f'群组目录编辑权限授予未完成(错误码: {code if code is not None else "unknown"})')


def _ensure_current_user_row(sid: str) -> UserPermission:
    username = (g.current_user or '').strip()
    row = UserPermission.query.filter_by(login_name=username).first()
    if row:
        return row

    info = _synology_get_user_info(sid, username)
    groups = set(info.get('groups') or [])
    is_admin = ADMIN_GROUP_NAME in groups

    row = UserPermission(
        login_name=username,
        description=info.get('description', ''),
        permission=PERMISSION_SUPER_ADMIN if is_admin else PERMISSION_VIEW,
        departments='全部' if is_admin else '',
    )
    db.session.add(row)
    db.session.commit()
    return row


def _sync_docscool_membership(sid: str, warnings: list[str]) -> None:
    _ensure_current_user_row(sid)
    group_members = _ensure_docscool_group_and_permissions(sid, warnings)

    db_rows = UserPermission.query.order_by(UserPermission.login_name.asc()).all()
    db_usernames = {row.login_name for row in db_rows}

    changed = False
    for row in db_rows:
        try:
            exists_in_synology = _sync_row_from_synology(row, sid, warnings)
            if exists_in_synology and row.login_name not in group_members:
                group_members.append(row.login_name)
                changed = True
        except Exception as exc:
            warnings.append(f'同步用户 {row.login_name} 到群组失败: {exc}')

    filtered_members = [name for name in group_members if name in db_usernames]
    if len(filtered_members) != len(group_members):
        changed = True

    if changed:
        _synology_set_group_users(sid, DOCSCOOL_GROUP_NAME, filtered_members)

    db.session.commit()


def _settings_login() -> str:
    try:
        return _synology_upload_login()
    except Exception as exc:
        raise RuntimeError(f'无法连接群晖: {exc}')


@contracts_bp.get('/settings/users')
@require_auth
def list_user_permissions():
    warnings = []
    sid = _settings_login()
    _sync_docscool_membership(sid, warnings)

    rows = UserPermission.query.order_by(UserPermission.login_name.asc()).all()
    return jsonify({
        'users': [row.to_dict() for row in rows],
        'department_options': _department_option_values(),
        'warnings': warnings,
    })


@contracts_bp.post('/settings/users')
@require_auth
def create_user_permission():
    body = request.get_json(silent=True) or {}
    login_name = (body.get('login_name') or '').strip()
    if not login_name:
        return jsonify({'message': 'login_name is required'}), 400
    if len(login_name) > 128:
        return jsonify({'message': '登录名称最多128个字符'}), 400

    existing = UserPermission.query.filter_by(login_name=login_name).first()
    if existing:
        return jsonify(existing.to_dict()), 200

    sid = _settings_login()
    info = _synology_get_user_info(sid, login_name)
    if not info.get('exists'):
        return jsonify({'message': '群晖中不存在该用户'}), 404

    row = UserPermission(
        login_name=login_name,
        description=info.get('description', ''),
        permission=PERMISSION_VIEW,
        departments='',
    )
    db.session.add(row)
    db.session.commit()

    warnings = []
    _sync_docscool_membership(sid, warnings)
    return jsonify({'user': row.to_dict(), 'warnings': warnings}), 201


@contracts_bp.put('/settings/users/<int:user_id>')
@require_auth
def update_user_permission(user_id):
    row = UserPermission.query.get_or_404(user_id)
    body = request.get_json(silent=True) or {}

    permission = (body.get('permission') or '').strip()
    if permission not in PERMISSION_VALUES:
        return jsonify({'message': 'permission is invalid'}), 400

    departments = _format_department_text(body.get('departments') or body.get('department_list') or '')

    row.permission = permission
    row.departments = departments
    db.session.commit()

    return jsonify(row.to_dict())

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
    payload = {
        key: list(CSV_OPTION_DEFAULTS.get(key, []))
        for key in CSV_OPTION_DEFAULTS.keys()
    }
    payload['project'] = _get_project_names()
    payload['stamp_tax_rate_by_contract_type'] = STAMP_TAX_RATE_BY_CONTRACT_TYPE
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

    if row.name == DEFAULT_DEPARTMENT_NAME:
        return jsonify({'message': '默认部门“财务部”不允许删除'}), 409

    in_use = Contract.query.filter(Contract.department == row.name).first()
    if in_use:
        return jsonify({'message': '该部门下已有合同，无法删除'}), 409

    db.session.delete(row)
    db.session.commit()
    return jsonify({'success': True})
