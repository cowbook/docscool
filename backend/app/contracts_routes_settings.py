import json
import re
from importlib import import_module
from urllib.parse import urlparse

from flask import current_app, g, jsonify, request

from .auth import get_cached_user_password, require_auth
from .contracts import contracts_bp
from .contracts_core import (
    CSV_OPTION_DEFAULTS,
    DEFAULT_DEPARTMENT_NAME,
    _get_contract_type_options,
    _get_stamp_tax_rate_mapping,
    _department_dir,
    _get_department_names,
    _get_project_names,
    _list_storage_entries,
)
from .extensions import db
from .models import Contract, Department, ProjectOption, StampTaxRateOption, UserPermission


DOCSCOOL_GROUP_NAME = 'docscool'
PERMISSION_EDIT = 'edit'
PERMISSION_VIEW = 'view'
ROLE_SUPER_ADMIN = 'super_admin'
ROLE_ADMIN = 'admin'
PERMISSION_ALL = '全部'
PERMISSION_VALUES = {PERMISSION_EDIT, PERMISSION_VIEW}
ROLE_VALUES = {ROLE_SUPER_ADMIN, ROLE_ADMIN}
ADD_DELETE_ALLOW_LOGIN_NAMES = {'zhangyan'}
NEW_USER_LOGIN_NAME_PATTERN = re.compile(r'^[a-z0-9_]+$')
NEW_USER_PASSWORD_PATTERN = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d\s])[\S]{8,}$')


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


def _normalize_permission_items(items):
    normalized = []
    if not isinstance(items, list):
        return normalized

    for item in items:
        if not isinstance(item, dict):
            continue
        permission = str(item.get('permission') or '').strip()
        if permission not in PERMISSION_VALUES:
            continue

        departments = _format_department_text(item.get('departments') or '').split(',') if item.get('departments') else []
        folders = _format_department_text(item.get('folders') or '').split(',') if item.get('folders') else []

        if isinstance(item.get('departments'), list):
            departments = _format_department_text(item.get('departments')).split(',') if item.get('departments') else []
        if isinstance(item.get('folders'), list):
            folders = _format_department_text(item.get('folders')).split(',') if item.get('folders') else []

        normalized.append({
            'permission': permission,
            'departments': [d for d in departments if d],
            'folders': [f for f in folders if f],
        })

    return normalized


def _extract_permission_items_from_body(body: dict):
    return _normalize_permission_items(body.get('permission_list'))


def _normalize_role_value(value: str) -> str:
    role = str(value or ROLE_ADMIN).strip()
    return role if role in ROLE_VALUES else ROLE_ADMIN


def _current_user_role_value() -> str:
    login_name = (getattr(g, 'current_user', '') or '').strip()
    if not login_name:
        return ROLE_ADMIN

    row = UserPermission.query.filter_by(login_name=login_name).first()
    if not row:
        return ROLE_ADMIN

    return _normalize_role_value(getattr(row, 'role', ROLE_ADMIN))


def _require_super_admin_write_permission():
    login_name = (getattr(g, 'current_user', '') or '').strip().lower()
    if _current_user_role_value() == ROLE_SUPER_ADMIN or login_name in ADD_DELETE_ALLOW_LOGIN_NAMES:
        return None
    return jsonify({'message': '仅超管或指定账号允许新增或删除'}), 403


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


def _validate_new_user_login_name(login_name: str) -> str:
    value = (login_name or '').strip()
    if not value:
        raise ValueError('登录名不能为空')
    if len(value) > 128:
        raise ValueError('登录名最多128个字符')
    if not NEW_USER_LOGIN_NAME_PATTERN.fullmatch(value):
        raise ValueError('登录名仅允许连续的小写英文字母、数字和下划线')
    return value


def _validate_new_user_password(password: str) -> str:
    value = (password or '').strip()
    if not value:
        raise ValueError('密码不能为空')
    if not NEW_USER_PASSWORD_PATTERN.fullmatch(value):
        raise ValueError('密码必须为8位以上且包含大小写字母、数字和特殊字符')
    return value


def _ensure_password_not_contains_user_info(password: str, login_name: str, display_name: str) -> None:
    password_text = (password or '').strip().lower()
    if not password_text:
        raise ValueError('密码不能为空')

    blocked_terms = []
    for raw_value in (login_name, display_name):
        value = (raw_value or '').strip().lower()
        if value:
            blocked_terms.append(value)

    for term in blocked_terms:
        normalized_term = ''.join(term.split())
        if not normalized_term:
            continue
        if normalized_term in password_text.replace(' ', ''):
            raise ValueError('密码不能包含登录名或姓名描述')


def _synology_error_code(payload: dict):
    code = (payload.get('error') or {}).get('code')
    try:
        return int(code) if code is not None else None
    except Exception:
        return None


def _synology_error_message(payload: dict, default: str = 'unknown') -> str:
    error = payload.get('error') or {}
    message = (error.get('message') or '').strip()
    code = _synology_error_code(payload)

    # Prefer explicit vendor message when available and meaningful.
    if message and message not in {'CoreError:', 'CoreError: '}:
        return message

    code_map = {
        119: '会话无效或已过期，请重试',
        3103: '用户参数不符合群晖策略(可能是用户名/密码策略限制)',
        3106: '群晖中不存在该用户',
        3206: '群组已存在或无法创建(请检查群组配置)',
    }
    if code in code_map:
        return code_map[code]

    return f'error_code={code}' if code is not None else default


def _sdk_error_payload(exc: Exception) -> dict:
    code = getattr(exc, 'error_code', None)
    return {
        'success': False,
        'error': {
            'code': code if code is not None else 'exception',
            'message': f'{exc.__class__.__name__}: {exc!s}',
        },
        'data': {},
    }


def _synology_payload_detail(payload: dict, default_prefix: str = 'synology-api error') -> str:
    error = payload.get('error') or {}
    code = error.get('code')
    message = (error.get('message') or '').strip()
    data = payload.get('data') or {}

    fragments = []
    if default_prefix:
        fragments.append(default_prefix)
    if code is not None:
        fragments.append(f'code={code}')
    if message:
        fragments.append(f'message={message}')
    if data:
        fragments.append(f'data={json.dumps(data, ensure_ascii=False)}')

    return ' | '.join(fragments) if fragments else default_prefix


def _is_group_api_unavailable(payload: dict = None, exc: Exception = None) -> bool:
    snippets = []
    if payload:
        try:
            snippets.append(json.dumps(payload, ensure_ascii=False, default=str))
        except Exception:
            snippets.append(str(payload))
    if exc is not None:
        snippets.append(str(exc))

    text = ' | '.join(snippets)
    if not text:
        return False

    return (
        'SYNO.Core.Group' in text
        or 'SYNO.Core.Group.Member' in text
        or 'KeyError' in text and 'Group' in text
    )


def _is_user_api_unavailable(payload: dict = None, exc: Exception = None) -> bool:
    snippets = []
    if payload:
        try:
            snippets.append(json.dumps(payload, ensure_ascii=False, default=str))
        except Exception:
            snippets.append(str(payload))
    if exc is not None:
        snippets.append(str(exc))

    text = ' | '.join(snippets)
    if not text:
        return False

    return (
        'SYNO.Core.User' in text
        or 'KeyError' in text and 'User' in text
    )


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

    # synology-api 0.8.2 会复用全局 shared_session，先重置避免跨 application 的 API 列表串用。
    base_api = import_module('synology_api.base_api')
    base_api.BaseApi.shared_session = None

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

    try:
        payload_preview = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        payload_preview = str(payload)
    if len(payload_preview) > 2000:
        payload_preview = f'{payload_preview[:2000]}...<truncated>'

    data = payload.get('data') or {}
    users = data.get('users') if isinstance(data.get('users'), list) else []
    groups = data.get('groups') if isinstance(data.get('groups'), list) else []
    current_app.logger.info(
        '[settings/users] synology sdk call result: label=%s success=%s code=%s users_count=%s groups_count=%s payload=%s',
        label,
        bool(payload.get('success')),
        _synology_error_code(payload),
        len(users),
        len(groups),
        payload_preview,
    )
    return payload


def _sdk_call_with_client_refresh(label: str, call_factory, retry_codes: set[int] = None, max_attempts: int = 2):
    retry_codes = retry_codes or {119}
    max_attempts = max(1, int(max_attempts or 1))

    last_payload = {'success': False, 'error': {'code': 'unknown', 'message': 'no-attempt'}}
    for attempt in range(1, max_attempts + 1):
        operator, group_api, user_api = _get_synology_sdk_clients()
        payload = _sdk_call(
            f'{label} attempt={attempt} operator={operator}',
            lambda: call_factory(group_api, user_api, operator),
        )
        last_payload = payload

        code = _synology_error_code(payload or {})
        if payload.get('success') or code not in retry_codes or attempt >= max_attempts:
            return payload

        current_app.logger.info(
            '[settings/users] sdk call retry scheduled: label=%s attempt=%s code=%s',
            label,
            attempt,
            code,
        )

    return last_payload


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
        payload = _sdk_call_with_client_refresh(
            f'user.get_user name={username}',
            lambda _group_api, user_api, _operator: user_api.get_user(username, additional=['description']),
        )
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
            'api_unavailable': _is_user_api_unavailable(exc=exc),
        }

    if payload.get('success'):
        target = _match_user_row(payload)
        if target:
            return _parse_user_row(target)
    if _is_user_api_unavailable(payload=payload):
        return {
            'exists': False,
            'description': '',
            'api_unavailable': True,
        }

    payload = _sdk_call_with_client_refresh(
        f'user.get_users name={username}',
        lambda _group_api, user_api, _operator: user_api.get_users(0, 5000, additional=['description']),
    )
    if payload.get('success'):
        target = _match_user_row(payload)
        if target:
            return _parse_user_row(target)
    if _is_user_api_unavailable(payload=payload):
        return {
            'exists': False,
            'description': '',
            'api_unavailable': True,
        }

    current_app.logger.warning('[settings/users] synology user lookup exhausted via sdk: username=%s', username)

    return {
        'exists': False,
        'description': '',
        'api_unavailable': False,
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
        groups_payload = _sdk_call_with_client_refresh(
            f'group.get_groups name={group_name}',
            lambda group_api, _user_api, _operator: group_api.get_groups(0, 5000, False),
        )
        member_payload = _sdk_call_with_client_refresh(
            f'group.get_users.in_group=true name={group_name}',
            lambda group_api, _user_api, _operator: group_api.get_users(group_name, True),
        )
    except Exception as exc:
        current_app.logger.warning(
            '[settings/users] synology sdk init failed: lookup_group=%s exc=%s message=%s',
            group_name,
            exc.__class__.__name__,
            str(exc),
        )
        return {'exists': False, 'users': [], 'payload': _sdk_error_payload(exc)}

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
    payload = _sdk_call_with_client_refresh(
        f'group.create name={group_name}',
        lambda group_api, _user_api, _operator: group_api.create(group_name, 'DocsCool 系统用户权限组'),
    )
    if payload.get('success'):
        return
    raise RuntimeError(_synology_error_message(payload, 'auth'))


def _synology_get_group_member_users(sid: str, group_name: str) -> tuple[list[str], dict]:
    _ = sid
    try:
        payload = _sdk_call_with_client_refresh(
            f'group.get_users.in_group=true group={group_name}',
            lambda group_api, _user_api, _operator: group_api.get_users(group_name, True),
        )
    except Exception as exc:
        return [], _sdk_error_payload(exc)

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
    payload = _sdk_call_with_client_refresh(
        f'group.add_users group={group_name} count={len(normalized)}',
        lambda group_api, _user_api, _operator: group_api.add_users(group_name, normalized),
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


def _synology_reset_user_password(sid: str, login_name: str, new_password: str) -> None:
    _ = sid
    operator, _group_api, user_api = _get_synology_sdk_clients()
    payload = _sdk_call(
        f'user.reset_password target={login_name} operator={operator}',
        lambda: user_api.modify_user(
            name=login_name,
            new_name=login_name,
            password=new_password,
        ),
    )
    if payload.get('success'):
        return

    code = _synology_error_code(payload)
    if code == 3106:
        raise LookupError('群晖中不存在该用户')
    raise RuntimeError(_synology_error_message(payload, 'auth'))


def _synology_update_user_description(sid: str, login_name: str, description: str) -> None:
    _ = sid
    operator, _group_api, user_api = _get_synology_sdk_clients()
    payload = _sdk_call(
        f'user.update_description target={login_name} operator={operator}',
        lambda: user_api.modify_user(
            name=login_name,
            new_name=login_name,
            description=description,
        ),
    )
    if payload.get('success'):
        return

    code = _synology_error_code(payload)
    if code == 3106:
        raise LookupError('群晖中不存在该用户')
    raise RuntimeError(_synology_payload_detail(payload, '更新群晖用户描述失败'))


def _synology_remove_user_from_group(sid: str, login_name: str, group_name: str = DOCSCOOL_GROUP_NAME) -> None:
    _ = sid
    operator, group_api, _user_api = _get_synology_sdk_clients()
    payload = _sdk_call(
        f'group.remove_users group={group_name} user={login_name} operator={operator}',
        lambda: group_api.remove_users(group_name, [login_name]),
    )
    if payload.get('success'):
        return

    code = _synology_error_code(payload)
    if code == 3106:
        raise LookupError('群晖中不存在该用户')
    raise RuntimeError(_synology_payload_detail(payload, '从群晖用户组移除用户失败'))


def _synology_create_user_and_join_group(sid: str, login_name: str, display_name: str, password: str) -> None:
    _ = sid
    operator, group_api, user_api = _get_synology_sdk_clients()
    current_app.logger.info(
        '[settings/users] create user start: operator=%s login_name=%s display_name=%s',
        operator,
        login_name,
        display_name,
    )

    ensure_payload = _sdk_call(
        f'group.ensure name={DOCSCOOL_GROUP_NAME} operator={operator}',
        lambda: group_api.get_users(DOCSCOOL_GROUP_NAME, True),
    )
    if not ensure_payload.get('success'):
        _sdk_call(
            f'group.ensure-create name={DOCSCOOL_GROUP_NAME} operator={operator}',
            lambda: group_api.create(DOCSCOOL_GROUP_NAME, 'DocsCool 系统用户权限组'),
        )

    create_payload = _sdk_call(
        f'user.create name={login_name} operator={operator}',
        lambda: user_api.create_user(
            name=login_name,
            password=password,
            description=display_name,
        ),
    )
    if not create_payload.get('success'):
        raise RuntimeError(_synology_payload_detail(create_payload, '创建群晖用户失败'))

    try:
        group_payload = _sdk_call(
            f'group.add_users name={DOCSCOOL_GROUP_NAME} user={login_name} operator={operator}',
            lambda: group_api.add_users(DOCSCOOL_GROUP_NAME, [login_name]),
        )
        if not group_payload.get('success'):
            raise RuntimeError(_synology_payload_detail(group_payload, '创建群晖用户后加入用户组失败'))
    except Exception:
        _sdk_call(
            f'user.delete rollback name={login_name} operator={operator}',
            lambda: user_api.delete_user(login_name),
        )
        raise


def _ensure_docscool_group_and_permissions(sid: str, warnings: list[str]) -> list[str]:
    group_info = _synology_get_group(sid, DOCSCOOL_GROUP_NAME)
    current_app.logger.info(
        '[settings/users] ensure-docscool-group: initial exists=%s users_count=%s payload=%s',
        bool(group_info.get('exists')),
        len(group_info.get('users') or []),
        json.dumps(group_info.get('payload') or {}, ensure_ascii=False, default=str),
    )

    if _is_group_api_unavailable(payload=group_info.get('payload') or {}):
        warnings.append('DSM 当前环境不支持群组管理 API(SYNO.Core.Group*)，已跳过 docscool 用户组同步')
        current_app.logger.warning(
            '[settings/users] ensure-docscool-group degraded: group api unavailable payload=%s',
            json.dumps(group_info.get('payload') or {}, ensure_ascii=False, default=str),
        )
        return list(group_info.get('users') or [])


    
    if not group_info.get('exists'):
        try:
            _synology_create_group(sid, DOCSCOOL_GROUP_NAME)
        except Exception as exc:
            if _is_group_api_unavailable(exc=exc):
                warnings.append('DSM 当前环境不支持创建群组 API(SYNO.Core.Group)，已跳过 docscool 用户组创建')
                current_app.logger.warning(
                    '[settings/users] ensure-docscool-group degraded: create unavailable exc=%s message=%s',
                    exc.__class__.__name__,
                    str(exc),
                )
                return list(group_info.get('users') or [])
            raise
        _try_grant_storage_root_edit_permission(sid, DOCSCOOL_GROUP_NAME, warnings)
        group_info = _synology_get_group(sid, DOCSCOOL_GROUP_NAME)
        current_app.logger.info(
            '[settings/users] ensure-docscool-group: after-create exists=%s users_count=%s payload=%s',
            bool(group_info.get('exists')),
            len(group_info.get('users') or []),
            json.dumps(group_info.get('payload') or {}, ensure_ascii=False, default=str),
        )

        if _is_group_api_unavailable(payload=group_info.get('payload') or {}):
            warnings.append('DSM 当前环境不支持群组查询 API(SYNO.Core.Group.Member)，已跳过 docscool 用户组成员校验')
            current_app.logger.warning(
                '[settings/users] ensure-docscool-group degraded: after-create group api unavailable payload=%s',
                json.dumps(group_info.get('payload') or {}, ensure_ascii=False, default=str),
            )
            return list(group_info.get('users') or [])

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
    try:
        group_members = _ensure_docscool_group_and_permissions(sid, warnings)
    except Exception as exc:
        warnings.append(f'docscool 用户组同步失败，已跳过: {exc}')
        current_app.logger.warning(
            '[settings/users] docscool membership sync degraded: exc=%s message=%s',
            exc.__class__.__name__,
            str(exc),
        )
        return
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

    try:
        _synology_set_group_users(sid, DOCSCOOL_GROUP_NAME, missing_members)
    except Exception as exc:
        if _is_group_api_unavailable(exc=exc):
            warnings.append('DSM 当前环境不支持群组成员写入 API(SYNO.Core.Group.Member)，已跳过 docscool 用户组成员同步')
            current_app.logger.warning(
                '[settings/users] docscool membership sync degraded at add_users: users=%s exc=%s message=%s',
                missing_members,
                exc.__class__.__name__,
                str(exc),
            )
            return
        raise

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

    admin_members, admin_payload = _synology_get_group_member_users(sid, 'administrators')
    if not admin_payload.get('success'):
        code = _synology_error_code(admin_payload)
        if code not in {119}:
            warnings.append(f'群晖 administrators 组成员读取失败(错误码: {code if code is not None else "unknown"})')
    admin_set = {name.strip() for name in admin_members if (name or '').strip()}

    rows = UserPermission.query.order_by(UserPermission.login_name.asc()).all()
    return jsonify({
        'users': [
            {
                **row.to_dict(),
                'is_synology_admin': (row.login_name or '').strip() in admin_set,
            }
            for row in rows
        ],
        'warnings': warnings,
    })


@contracts_bp.get('/settings/users/departments')
@require_auth
def list_user_permission_departments():
    return jsonify({
        'department_options': _department_option_values(),
    })


@contracts_bp.get('/settings/users/folders')
@require_auth
def list_user_permission_folders():
    return jsonify({
        'folder_options': _folder_option_values(),
    })


@contracts_bp.get('/settings/users/current-permission')
@require_auth
def get_current_user_permission():
    login_name = (getattr(g, 'current_user', '') or '').strip()
    if not login_name:
        return jsonify({'message': '未找到当前登录用户'}), 401

    row = UserPermission.query.filter_by(login_name=login_name).first()
    if not row:
        return jsonify({
            'login_name': login_name,
            'role': ROLE_ADMIN,
            'permission': PERMISSION_VIEW,
            'departments': '',
            'department_list': [],
            'folders': '',
            'folder_list': [],
            'permission_list': [],
        })

    return jsonify(row.to_dict())


@contracts_bp.post('/settings/users')
@require_auth
def create_user_permission():
    permission_error = _require_super_admin_write_permission()
    if permission_error:
        return permission_error

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

    warnings = []
    info = _synology_get_user_info(sid, login_name)
    if not info.get('exists'):
        if info.get('api_unavailable'):
            warnings.append('DSM 当前环境不支持用户查询 API(SYNO.Core.User)，已跳过群晖用户存在性校验')
            current_app.logger.warning(
                '[settings/users] create user permission degraded: login_name=%s reason=user-api-unavailable',
                login_name,
            )
        else:
            return jsonify({'message': '群晖中不存在该用户'}), 404

    row = UserPermission(
        login_name=login_name,
        me_added=False,
        description=info.get('description', ''),
        role=ROLE_ADMIN,
    )
    row.set_permission_items([{
        'permission': PERMISSION_VIEW,
        'departments': [],
        'folders': [],
    }])
    db.session.add(row)
    db.session.commit()

    _sync_docscool_membership(sid, warnings)
    return jsonify({'user': row.to_dict(), 'warnings': warnings}), 201


@contracts_bp.post('/settings/users/create-user')
@require_auth
def create_new_user_permission():
    permission_error = _require_super_admin_write_permission()
    if permission_error:
        return permission_error

    body = request.get_json(silent=True) or {}

    try:
        login_name = _validate_new_user_login_name(body.get('login_name'))
        display_name = (body.get('name') or body.get('description') or '').strip()
        role = _normalize_role_value(body.get('role'))
        if len(display_name) > 255:
            return jsonify({'message': '姓名最多255个字符'}), 400
        password = _validate_new_user_password(body.get('password'))
        password_confirm = str(body.get('password_confirm') or body.get('confirm_password') or '').strip()
        if not password_confirm:
            return jsonify({'message': '密码验证不能为空'}), 400
        if password_confirm != password:
            return jsonify({'message': '两次输入的密码不一致'}), 400
        _ensure_password_not_contains_user_info(password, login_name, display_name)
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400

    permission_items = _extract_permission_items_from_body(body)
    if not permission_items:
        return jsonify({'message': 'permission_list is invalid'}), 400

    existing = UserPermission.query.filter_by(login_name=login_name).first()
    if existing:
        return jsonify(existing.to_dict()), 200

    sid, auth_error = _settings_login()
    if auth_error:
        return jsonify({'message': auth_error}), 401

    warnings = []
    try:
        _synology_create_user_and_join_group(sid, login_name, display_name, password)
    except LookupError as exc:
        return jsonify({'message': str(exc)}), 404
    except Exception as exc:
        return jsonify({
            'message': str(exc),
            'synology_error': getattr(exc, 'args', [''])[0] if getattr(exc, 'args', None) else '',
        }), 400

    row = UserPermission(
        login_name=login_name,
        me_added=True,
        description=display_name,
        role=role,
    )
    row.set_permission_items(permission_items)
    try:
        db.session.add(row)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        try:
            _operator, _group_api, user_api = _get_synology_sdk_clients()
            _sdk_call(
                f'user.delete db-rollback name={login_name}',
                lambda: user_api.delete_user(login_name),
            )
        except Exception:
            pass
        return jsonify({'message': f'写入数据库失败: {exc}'}), 500

    _sync_docscool_membership(sid, warnings)
    return jsonify({'user': row.to_dict(), 'warnings': warnings}), 201


@contracts_bp.put('/settings/users/<int:user_id>')
@require_auth
def update_user_permission(user_id):
    row = UserPermission.query.get_or_404(user_id)
    body = request.get_json(silent=True) or {}

    description = str(body.get('description') or '').strip()
    role = _normalize_role_value(body.get('role') if body.get('role') is not None else row.role)
    if len(description) > 255:
        return jsonify({'message': '描述最多255个字符'}), 400

    permission_items = _extract_permission_items_from_body(body)
    if not permission_items:
        return jsonify({'message': 'permission_list is invalid'}), 400

    sid, auth_error = _settings_login()
    if auth_error:
        return jsonify({'message': auth_error}), 401

    old_description = row.description or ''
    try:
        _synology_update_user_description(sid, row.login_name, description)
    except LookupError as exc:
        return jsonify({'message': str(exc)}), 404
    except Exception as exc:
        return jsonify({'message': f'同步群晖用户描述失败: {exc}'}), 400

    row.description = description
    row.role = role
    row.set_permission_items(permission_items)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        try:
            _synology_update_user_description(sid, row.login_name, old_description)
        except Exception:
            pass
        return jsonify({'message': f'写入数据库失败: {exc}'}), 500

    return jsonify(row.to_dict())


@contracts_bp.delete('/settings/users/<int:user_id>')
@require_auth
def delete_user_permission(user_id):
    permission_error = _require_super_admin_write_permission()
    if permission_error:
        return permission_error

    row = UserPermission.query.get_or_404(user_id)

    if not bool(row.me_added):
        return jsonify({'message': '仅允许删除由本系统创建的用户'}), 403

    sid, auth_error = _settings_login()
    if auth_error:
        return jsonify({'message': auth_error}), 401

    try:
        _operator, _group_api, user_api = _get_synology_sdk_clients()
        payload = _sdk_call(
            f'user.delete target={row.login_name}',
            lambda: user_api.delete_user(row.login_name),
        )
        if not payload.get('success'):
            code = _synology_error_code(payload)
            if code == 3106:
                return jsonify({'message': '群晖中不存在该用户'}), 404
            return jsonify({'message': _synology_payload_detail(payload, '删除群晖用户失败')}), 400
    except LookupError as exc:
        return jsonify({'message': str(exc)}), 404
    except Exception as exc:
        return jsonify({'message': f'删除群晖用户失败: {exc}'}), 400

    db.session.delete(row)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({'message': f'写入数据库失败: {exc}'}), 500

    return jsonify({'success': True})


@contracts_bp.post('/settings/users/<int:user_id>/remove')
@require_auth
def remove_user_permission_from_group(user_id):
    permission_error = _require_super_admin_write_permission()
    if permission_error:
        return permission_error

    row = UserPermission.query.get_or_404(user_id)

    sid, auth_error = _settings_login()
    if auth_error:
        return jsonify({'message': auth_error}), 401

    try:
        _synology_remove_user_from_group(sid, row.login_name)
    except LookupError as exc:
        return jsonify({'message': str(exc)}), 404
    except Exception as exc:
        return jsonify({'message': f'从群晖用户组移除失败: {exc}'}), 400

    db.session.delete(row)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        try:
            _synology_set_group_users(sid, DOCSCOOL_GROUP_NAME, [row.login_name])
        except Exception:
            pass
        return jsonify({'message': f'写入数据库失败: {exc}'}), 500

    return jsonify({'success': True})


@contracts_bp.post('/settings/users/<int:user_id>/reset-password')
@require_auth
def reset_user_permission_password(user_id):
    row = UserPermission.query.get_or_404(user_id)
    body = request.get_json(silent=True) or {}

    new_password = str(body.get('password') or '').strip()
    password_confirm = str(body.get('password_confirm') or body.get('confirm_password') or '').strip()
    if not new_password:
        return jsonify({'message': '新密码不能为空'}), 400
    if len(new_password) > 128:
        return jsonify({'message': '新密码长度不能超过128字符'}), 400
    if password_confirm and password_confirm != new_password:
        return jsonify({'message': '两次输入的新密码不一致'}), 400
    try:
        _validate_new_user_password(new_password)
        _ensure_password_not_contains_user_info(new_password, row.login_name, row.description or '')
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400

    sid, auth_error = _settings_login()
    if auth_error:
        return jsonify({'message': auth_error}), 401

    try:
        _synology_reset_user_password(sid, row.login_name, new_password)
    except LookupError as exc:
        return jsonify({'message': str(exc)}), 404
    except Exception as exc:
        return jsonify({'message': f'重设密码失败: {exc}'}), 400

    return jsonify({'success': True})

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


@contracts_bp.get('/settings/stamp-tax-rates')
@require_auth
def list_stamp_tax_rate_settings():
    rows = StampTaxRateOption.query.order_by(StampTaxRateOption.id.asc()).all()
    return jsonify([row.to_dict() for row in rows])


@contracts_bp.post('/settings/stamp-tax-rates')
@require_auth
def create_stamp_tax_rate_setting():
    permission_error = _require_super_admin_write_permission()
    if permission_error:
        return permission_error

    body = request.get_json(silent=True) or {}
    contract_type = (body.get('contract_type') or '').strip()
    tax_rate = (body.get('tax_rate') or '').strip()

    if not contract_type:
        return jsonify({'message': 'contract_type is required'}), 400
    if len(contract_type) > 64:
        return jsonify({'message': '合同类型最多64个字符'}), 400
    if len(tax_rate) > 32:
        return jsonify({'message': '税率最多32个字符'}), 400
    if StampTaxRateOption.query.filter_by(contract_type=contract_type).first():
        return jsonify({'message': '该合同类型已存在'}), 409

    row = StampTaxRateOption(contract_type=contract_type, tax_rate=tax_rate)
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict()), 201


@contracts_bp.put('/settings/stamp-tax-rates/<int:option_id>')
@require_auth
def update_stamp_tax_rate_setting(option_id):
    permission_error = _require_super_admin_write_permission()
    if permission_error:
        return permission_error

    row = StampTaxRateOption.query.get_or_404(option_id)
    body = request.get_json(silent=True) or {}

    contract_type = (body.get('contract_type') or '').strip()
    tax_rate = (body.get('tax_rate') or '').strip()

    if not contract_type:
        return jsonify({'message': 'contract_type is required'}), 400
    if len(contract_type) > 64:
        return jsonify({'message': '合同类型最多64个字符'}), 400
    if len(tax_rate) > 32:
        return jsonify({'message': '税率最多32个字符'}), 400

    duplicate = StampTaxRateOption.query.filter(
        StampTaxRateOption.contract_type == contract_type,
        StampTaxRateOption.id != option_id,
    ).first()
    if duplicate:
        return jsonify({'message': '该合同类型已存在'}), 409

    row.contract_type = contract_type
    row.tax_rate = tax_rate
    db.session.commit()
    return jsonify(row.to_dict())


@contracts_bp.delete('/settings/stamp-tax-rates/<int:option_id>')
@require_auth
def delete_stamp_tax_rate_setting(option_id):
    permission_error = _require_super_admin_write_permission()
    if permission_error:
        return permission_error

    row = StampTaxRateOption.query.get_or_404(option_id)

    in_use = Contract.query.filter(Contract.contract_type == row.contract_type).first()
    if in_use:
        return jsonify({'message': '该合同类型已被合同使用，无法删除'}), 409

    db.session.delete(row)
    db.session.commit()
    return jsonify({'success': True})


@contracts_bp.post('/settings/projects')
@require_auth
def create_project_setting():
    permission_error = _require_super_admin_write_permission()
    if permission_error:
        return permission_error

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
    permission_error = _require_super_admin_write_permission()
    if permission_error:
        return permission_error

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
    payload['contract_type'] = _get_contract_type_options()
    payload['project'] = _get_project_names()
    payload['stamp_tax_rate_by_contract_type'] = _get_stamp_tax_rate_mapping()
    return jsonify(payload)


@contracts_bp.post('/settings/departments')
@require_auth
def create_department_setting():
    permission_error = _require_super_admin_write_permission()
    if permission_error:
        return permission_error

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
    permission_error = _require_super_admin_write_permission()
    if permission_error:
        return permission_error

    row = Department.query.get_or_404(department_id)

    if row.name == DEFAULT_DEPARTMENT_NAME:
        return jsonify({'message': '默认部门“财务部”不允许删除'}), 409

    in_use = Contract.query.filter(Contract.department == row.name).first()
    if in_use:
        return jsonify({'message': '该部门下已有合同，无法删除'}), 409

    db.session.delete(row)
    db.session.commit()
    return jsonify({'success': True})
