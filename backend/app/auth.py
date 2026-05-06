from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
import requests
from flask import Blueprint, current_app, g, jsonify, request


auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

_USER_PASSWORD_CACHE = {}
EXTERNAL_API_TIMEOUT_SECONDS = 300


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


def _synology_login_with_sid(username: str, password: str, otp_code: str = ''):
    base_url = current_app.config['SYNOLOGY_BASE_URL']
    if not base_url:
        current_app.logger.warning('[auth] synology login aborted: base url is empty; user=%s', username)
        return False, 'SYNOLOGY_BASE_URL is empty', None

    endpoints = [
        f"{base_url}/webapi/entry.cgi",
        f"{base_url}/webapi/auth.cgi",
    ]
    versions = ['7', '6']
    last_message = 'Synology authentication failed'

    for endpoint in endpoints:
        for version in versions:
            params = {
                'api': 'SYNO.API.Auth',
                'version': version,
                'method': 'login',
                'account': username,
                'passwd': password,
                'session': current_app.config['SYNOLOGY_AUTH_SESSION'],
                'format': 'sid',
            }
            if otp_code:
                params['otp_code'] = otp_code

            try:
                current_app.logger.info(
                    '[auth] synology login attempt: user=%s endpoint=%s version=%s has_otp=%s',
                    username,
                    endpoint,
                    version,
                    bool(otp_code),
                )
                response = requests.get(
                    endpoint,
                    params=params,
                    timeout=EXTERNAL_API_TIMEOUT_SECONDS,
                    verify=current_app.config['SYNOLOGY_VERIFY_SSL'],
                )
                response.raise_for_status()
                payload = response.json()

                if payload.get('success'):
                    sid = ((payload.get('data') or {}).get('sid') or '').strip()
                    if sid:
                        current_app.logger.info(
                            '[auth] synology login succeeded: user=%s endpoint=%s version=%s sid_len=%s',
                            username,
                            endpoint,
                            version,
                            len(sid),
                        )
                        return True, '', {
                            'endpoint': endpoint,
                            'version': version,
                            'sid': sid,
                        }

                    current_app.logger.warning(
                        '[auth] synology login response missing sid: user=%s endpoint=%s version=%s',
                        username,
                        endpoint,
                        version,
                    )
                    last_message = 'Synology authentication succeeded but sid is missing'
                    continue

                error = payload.get('error') or {}
                code = error.get('code')
                if code is not None:
                    current_app.logger.warning(
                        '[auth] synology login failed with code: user=%s endpoint=%s version=%s code=%s',
                        username,
                        endpoint,
                        version,
                        code,
                    )
                    last_message = _synology_error_message(int(code))
                else:
                    current_app.logger.warning(
                        '[auth] synology login failed without error code: user=%s endpoint=%s version=%s payload_keys=%s',
                        username,
                        endpoint,
                        version,
                        list(payload.keys()),
                    )
                    last_message = 'Synology authentication failed'
            except requests.RequestException as exc:
                current_app.logger.warning(
                    '[auth] synology login request exception: user=%s endpoint=%s version=%s exc=%s',
                    username,
                    endpoint,
                    version,
                    exc.__class__.__name__,
                )
                last_message = f'Synology request failed: {exc.__class__.__name__}'

    return False, last_message, None


def _synology_logout(endpoint: str, version: str, sid: str) -> None:
    if not endpoint or not sid:
        return

    params = {
        'api': 'SYNO.API.Auth',
        'version': version,
        'method': 'logout',
        'session': current_app.config['SYNOLOGY_AUTH_SESSION'],
        '_sid': sid,
    }

    try:
        requests.get(
            endpoint,
            params=params,
            timeout=EXTERNAL_API_TIMEOUT_SECONDS,
            verify=current_app.config['SYNOLOGY_VERIFY_SSL'],
        )
    except requests.RequestException:
        # Best-effort logout only.
        return


def _synology_query_api_info(endpoint: str):
    params = {
        'api': 'SYNO.API.Info',
        'version': '1',
        'method': 'query',
        'query': 'SYNO.Core.User,SYNO.Core.User.Password',
    }

    try:
        response = requests.get(
            endpoint,
            params=params,
            timeout=EXTERNAL_API_TIMEOUT_SECONDS,
            verify=current_app.config['SYNOLOGY_VERIFY_SSL'],
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get('success'):
            return {'success': False, 'message': f'query failed: {payload.get("error") or {}}'}

        data = payload.get('data') or {}
        info_map = {}
        for api_name in ('SYNO.Core.User', 'SYNO.Core.User.Password'):
            info = data.get(api_name)
            if info:
                info_map[api_name] = {
                    'path': info.get('path'),
                    'minVersion': info.get('minVersion'),
                    'maxVersion': info.get('maxVersion'),
                    'requestFormat': info.get('requestFormat'),
                }

        return {'success': True, 'apis': info_map}
    except requests.RequestException as exc:
        return {'success': False, 'message': f'request exception: {exc.__class__.__name__}'}


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

    endpoint = session['endpoint']
    version = session['version']
    sid = session['sid']
    last_message = 'Synology password change failed'

    api_info = _synology_query_api_info(endpoint)
    if api_info.get('success'):
        current_app.logger.info('[auth] change-password api-info: user=%s details=%s', username, api_info.get('apis'))
    else:
        current_app.logger.warning('[auth] change-password api-info query failed: user=%s msg=%s', username, api_info.get('message'))

    # Ordered by observed effectiveness in production logs.
    payload_candidates = [
        {
            'api': 'SYNO.Core.User',
            'version': '1',
            'method': 'set',
            'name': username,
            'password': new_password,
            'old_password': current_password,
        },
        {
            'api': 'SYNO.Core.User',
            'version': '1',
            'method': 'set',
            'name': username,
            'passwd': new_password,
            'old_passwd': current_password,
        },
        {
            'api': 'SYNO.Core.User.Password',
            'version': '1',
            'method': 'set',
            'new_password': new_password,
            'old_password': current_password,
        },
        {
            'api': 'SYNO.Core.User.Password',
            'version': '1',
            'method': 'set',
            'passwd': new_password,
            'old_passwd': current_password,
        },
    ]

    try:
        for payload_index, payload in enumerate(payload_candidates, start=1):
            request_payload = {
                **payload,
                '_sid': sid,
            }
            payload_signature = {
                'api': payload.get('api'),
                'version': payload.get('version'),
                'method': payload.get('method'),
                'keys': sorted(payload.keys()),
            }

            try:
                current_app.logger.info(
                    '[auth] change-password attempt: user=%s payload_index=%s http_method=%s signature=%s',
                    username,
                    payload_index,
                    'post',
                    payload_signature,
                )
                response = requests.post(
                    endpoint,
                    data=request_payload,
                    timeout=EXTERNAL_API_TIMEOUT_SECONDS,
                    verify=current_app.config['SYNOLOGY_VERIFY_SSL'],
                )

                response.raise_for_status()
                body = response.json()

                if body.get('success'):
                    current_app.logger.info(
                        '[auth] change-password api returned success: user=%s payload_index=%s http_method=%s body_keys=%s data_keys=%s',
                        username,
                        payload_index,
                        'post',
                        list(body.keys()),
                        list((body.get('data') or {}).keys()),
                    )

                    verify_ok, verify_message = _synology_login(username, new_password)
                    if not verify_ok:
                        current_app.logger.warning(
                            '[auth] change-password verification failed: user=%s new_password_login_ok=false msg=%s',
                            username,
                            verify_message,
                        )
                        last_message = f'密码修改未生效：{verify_message or "新密码校验失败"}'
                        continue

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

                error = body.get('error') or {}
                code = error.get('code')
                if code is not None:
                    current_app.logger.warning(
                        '[auth] change-password api failed: user=%s payload_index=%s http_method=%s code=%s',
                        username,
                        payload_index,
                        'post',
                        code,
                    )
                    last_message = f'密码修改失败 (code={code})'
                else:
                    current_app.logger.warning(
                        '[auth] change-password api failed without code: user=%s payload_index=%s http_method=%s payload_keys=%s',
                        username,
                        payload_index,
                        'post',
                        list(body.keys()),
                    )
                    last_message = '密码修改失败，请稍后重试'
            except requests.RequestException as exc:
                current_app.logger.warning(
                    '[auth] change-password request exception: user=%s payload_index=%s http_method=%s exc=%s',
                    username,
                    payload_index,
                    'post',
                    exc.__class__.__name__,
                )
                last_message = f'Synology request failed: {exc.__class__.__name__}'

        current_app.logger.warning('[auth] change-password all attempts failed: user=%s last_message=%s', username, last_message)
        return False, last_message
    finally:
        current_app.logger.info('[auth] change-password logout sid: user=%s endpoint=%s version=%s', username, endpoint, version)
        _synology_logout(endpoint, version, sid)


def _encode_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=current_app.config['JWT_EXPIRES_HOURS'])

    payload = {
        'sub': username,
        'iat': int(now.timestamp()),
        'exp': int(expires.timestamp()),
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


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
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'message': 'Missing token'}), 401

        token = auth_header.replace('Bearer ', '', 1).strip()
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
