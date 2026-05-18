import json

from flask import current_app, jsonify, request

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


def _synology_get_user_info(sid: str, username: str):

    def _parse_user_row(row: dict):
        description = (row.get('description') or row.get('desc') or '').strip()
        name = (row.get('name') or row.get('username') or username or '').strip()
        return {
            'exists': True,
            'name': name,
            'description': description,
        }

    def _match_user_row(payload: dict):
        users = ((payload.get('data') or {}).get('users') or [])
        for row in users:
            name = (row.get('name') or row.get('username') or '').strip()
            if name == username:
                return row
        return users[0] if len(users) == 1 else None

    attempts = [
        {
            'label': 'get-name-plain',
            'api': 'SYNO.Core.User',
            'version': '1',
            'method': 'get',
            'args': {
                'name': username,
                'additional': '["description"]',
            },
        },
        {
            'label': 'get-name-json-array',
            'api': 'SYNO.Core.User',
            'version': '1',
            'method': 'get',
            'args': {
                'name': json.dumps([username], ensure_ascii=False),
                'additional': '["description"]',
            },
        },
        {
            'label': 'get-self-no-name',
            'api': 'SYNO.Core.User',
            'version': '1',
            'method': 'get',
            'args': {
                'additional': '["description"]',
            },
        },
        {
            'label': 'list-all-users',
            'api': 'SYNO.Core.User',
            'version': '1',
            'method': 'list',
            'args': {
                'offset': '0',
                'limit': '5000',
                'additional': '["description"]',
            },
        },
    ]

    failures = []
    for params in attempts:
        query = {
            'api': params['api'],
            'version': params['version'],
            'method': params['method'],
            **(params.get('args') or {}),
        }

        payload = None
        try:
            current_app.logger.info(
                '[settings/users] synology user lookup GET request: username=%s attempt=%s query=%s',
                username,
                params.get('label'),
                query,
            )
            payload = _synology_api_get(sid, query)
            current_app.logger.info(
                '[settings/users] synology user lookup GET response: username=%s attempt=%s success=%s code=%s users_count=%s',
                username,
                params.get('label'),
                bool(payload and payload.get('success')),
                _synology_error_code(payload or {}),
                len((((payload or {}).get('data') or {}).get('users') or [])),
            )
        except Exception as exc:
            current_app.logger.info(
                '[settings/users] synology user lookup GET exception: username=%s attempt=%s exc=%s',
                username,
                params.get('label'),
                exc.__class__.__name__,
            )
            failures.append({'attempt': params.get('label'), 'stage': 'get-exception'})

        if not payload or not payload.get('success'):
            try:
                current_app.logger.info(
                    '[settings/users] synology user lookup POST request: username=%s attempt=%s args=%s',
                    username,
                    params.get('label'),
                    params.get('args') or {},
                )
                payload = _synology_api_post(
                    sid,
                    {
                        'api': params['api'],
                        'version': params['version'],
                        'method': params['method'],
                    },
                    data=params.get('args') or {},
                )
                current_app.logger.info(
                    '[settings/users] synology user lookup POST response: username=%s attempt=%s success=%s code=%s users_count=%s',
                    username,
                    params.get('label'),
                    bool(payload and payload.get('success')),
                    _synology_error_code(payload or {}),
                    len((((payload or {}).get('data') or {}).get('users') or [])),
                )
            except Exception as exc:
                current_app.logger.info(
                    '[settings/users] synology user lookup POST exception: username=%s attempt=%s exc=%s',
                    username,
                    params.get('label'),
                    exc.__class__.__name__,
                )
                failures.append({'attempt': params.get('label'), 'stage': 'post-exception'})
                payload = None

        if not payload or not payload.get('success'):
            failures.append({
                'attempt': params.get('label'),
                'stage': 'api-failed',
                'code': _synology_error_code(payload or {}),
            })
            continue

        target = _match_user_row(payload)
        if not target:
            continue

        parsed = _parse_user_row(target)
        return parsed

    current_app.logger.warning(
        '[settings/users] synology user lookup exhausted: username=%s failures=%s',
        username,
        failures,
    )

    return {
        'exists': False,
        'description': '',
    }


def _synology_get_group(sid: str, group_name: str):
    def _extract_users_from_group(row: dict):
        users = []
        for item in row.get('users') or []:
            if isinstance(item, str):
                value = item.strip()
            else:
                value = (item.get('name') or '').strip()
            if value:
                users.append(value)
        return users

    def _extract_users(row: dict):
        users = []
        for item in row.get('users') or []:
            if isinstance(item, str):
                value = item.strip()
            else:
                value = (item.get('name') or '').strip()
            if value:
                users.append(value)
        return users

    def _match_group(payload: dict):
        rows = ((payload.get('data') or {}).get('groups') or [])
        for row in rows:
            if (row.get('name') or '').strip() == group_name:
                return row
        return rows[0] if len(rows) == 1 else None

    attempts = [
        {
            'label': 'group-get-name-plain',
            'api': 'SYNO.Core.Group',
            'version': '1',
            'method': 'get',
            'args': {
                'name': group_name,
                'additional': '["users","description"]',
            },
        },
        {
            'label': 'group-get-name-json-array',
            'api': 'SYNO.Core.Group',
            'version': '1',
            'method': 'get',
            'args': {
                'name': json.dumps([group_name], ensure_ascii=False),
                'additional': '["users","description"]',
            },
        },
        {
            'label': 'group-list-all',
            'api': 'SYNO.Core.Group',
            'version': '1',
            'method': 'list',
            'args': {
                'offset': '0',
                'limit': '5000',
                'additional': '["users","description"]',
            },
        },
    ]

    last_payload = None
    for params in attempts:
        query = {
            'api': params['api'],
            'version': params['version'],
            'method': params['method'],
            **(params.get('args') or {}),
        }

        payload = _synology_api_get(sid, query)
        if not payload.get('success'):
            payload = _synology_api_post(
                sid,
                {
                    'api': params['api'],
                    'version': params['version'],
                    'method': params['method'],
                },
                data=params.get('args') or {},
            )

        last_payload = payload
        if not payload.get('success'):
            current_app.logger.warning(
                '[settings/users] synology group lookup failed: group=%s attempt=%s code=%s',
                group_name,
                params.get('label'),
                _synology_error_code(payload),
            )
            continue

        target = _match_group(payload)
        if not target:
            continue

        return {
            'exists': True,
            'users': _extract_users(target),
            'payload': payload,
        }

    return {'exists': False, 'users': [], 'payload': last_payload or {}}


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


def _sync_docscool_membership(sid: str, warnings: list[str]) -> None:
    group_members = _ensure_docscool_group_and_permissions(sid, warnings)
    group_set = {(name or '').strip() for name in group_members if (name or '').strip()}

    db_rows = UserPermission.query.order_by(UserPermission.login_name.asc()).all()
    db_usernames = {(row.login_name or '').strip() for row in db_rows if (row.login_name or '').strip()}

    missing_members = sorted(db_usernames - group_set)
    if not missing_members:
        return

    merged_members = sorted(group_set | db_usernames)
    _synology_set_group_users(sid, DOCSCOOL_GROUP_NAME, merged_members)
    current_app.logger.info(
        '[settings/users] docscool membership sync add-only: added=%s total=%s',
        missing_members,
        len(merged_members),
    )


def _settings_login() -> tuple[str, str]:
    try:
        return _synology_upload_login(), ''
    except PermissionError as exc:
        return '', str(exc)
    except Exception as exc:
        raise RuntimeError(f'无法连接群晖: {exc}')


@contracts_bp.get('/settings/users')
@require_auth
def list_user_permissions():
    warnings = []
    sid, auth_error = _settings_login()
    if auth_error:
        return jsonify({'message': auth_error}), 401
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

    sid, auth_error = _settings_login()
    if auth_error:
        return jsonify({'message': auth_error}), 401
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


@contracts_bp.delete('/settings/users/<int:user_id>')
@require_auth
def delete_user_permission(user_id):
    row = UserPermission.query.get_or_404(user_id)

    sid, auth_error = _settings_login()
    if auth_error:
        return jsonify({'message': auth_error}), 401

    db.session.delete(row)
    db.session.commit()

    warnings = []
    _sync_docscool_membership(sid, warnings)
    return jsonify({'success': True, 'warnings': warnings})

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
