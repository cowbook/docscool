import json
from importlib import import_module
from urllib.parse import urlparse

from flask import current_app, g, jsonify, request

from .auth import get_cached_user_password, require_auth
from .contracts import contracts_bp
from .contracts_core import (
    CSV_OPTION_DEFAULTS,
    DEFAULT_DEPARTMENT_NAME,
    STAMP_TAX_RATE_BY_CONTRACT_TYPE,
    _department_dir,
    _get_department_names,
    _get_project_names,
    _list_storage_entries,
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


def _folder_option_values():
    level1_dirs, _files = _list_storage_entries('')
    values = set()

    for level1 in level1_dirs:
        level1_path = (level1.get('path') or '').strip().replace('\\', '/')
        if not level1_path:
            continue

        parts = [part for part in level1_path.split('/') if part]
        if len(parts) != 1:
            continue
        values.add(parts[0])

    return sorted(values)


def _synology_error_code(payload: dict):
    code = (payload.get('error') or {}).get('code')
    try:
        return int(code) if code is not None else None
    except Exception:
        return None


def _synology_error_message(payload: dict, default: str = 'unknown') -> str:
    error = payload.get('error') or {}
    message = (error.get('message') or '').strip()
    if message:
        return message
    code = _synology_error_code(payload)
    return f'error_code={code}' if code is not None else default


def _sdk_error_payload(exc: Exception) -> dict:
    code = getattr(exc, 'error_code', None)
    return {
        'success': False,
        'error': {
            'code': code if code is not None else 'exception',
            'message': f'{exc.__class__.__name__}: {exc}',
        },
        'data': {},
    }


def _get_synology_sdk_clients():
    base_url = (current_app.config.get('SYNOLOGY_BASE_URL') or '').strip()
    if not base_url:
        raise RuntimeError('Missing SYNOLOGY_BASE_URL in .env')

    username = (getattr(g, 'current_user', '') or '').strip()
    if not username:
        raise PermissionError('未找到当前登录用户，请重新登录后重试')

    password = get_cached_user_password(username)
    if not password:
        raise PermissionError('登录凭据已过期，请重新登录后重试')

    parsed = urlparse(base_url)
    if not parsed.hostname:
        raise RuntimeError(f'Invalid SYNOLOGY_BASE_URL: {base_url}')

    secure = parsed.scheme.lower() == 'https'
    port = parsed.port or (5001 if secure else 5000)

    core_group = import_module('synology_api.core_group')
    core_user = import_module('synology_api.core_user')

    common_kwargs = {
        'secure': secure,
        'cert_verify': bool(current_app.config.get('SYNOLOGY_VERIFY_SSL', False)),
        'dsm_version': int(current_app.config.get('SYNOLOGY_DSM_VERSION', 7)),
        'debug': False,
        'application': 'Core',
    }

    group_api = core_group.Group(parsed.hostname, str(port), username, password, **common_kwargs)
    user_api = core_user.User(parsed.hostname, str(port), username, password, **common_kwargs)
    return username, group_api, user_api


def _sdk_call(label: str, func):
    try:
        payload = func()
        if not isinstance(payload, dict):
            payload = {
                'success': False,
                'error': {'code': 'non-dict-payload', 'message': str(payload)},
                'data': {},
            }
    except Exception as exc:
        payload = _sdk_error_payload(exc)
        current_app.logger.info(
            '[settings/users] synology sdk call exception: label=%s exc=%s message=%s code=%s',
            label,
            exc.__class__.__name__,
            str(exc),
            _synology_error_code(payload),
        )

    data = payload.get('data') or {}
    users = data.get('users') if isinstance(data.get('users'), list) else []
    groups = data.get('groups') if isinstance(data.get('groups'), list) else []
    current_app.logger.info(
        '[settings/users] synology sdk call result: label=%s success=%s code=%s users_count=%s groups_count=%s',
        label,
        bool(payload.get('success')),
        _synology_error_code(payload),
        len(users),
        len(groups),
    )
    return payload


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

    _ = sid
    try:
        operator, _group_api, user_api = _get_synology_sdk_clients()
    except Exception as exc:
        current_app.logger.warning(
            '[settings/users] synology sdk init failed: lookup_user=%s operator=%s exc=%s message=%s',
            username,
            (getattr(g, 'current_user', '') or '').strip(),
            exc.__class__.__name__,
            str(exc),
        )
        return {
            'exists': False,
            'description': '',
        }

    payload = _sdk_call(
        f'user.get_user name={username} operator={operator}',
        lambda: user_api.get_user(username, additional=['description']),
    )
    if payload.get('success'):
        target = _match_user_row(payload)
        if target:
            return _parse_user_row(target)

    payload = _sdk_call(
        f'user.get_users name={username} operator={operator}',
        lambda: user_api.get_users(0, 5000, additional=['description']),
    )
    if payload.get('success'):
        target = _match_user_row(payload)
        if target:
            return _parse_user_row(target)

    current_app.logger.warning('[settings/users] synology user lookup exhausted via sdk: username=%s', username)

    return {
        'exists': False,
        'description': '',
    }


def _synology_get_group(sid: str, group_name: str):
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

    _ = sid
    try:
        _operator, group_api, _user_api = _get_synology_sdk_clients()
    except Exception as exc:
        current_app.logger.warning(
            '[settings/users] synology sdk init failed: lookup_group=%s exc=%s message=%s',
            group_name,
            exc.__class__.__name__,
            str(exc),
        )
        return {'exists': False, 'users': [], 'payload': _sdk_error_payload(exc)}

    groups_payload = _sdk_call(
        f'group.get_groups name={group_name}',
        lambda: group_api.get_groups(0, 5000, False),
    )
    member_payload = _sdk_call(
        f'group.get_users.in_group=true name={group_name}',
        lambda: group_api.get_users(group_name, True),
    )

    groups = ((groups_payload.get('data') or {}).get('groups') or [])
    exists = any((row.get('name') or '').strip() == group_name for row in groups)
    if member_payload.get('success'):
        exists = True

    users = _extract_users({'users': ((member_payload.get('data') or {}).get('users') or [])})
    return {
        'exists': exists,
        'users': users,
        'payload': member_payload if member_payload else groups_payload,
    }


def _synology_create_group(sid: str, group_name: str) -> None:
    _ = sid
    _operator, group_api, _user_api = _get_synology_sdk_clients()
    payload = _sdk_call(
        f'group.create name={group_name}',
        lambda: group_api.create(group_name, 'DocsCool 系统用户权限组'),
    )
    if payload.get('success'):
        return
    raise RuntimeError(_synology_error_message(payload, 'auth'))


def _synology_get_group_member_users(sid: str, group_name: str) -> tuple[list[str], dict]:
    _ = sid
    try:
        _operator, group_api, _user_api = _get_synology_sdk_clients()
    except Exception as exc:
        return [], _sdk_error_payload(exc)

    payload = _sdk_call(
        f'group.get_users.in_group=true group={group_name}',
        lambda: group_api.get_users(group_name, True),
    )
    if not payload.get('success'):
        return [], payload

    users = ((payload.get('data') or {}).get('users') or [])
    normalized_users = []
    for item in users:
        if isinstance(item, str):
            value = item.strip()
        else:
            value = (item.get('name') or '').strip()
        if value:
            normalized_users.append(value)
    return normalized_users, payload


def _synology_set_group_users(sid: str, group_name: str, usernames: list[str]) -> None:
    normalized = sorted({(item or '').strip() for item in usernames if (item or '').strip()})
    if not normalized:
        current_app.logger.info(
            '[settings/users] group add users skipped: group=%s reason=no-users',
            group_name,
        )
        return

    expected_set = set(normalized)

    def _verify_membership(stage: str) -> tuple[list[str], bool]:
        try:
            actual_users, verify_payload = _synology_get_group_member_users(sid, group_name)
            actual_set = {(item or '').strip() for item in actual_users if (item or '').strip()}
            missing = sorted(expected_set - actual_set)
            verify_code = _synology_error_code(verify_payload or {})
            current_app.logger.info(
                '[settings/users] group add users verify: stage=%s group=%s expected=%s actual_count=%s missing=%s actual_sample=%s verify_code=%s',
                stage,
                group_name,
                normalized,
                len(actual_set),
                missing,
                sorted(actual_set)[:20],
                verify_code,
            )
            if verify_code == 103:
                current_app.logger.info(
                    '[settings/users] group add users verify unavailable: stage=%s group=%s code=%s',
                    stage,
                    group_name,
                    verify_code,
                )
                return [], False
            return missing, True
        except Exception as exc:
            current_app.logger.info(
                '[settings/users] group add users verify exception: stage=%s group=%s exc=%s message=%s',
                stage,
                group_name,
                exc.__class__.__name__,
                str(exc),
            )
            return list(expected_set), False

    _ = sid
    _operator, group_api, _user_api = _get_synology_sdk_clients()

    payload = _sdk_call(
        f'group.add_users group={group_name} count={len(normalized)}',
        lambda: group_api.add_users(group_name, normalized),
    )
    if not payload.get('success'):
        raise RuntimeError(f"群组添加用户失败: {_synology_error_message(payload or {}, 'auth')}")

    missing, verified = _verify_membership('sdk-group-add_users-after-success')
    if not verified:
        current_app.logger.info(
            '[settings/users] group add users accepted without verification: group=%s users=%s',
            group_name,
            normalized,
        )
        return

    if not missing:
        current_app.logger.info(
            '[settings/users] group add users effective via sdk: group=%s users=%s',
            group_name,
            normalized,
        )
        return

    raise RuntimeError(
        f"群组添加用户后校验失败: group={group_name} missing={missing} requested={normalized}"
    )


def _ensure_docscool_group_and_permissions(sid: str, warnings: list[str]) -> list[str]:
    group_info = _synology_get_group(sid, DOCSCOOL_GROUP_NAME)
    if not group_info.get('exists'):
        _synology_create_group(sid, DOCSCOOL_GROUP_NAME)
        _try_grant_storage_root_edit_permission(sid, DOCSCOOL_GROUP_NAME, warnings)
        group_info = _synology_get_group(sid, DOCSCOOL_GROUP_NAME)

    return list(group_info.get('users') or [])


def _try_grant_storage_root_edit_permission(sid: str, group_name: str, warnings: list[str]) -> None:
    # Best-effort ACL assignment for DSM shared folder. Some DSM builds may not expose this API.
    _ = sid
    storage_root = (current_app.config.get('CONTRACT_STORAGE_ROOT') or '').replace('\\', '/').strip('/')
    share_name = storage_root.split('/')[-1] if storage_root else ''
    if not share_name:
        warnings.append('无法从 CONTRACT_STORAGE_ROOT 解析共享目录名，已跳过授权')
        return

    try:
        _operator, group_api, _user_api = _get_synology_sdk_clients()
    except Exception as exc:
        warnings.append(f'群组目录编辑权限授予未完成(SDK初始化失败: {exc})')
        return

    payload = _sdk_call(
        f'group.set_share_permissions group={group_name} share={share_name}',
        lambda: group_api.set_share_permissions(
            group_name,
            [
                {
                    'name': share_name,
                    'rw': True,
                }
            ],
        ),
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
        current_app.logger.info(
            '[settings/users] docscool membership sync add-only: no-missing-members db_count=%s group_count=%s',
            len(db_usernames),
            len(group_set),
        )
        return

    current_app.logger.info(
        '[settings/users] docscool membership sync add-only: to_add=%s db_count=%s group_count=%s',
        missing_members,
        len(db_usernames),
        len(group_set),
    )

    _synology_set_group_users(sid, DOCSCOOL_GROUP_NAME, missing_members)
    current_app.logger.info(
        '[settings/users] docscool membership sync add-only: added=%s total=%s',
        missing_members,
        len(group_set | db_usernames),
    )


def _settings_login() -> tuple[str, str]:
    try:
        username, _group_api, _user_api = _get_synology_sdk_clients()
        return username, ''
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
        'folder_options': _folder_option_values(),
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
        folders='',
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
    folders = _format_department_text(body.get('folders') or body.get('folder_list') or '')

    row.permission = permission
    row.departments = departments
    row.folders = folders
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
