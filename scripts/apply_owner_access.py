from pathlib import Path


SERVER_PATH = Path("backend/server.py")
TEST_PATH = Path("tests/test_auth_and_limits.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


server = SERVER_PATH.read_text(encoding="utf-8")

server = replace_once(
    server,
    '''def normalize_auth_email(value: str) -> str:\n    return (value or "").strip().lower()\n\n\n''',
    '''def normalize_auth_email(value: str) -> str:\n    return (value or "").strip().lower()\n\n\ndef get_owner_emails() -> set[str]:\n    raw_value = (\n        os.environ.get("OWNER_EMAILS")\n        or os.environ.get("OWNER_EMAIL")\n        or ""\n    )\n    return {\n        normalize_auth_email(value)\n        for value in re.split(r"[,;\\s]+", raw_value)\n        if value.strip()\n    }\n\n\ndef is_owner_user(user: Dict[str, Any]) -> bool:\n    email = normalize_auth_email(str(user.get("email") or ""))\n    return bool(email and email in get_owner_emails())\n\n\n''',
    "owner email helpers",
)

server = replace_once(
    server,
    '''def get_user_access_plan(user: Dict[str, Any], now: Optional[datetime] = None) -> str:\n    now = now or datetime.utcnow()\n    pro_until = user.get("pro_until")\n''',
    '''def get_user_access_plan(user: Dict[str, Any], now: Optional[datetime] = None) -> str:\n    if is_owner_user(user):\n        return "owner"\n    now = now or datetime.utcnow()\n    pro_until = user.get("pro_until")\n''',
    "owner access plan",
)

server = replace_once(
    server,
    '''            "subscription_status": user.get("subscription_status") or "inactive",\n            "can_use_ai": plan in AI_USAGE_LIMITS,\n''',
    '''            "subscription_status": (\n                "owner" if plan == "owner"\n                else user.get("subscription_status") or "inactive"\n            ),\n            "can_use_ai": plan == "owner" or plan in AI_USAGE_LIMITS,\n            "is_owner": plan == "owner",\n''',
    "serialized owner access",
)

server = replace_once(
    server,
    '''async def reserve_ai_usage(user: Dict[str, Any], use_web_search: bool) -> Tuple[str, str]:\n    plan = get_user_access_plan(user)\n    if plan not in AI_USAGE_LIMITS:\n''',
    '''async def reserve_ai_usage(user: Dict[str, Any], use_web_search: bool) -> Tuple[str, str]:\n    plan = get_user_access_plan(user)\n    if plan == "owner":\n        return "owner", "owner"\n    if plan not in AI_USAGE_LIMITS:\n''',
    "unlimited owner reservation",
)

server = replace_once(
    server,
    '''async def rollback_ai_usage(reservation: Tuple[str, str]) -> None:\n    usage_id, field = reservation\n    await db.ai_usage.update_one(\n''',
    '''async def rollback_ai_usage(reservation: Tuple[str, str]) -> None:\n    usage_id, field = reservation\n    if usage_id == "owner":\n        return\n    await db.ai_usage.update_one(\n''',
    "owner rollback bypass",
)

SERVER_PATH.write_text(server, encoding="utf-8")


tests = TEST_PATH.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '''    def test_chats_migrate_from_device_to_account(self):\n''',
    '''    def test_owner_access_is_unlimited_and_configured_by_environment(self):\n        self.assertIn('os.environ.get("OWNER_EMAILS")', SERVER_SOURCE)\n        self.assertIn('return "owner"', SERVER_SOURCE)\n        self.assertIn('if plan == "owner":', SERVER_SOURCE)\n        self.assertIn('return "owner", "owner"', SERVER_SOURCE)\n        self.assertIn('"is_owner": plan == "owner"', SERVER_SOURCE)\n\n    def test_chats_migrate_from_device_to_account(self):\n''',
    "owner access tests",
)
TEST_PATH.write_text(tests, encoding="utf-8")
