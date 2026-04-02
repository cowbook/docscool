from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
import requests
from flask import Blueprint, current_app, g, jsonify, request


auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

_USER_PASSWORD_CACHE = {}


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
    base_url = current_app.config['SYNOLOGY_BASE_URL']
    if not base_url:
        return False, 'SYNOLOGY_BASE_URL is empty'

    endpoints = [
        f"{base_url}/webapi/auth.cgi",
        f"{base_url}/webapi/entry.cgi",
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
                response = requests.get(
                    endpoint,
                    params=params,
                    timeout=8,
                    verify=current_app.config['SYNOLOGY_VERIFY_SSL'],
                )
                response.raise_for_status()
                payload = response.json()

                if payload.get('success'):
                    return True, ''

                error = payload.get('error') or {}
                code = error.get('code')
                if code is not None:
                    last_message = _synology_error_message(int(code))
                else:
                    last_message = 'Synology authentication failed'
            except requests.RequestException as exc:
                last_message = f'Synology request failed: {exc.__class__.__name__}'

    return False, last_message


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
