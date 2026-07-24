from datetime import datetime, timedelta, timezone
from functools import wraps
from importlib import import_module
from urllib.parse import urlparse

import jwt
from flask import Blueprint, current_app, g, jsonify, request

from .extensions import db
from .models import UserLog, UserPermission


auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

_USER_PASSWORD_CACHE = {}
_QUERY_TOKEN_ALLOWED_ENDPOINTS = {
    'files.get_file_thumbnail',
}


def _extract_request_token() -> str:
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.replace('Bearer ', '', 1).strip()

    # Limited fallback for browser-native asset requests (img/iframe) that cannot set headers.
    if request.method == 'GET' and request.endpoint in _QUERY_TOKEN_ALLOWED_ENDPOINTS:
        token = (request.args.get('token') or '').strip()
        if token:
            return token

    return ''


def _synology_error_message(code: int) -> str:
    mapping = {
        400: '账号或密码错误',
        401: '账号被停用',
        402: '权限不足',
        403: '需要两步验证验证码(OTP)',
        404: '两步验证验证码(OTP)错误',
        407: 'IP 被阻止，请稍后重试',
    }
    return mapping.get(code, f'Synology authentication failed (code={code})')


def _synology_login(username: str, password: str, otp_code: str = ''):
    success, message, _session = _synology_login_with_sid(username, password, otp_code)
    return success, message


def _synology_error_code_from_exception(exc: Exception):
    code = getattr(exc, 'error_code', None)
    try:
        return int(code) if code is not None else None
    except Exception:
        return None


def _get_synology_user_client(username: str, password: str, otp_code: str = ''):
    base_url = (current_app.config.get('SYNOLOGY_BASE_URL') or '').strip()
    if not base_url:
        raise RuntimeError('SYNOLOGY_BASE_URL is empty')

    parsed = urlparse(base_url)
    if not parsed.hostname:
        raise RuntimeError(f'Invalid SYNOLOGY_BASE_URL: {base_url}')

    secure = parsed.scheme.lower() == 'https'
    port = parsed.port or (5001 if secure else 5000)

    core_user = import_module('synology_api.core_user')
    # synology-api 0.8.2 复用全局 shared_session，会导致不同 application 的 API 列表串用。
    # 这里强制重置，确保当前客户端按 User/Core 场景重新拉取 API 列表。
    base_api = import_module('synology_api.base_api')
    base_api.BaseApi.shared_session = None
    return core_user.User(
        parsed.hostname,
        str(port),
        username,
        password,
        secure=secure,
        cert_verify=bool(current_app.config.get('SYNOLOGY_VERIFY_SSL', False)),
        dsm_version=int(current_app.config.get('SYNOLOGY_DSM_VERSION', 7)),
        debug=False,
        otp_code=otp_code or None,
        application=current_app.config.get('SYNOLOGY_AUTH_SESSION') or 'Core',
    )


def _synology_login_with_sid(username: str, password: str, otp_code: str = ''):
    try:
        current_app.logger.info(
            '[auth] synology sdk login attempt: user=%s has_otp=%s',
            username,
            bool(otp_code),
        )
        client = _get_synology_user_client(username, password, otp_code)
        current_app.logger.info('[auth] synology sdk login succeeded: user=%s', username)
        return True, '', {'client': client}
    except Exception as exc:
        code = _synology_error_code_from_exception(exc)
        if code is not None:
            message = _synology_error_message(code)
        else:
            message = f'Synology SDK login failed: {exc.__class__.__name__}'
        current_app.logger.warning(
            '[auth] synology sdk login failed: user=%s code=%s exc=%s message=%s',
            username,
            code,
            exc.__class__.__name__,
            str(exc),
        )
        return False, message, None


def _synology_change_own_password(username: str, current_password: str, new_password: str):
    current_app.logger.info(
        '[auth] change-password requested: user=%s current_len=%s new_len=%s',
        username,
        len(current_password),
        len(new_password),
    )
    ok, message, session = _synology_login_with_sid(username, current_password)
    if not ok:
        current_app.logger.warning('[auth] change-password aborted: user=%s login_with_current_password_failed msg=%s', username, message)
        return False, message

    user_api = session['client']
    last_message = 'Synology password change failed'

    try:
        current_app.logger.info('[auth] change-password sdk modify_user attempt: user=%s', username)
        payload = user_api.modify_user(
            name=username,
            new_name=username,
            password=new_password,
        )

        if not payload.get('success'):
            error = payload.get('error') or {}
            code = error.get('code')
            if code is not None:
                last_message = f'密码修改失败 (code={code})'
            else:
                last_message = '密码修改失败，请稍后重试'
            current_app.logger.warning(
                '[auth] change-password sdk modify_user failed: user=%s code=%s error=%s',
                username,
                code,
                error,
            )
            return False, last_message

        verify_ok, verify_message = _synology_login(username, new_password)
        if not verify_ok:
            current_app.logger.warning(
                '[auth] change-password verification failed: user=%s new_password_login_ok=false msg=%s',
                username,
                verify_message,
            )
            return False, f'密码修改未生效：{verify_message or "新密码校验失败"}'

        current_app.logger.info('[auth] change-password verification passed: user=%s new_password_login_ok=true', username)

        old_password_still_valid, old_password_message = _synology_login(username, current_password)
        if old_password_still_valid:
            current_app.logger.warning(
                '[auth] change-password anomaly: user=%s old_password_still_valid=true',
                username,
            )
        else:
            current_app.logger.info(
                '[auth] change-password old-password check: user=%s old_password_still_valid=false msg=%s',
                username,
                old_password_message,
            )

        return True, ''
    except Exception as exc:
        code = _synology_error_code_from_exception(exc)
        if code is not None:
            last_message = _synology_error_message(code)
        else:
            last_message = f'Synology SDK request failed: {exc.__class__.__name__}'
        current_app.logger.warning(
            '[auth] change-password sdk exception: user=%s code=%s exc=%s message=%s',
            username,
            code,
            exc.__class__.__name__,
            str(exc),
        )
        return False, last_message
    finally:
        try:
            user_api.logout()
            current_app.logger.info('[auth] change-password sdk logout: user=%s', username)
        except Exception:
            # Best-effort logout only.
            pass


def _encode_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=current_app.config['JWT_EXPIRES_HOURS'])

    payload = {
        'sub': username,
        'iat': int(now.timestamp()),
        'exp': int(expires.timestamp()),
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def _resolve_user_permission_id(username: str) -> int | None:
    login_name = str(username or '').strip()
    if not login_name:
        return None

    row = UserPermission.query.filter_by(login_name=login_name).first()
    return row.id if row else None


def _write_login_user_log(username: str) -> None:
    login_name = str(username or '').strip()
    if not login_name:
        return

    db.session.add(UserLog(
        user_id=_resolve_user_permission_id(login_name),
        operation_module='系统认证',
        operation_target=login_name,
        operation_type='登录',
        detail='用户登录成功',
    ))
    db.session.commit()


def cache_user_password(username: str, password: str) -> None:
    expires = datetime.now(timezone.utc) + timedelta(hours=current_app.config['JWT_EXPIRES_HOURS'])
    _USER_PASSWORD_CACHE[username] = {
        'password': password,
        'expires_at': expires,
    }


def get_cached_user_password(username: str) -> str:
    row = _USER_PASSWORD_CACHE.get(username)
    if not row:
        return ''

    expires_at = row.get('expires_at')
    if not expires_at or datetime.now(timezone.utc) >= expires_at:
        _USER_PASSWORD_CACHE.pop(username, None)
        return ''

    return row.get('password', '')


def decode_token(token: str):
    return jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])


def require_auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = _extract_request_token()
        if not token:
            return jsonify({'message': 'Missing token'}), 401
        try:
            payload = decode_token(token)
        except jwt.PyJWTError:
            return jsonify({'message': 'Invalid token'}), 401

        g.current_user = payload.get('sub')
        if not g.current_user:
            return jsonify({'message': 'Invalid token payload'}), 401

        return func(*args, **kwargs)

    return wrapper


@auth_bp.post('/login')
def login():
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    otp_code = (body.get('otp_code') or '').strip()

    if not username or not password:
        return jsonify({'message': 'username and password are required'}), 400

    success, message = _synology_login(username, password, otp_code)
    if not success:
        return jsonify({'message': message}), 401

    cache_user_password(username, password)

    try:
        _write_login_user_log(username)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('[auth] failed to write login user log: user=%s', username)

    token = _encode_token(username)
    return jsonify({'token': token, 'username': username})


@auth_bp.get('/me')
@require_auth
def me():
    return jsonify({'username': g.current_user})


@auth_bp.post('/change-password')
@require_auth
def change_password():
    body = request.get_json(silent=True) or {}
    current_password = body.get('current_password') or ''
    new_password = body.get('new_password') or ''

    if not current_password or not new_password:
        return jsonify({'message': 'current_password and new_password are required'}), 400

    if len(new_password) < 6:
        return jsonify({'message': '新密码长度至少 6 位'}), 400

    if current_password == new_password:
        return jsonify({'message': '新密码不能与当前密码相同'}), 400

    username = g.current_user
    current_app.logger.info('[auth] change-password endpoint called: user=%s', username)
    success, message = _synology_change_own_password(username, current_password, new_password)
    if not success:
        current_app.logger.warning('[auth] change-password endpoint failed: user=%s msg=%s', username, message)
        return jsonify({'message': message}), 400

    cache_user_password(username, new_password)
    current_app.logger.info('[auth] change-password endpoint success: user=%s', username)
    return jsonify({'message': '密码修改成功'})
