import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

TIMEOUT_SECONDS = 30


def _str_to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _load_env() -> None:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates = [
        os.path.join(base_dir, ".env"),
        os.path.join(base_dir, ".env.local"),
        os.path.join(base_dir, ".env.development"),
        os.path.join(os.path.dirname(base_dir), ".env"),
    ]
    for path in candidates:
        if os.path.exists(path):
            load_dotenv(path, override=False)


def _safe_json(resp: requests.Response) -> Dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {}


def _error_code(payload: Dict[str, Any]) -> Optional[int]:
    code = (payload.get("error") or {}).get("code")
    try:
        return int(code) if code is not None else None
    except Exception:
        return None


def _print_request(stage: str, method: str, endpoint: str, params: Dict[str, Any], data: Optional[Dict[str, Any]]) -> None:
    print(f"\n[{stage}] REQUEST")
    print(f"  method={method}")
    print(f"  endpoint={endpoint}")
    print(f"  params={json.dumps(params, ensure_ascii=False)}")
    if data is not None:
        print(f"  data={json.dumps(data, ensure_ascii=False)}")


def _print_response(stage: str, resp: Optional[requests.Response], payload: Dict[str, Any], exc: Optional[Exception]) -> None:
    print(f"[{stage}] RESPONSE")
    if exc is not None:
        print(f"  exception={exc.__class__.__name__}: {exc}")
        return
    if resp is not None:
        print(f"  status_code={resp.status_code}")
    print(f"  success={bool(payload.get('success'))}")
    print(f"  error_code={_error_code(payload)}")
    print(f"  payload={json.dumps(payload, ensure_ascii=False)}")


def _request_json(
    stage: str,
    method: str,
    endpoint: str,
    params: Dict[str, Any],
    data: Optional[Dict[str, Any]],
    verify_ssl: bool,
) -> Tuple[Optional[requests.Response], Dict[str, Any], Optional[Exception]]:
    _print_request(stage, method, endpoint, params, data)

    try:
        if method == "GET":
            resp = requests.get(endpoint, params=params, timeout=TIMEOUT_SECONDS, verify=verify_ssl)
        else:
            resp = requests.post(endpoint, params=params, data=data, timeout=TIMEOUT_SECONDS, verify=verify_ssl)
        resp.raise_for_status()
        payload = _safe_json(resp)
        _print_response(stage, resp, payload, None)
        return resp, payload, None
    except Exception as exc:
        payload = {}
        resp = None
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            resp = exc.response
            payload = _safe_json(resp)
        _print_response(stage, resp, payload, exc)
        return resp, payload, exc


def _login(base_url: str, username: str, password: str, session_name: str, verify_ssl: bool) -> str:
    endpoints = [f"{base_url}/webapi/entry.cgi", f"{base_url}/webapi/auth.cgi"]
    versions = ["7", "6"]

    for endpoint in endpoints:
        for version in versions:
            params = {
                "api": "SYNO.API.Auth",
                "version": version,
                "method": "login",
                "account": username,
                "passwd": password,
                "session": session_name,
                "format": "sid",
            }
            stage = f"login endpoint={endpoint} version={version}"
            _resp, payload, _exc = _request_json(stage, "GET", endpoint, params, None, verify_ssl)
            sid = ((payload.get("data") or {}).get("sid") or "").strip()
            if payload.get("success") and sid:
                print(f"\n[login] SUCCESS sid_len={len(sid)}")
                return sid

    raise RuntimeError("Synology login failed in all endpoint/version attempts")


def _extract_users_from_member_payload(payload: Dict[str, Any]) -> List[str]:
    rows = ((payload.get("data") or {}).get("users") or [])
    out: List[str] = []
    for item in rows:
        if isinstance(item, str):
            value = item.strip()
        else:
            value = (item.get("name") or "").strip()
        if value:
            out.append(value)
    return out


def _extract_users_from_group_payload(payload: Dict[str, Any], group_name: str) -> List[str]:
    groups = ((payload.get("data") or {}).get("groups") or [])
    target = None
    for row in groups:
        if (row.get("name") or "").strip() == group_name:
            target = row
            break
    if target is None and len(groups) == 1:
        target = groups[0]
    if target is None:
        return []

    out: List[str] = []
    for item in target.get("users") or []:
        if isinstance(item, str):
            value = item.strip()
        else:
            value = (item.get("name") or "").strip()
        if value:
            out.append(value)
    return out


def _extract_users_from_user_payload(payload: Dict[str, Any], target_group: str, target_user: str) -> List[str]:
    users = ((payload.get("data") or {}).get("users") or [])
    matched: List[str] = []
    for row in users:
        name = (row.get("name") or row.get("username") or "").strip()
        if not name:
            continue

        groups_raw = row.get("groups") or []
        groups: List[str] = []
        for item in groups_raw:
            if isinstance(item, str):
                value = item.strip()
            else:
                value = (item.get("name") or item.get("group_name") or "").strip()
            if value:
                groups.append(value)

        if name == target_user and target_group in groups:
            matched.append(name)
            print(
                f"[user-extractor] target user groups={json.dumps(sorted(set(groups)), ensure_ascii=False)}"
            )
    return matched


def _run_attempt(
    index: int,
    sid: str,
    base_url: str,
    verify_ssl: bool,
    target_group: str,
    target_user: str,
    spec: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    endpoint = f"{base_url}/webapi/entry.cgi"

    params = {
        "api": spec["api"],
        "version": spec["version"],
        "method": spec["method"],
        "_sid": sid,
    }

    stage_prefix = f"attempt#{index} {spec['label']}"
    payload = {}

    if spec["http"] == "GET":
        params.update(spec.get("args") or {})
        _resp, payload, _exc = _request_json(stage_prefix + " GET", "GET", endpoint, params, None, verify_ssl)
    else:
        body = spec.get("args") or {}
        _resp, payload, _exc = _request_json(stage_prefix + " POST", "POST", endpoint, params, body, verify_ssl)

    if spec["extractor"] == "member":
        users = _extract_users_from_member_payload(payload)
    elif spec["extractor"] == "user":
        users = _extract_users_from_user_payload(payload, target_group, target_user)
    else:
        users = _extract_users_from_group_payload(payload, target_group)

    hit = target_user in users
    print(f"[{stage_prefix}] USERS count={len(users)} contains_{target_user}={hit}")
    if users:
        print(f"[{stage_prefix}] sample_users={json.dumps(users[:20], ensure_ascii=False)}")
    return hit, users


def main() -> int:
    _load_env()

    parser = argparse.ArgumentParser(
        description="Enumerate Synology APIs to find which can list administrators group users.",
    )
    parser.add_argument("--base-url", default=os.getenv("SYNOLOGY_BASE_URL", ""))
    parser.add_argument("--username", default=os.getenv("SYNOLOGY_USERNAME") or os.getenv("SYNOLOGY_ACCOUNT") or "")
    parser.add_argument("--password", default=os.getenv("SYNOLOGY_PASSWORD", ""))
    parser.add_argument("--session", default=os.getenv("SYNOLOGY_AUTH_SESSION", "DocsCoolUpload"))
    parser.add_argument("--verify-ssl", action="store_true", default=_str_to_bool(os.getenv("SYNOLOGY_VERIFY_SSL", "false"), False))
    parser.add_argument("--group", default="administrators")
    parser.add_argument("--target-user", default="zhangyan")
    args = parser.parse_args()

    if not args.base_url:
        print("ERROR: missing base url; set SYNOLOGY_BASE_URL in .env or pass --base-url")
        return 2
    if not args.username:
        print("ERROR: missing username; set SYNOLOGY_USERNAME/SYNOLOGY_ACCOUNT or pass --username")
        return 2
    if not args.password:
        print("ERROR: missing password; set SYNOLOGY_PASSWORD or pass --password")
        return 2

    base_url = args.base_url.rstrip("/")

    print("=== Synology Admin Group API Enumerator ===")
    print(f"base_url={base_url}")
    print(f"username={args.username}")
    print(f"group={args.group}")
    print(f"target_user={args.target_user}")
    print(f"verify_ssl={args.verify_ssl}")

    sid = _login(base_url, args.username, args.password, args.session, args.verify_ssl)

    specs: List[Dict[str, Any]] = [
        {
            "label": "member.get_users.in_group=true.GET",
            "http": "GET",
            "api": "SYNO.Core.Group.Member",
            "version": "1",
            "method": "get_users",
            "args": {"group": args.group, "in_group": "true"},
            "extractor": "member",
        },
        {
            "label": "member.get_users.in_group=1.GET",
            "http": "GET",
            "api": "SYNO.Core.Group.Member",
            "version": "1",
            "method": "get_users",
            "args": {"group": args.group, "in_group": "1"},
            "extractor": "member",
        },
        {
            "label": "member.get_users.in_group=true.POST",
            "http": "POST",
            "api": "SYNO.Core.Group.Member",
            "version": "1",
            "method": "get_users",
            "args": {"group": args.group, "in_group": "true"},
            "extractor": "member",
        },
        {
            "label": "group.get.name=plain.GET",
            "http": "GET",
            "api": "SYNO.Core.Group",
            "version": "1",
            "method": "get",
            "args": {"name": args.group, "additional": '["users","description"]'},
            "extractor": "group",
        },
        {
            "label": "group.get.name=json-array.GET",
            "http": "GET",
            "api": "SYNO.Core.Group",
            "version": "1",
            "method": "get",
            "args": {"name": json.dumps([args.group], ensure_ascii=False), "additional": '["users","description"]'},
            "extractor": "group",
        },
        {
            "label": "group.list.GET",
            "http": "GET",
            "api": "SYNO.Core.Group",
            "version": "1",
            "method": "list",
            "args": {"offset": "0", "limit": "5000", "additional": '["users","description"]'},
            "extractor": "group",
        },
        {
            "label": "group.list.POST",
            "http": "POST",
            "api": "SYNO.Core.Group",
            "version": "1",
            "method": "list",
            "args": {"offset": "0", "limit": "5000", "additional": '["users","description"]'},
            "extractor": "group",
        },
        {
            "label": "user.get.name=plain.GET",
            "http": "GET",
            "api": "SYNO.Core.User",
            "version": "1",
            "method": "get",
            "args": {"name": args.target_user, "additional": '["description","groups"]'},
            "extractor": "user",
        },
        {
            "label": "user.get.name=json-array.GET",
            "http": "GET",
            "api": "SYNO.Core.User",
            "version": "1",
            "method": "get",
            "args": {"name": json.dumps([args.target_user], ensure_ascii=False), "additional": '["description","groups"]'},
            "extractor": "user",
        },
        {
            "label": "user.get.name=plain.POST",
            "http": "POST",
            "api": "SYNO.Core.User",
            "version": "1",
            "method": "get",
            "args": {"name": args.target_user, "additional": '["description","groups"]'},
            "extractor": "user",
        },
        {
            "label": "user.list.GET",
            "http": "GET",
            "api": "SYNO.Core.User",
            "version": "1",
            "method": "list",
            "args": {"offset": "0", "limit": "5000", "additional": '["description","groups"]'},
            "extractor": "user",
        },
        {
            "label": "user.list.POST",
            "http": "POST",
            "api": "SYNO.Core.User",
            "version": "1",
            "method": "list",
            "args": {"offset": "0", "limit": "5000", "additional": '["description","groups"]'},
            "extractor": "user",
        },
    ]

    effective: List[str] = []
    for idx, spec in enumerate(specs, start=1):
        print("\n" + "-" * 80)
        print(f"RUN {idx}/{len(specs)}: {spec['label']}")
        hit, _users = _run_attempt(idx, sid, base_url, args.verify_ssl, args.group, args.target_user, spec)
        if hit:
            effective.append(spec["label"])

    print("\n" + "=" * 80)
    print("SUMMARY")
    if effective:
        print("APIs that returned the target user:")
        for item in effective:
            print(f"  - {item}")
        print("RESULT: PASS")
        return 0

    print("No attempted API returned target user in the target group.")
    print("RESULT: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
