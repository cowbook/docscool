import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from dotenv import load_dotenv
from synology_api import core_group, core_user


def _str_to_bool(value: Optional[str], default: bool = False) -> bool:
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


def _parse_base_url(base_url: str) -> Tuple[str, str, bool]:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError(f"invalid base url: {base_url}")

    secure = parsed.scheme.lower() == "https"
    port: int
    if parsed.port:
        port = parsed.port
    else:
        port = 5001 if secure else 5000

    return parsed.hostname, str(port), secure


def _print_result(label: str, payload: Dict[str, Any]) -> None:
    success = bool(payload.get("success"))
    code = (payload.get("error") or {}).get("code")
    print(f"[{label}] success={success} error_code={code}")
    print(f"[{label}] payload={json.dumps(payload, ensure_ascii=False)}")


def _run_sdk_call(label: str, func) -> Tuple[str, Dict[str, Any]]:
    try:
        payload = func()
        if isinstance(payload, dict):
            return label, payload
        return label, {"success": False, "error": {"code": "non_dict_payload"}, "data": {"raw": str(payload)}}
    except Exception as exc:
        return label, {
            "success": False,
            "error": {"code": "exception", "message": f"{exc.__class__.__name__}: {exc}"},
            "data": {},
        }


def _extract_usernames(value: Any) -> List[str]:
    out: List[str] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = (item.get("name") or item.get("username") or "").strip()
        else:
            name = ""
        if name:
            out.append(name)
    return out


def _contains_target(payload: Dict[str, Any], target_user: str) -> bool:
    data = payload.get("data") or {}
    users = data.get("users")
    names = _extract_usernames(users)
    if target_user in names:
        return True

    groups = data.get("groups") or []
    for group in groups:
        group_users = _extract_usernames((group or {}).get("users"))
        if target_user in group_users:
            return True

    user_rows = data.get("users") or []
    if isinstance(user_rows, list):
        for row in user_rows:
            if not isinstance(row, dict):
                continue
            name = (row.get("name") or row.get("username") or "").strip()
            if name == target_user:
                return True

    return False


def main() -> int:
    _load_env()

    parser = argparse.ArgumentParser(
        description="Use synology-api SDK to verify if target user is in administrators group.",
    )
    parser.add_argument("--base-url", default=os.getenv("SYNOLOGY_BASE_URL", ""))
    parser.add_argument("--username", default=os.getenv("SYNOLOGY_USERNAME") or os.getenv("SYNOLOGY_ACCOUNT") or "")
    parser.add_argument("--password", default=os.getenv("SYNOLOGY_PASSWORD", ""))
    parser.add_argument("--verify-ssl", action="store_true", default=_str_to_bool(os.getenv("SYNOLOGY_VERIFY_SSL", "false"), False))
    parser.add_argument("--group", default="administrators")
    parser.add_argument("--target-user", default="zhangyan")
    parser.add_argument("--dsm-version", type=int, default=7)
    parser.add_argument("--debug", action="store_true", default=True)
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

    try:
        host, port, secure = _parse_base_url(args.base_url)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("=== Synology SDK Admin Group Probe ===")
    print(f"base_url={args.base_url}")
    print(f"host={host} port={port} secure={secure}")
    print(f"username={args.username}")
    print(f"group={args.group}")
    print(f"target_user={args.target_user}")
    print(f"verify_ssl={args.verify_ssl}")
    print(f"dsm_version={args.dsm_version}")

    group_api = core_group.Group(
        host,
        port,
        args.username,
        args.password,
        secure=secure,
        cert_verify=args.verify_ssl,
        dsm_version=args.dsm_version,
        debug=args.debug,
    )
    user_api = core_user.User(
        host,
        port,
        args.username,
        args.password,
        secure=secure,
        cert_verify=args.verify_ssl,
        dsm_version=args.dsm_version,
        debug=args.debug,
    )

    attempts: List[Tuple[str, Dict[str, Any]]] = []

    # SDK wrappers call underlying SYNO.Core APIs; we print full raw payloads for comparison.
    attempts.append(
        _run_sdk_call(
            "sdk.group.get_users(in_group=True)",
            lambda: group_api.get_users(args.group, True),
        )
    )
    attempts.append(
        _run_sdk_call(
            "sdk.group.get_users(in_group=False)",
            lambda: group_api.get_users(args.group, False),
        )
    )
    attempts.append(
        _run_sdk_call(
            "sdk.group.get_groups(offset=0,limit=5000)",
            lambda: group_api.get_groups(0, 5000, False),
        )
    )
    attempts.append(
        _run_sdk_call(
            "sdk.user.get_user(additional=[description,groups])",
            lambda: user_api.get_user(args.target_user, additional=["description", "groups"]),
        )
    )
    attempts.append(
        _run_sdk_call(
            "sdk.user.get_users(additional=[description,groups])",
            lambda: user_api.get_users(0, 5000, additional=["description", "groups"]),
        )
    )

    hits: List[str] = []
    for idx, (label, payload) in enumerate(attempts, start=1):
        print("\n" + "-" * 80)
        print(f"RUN {idx}/{len(attempts)}: {label}")
        _print_result(label, payload)
        hit = _contains_target(payload, args.target_user)
        print(f"[{label}] contains_{args.target_user}={hit}")
        if hit:
            hits.append(label)

    print("\n" + "=" * 80)
    print("SUMMARY")
    if hits:
        print("SDK paths that returned target user:")
        for item in hits:
            print(f"  - {item}")
        print("RESULT: PASS")
        return 0

    print("No SDK call returned target user in expected group payloads.")
    print("RESULT: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
