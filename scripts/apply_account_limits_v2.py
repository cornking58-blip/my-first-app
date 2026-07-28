from pathlib import Path


def replace_or_skip(path: str, old: str, new: str, label: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    old_count = text.count(old)
    if old_count == 1:
        file_path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"applied: {label}")
        return
    if old_count == 0 and new in text:
        print(f"already applied: {label}")
        return
    raise RuntimeError(f"{label}: old={old_count}, new_present={new in text}")


replace_or_skip(
    "backend/server.py",
    '    "trial": {"ai_requests": 10, "web_requests": 2, "photo_diagnostics": 2},',
    '    "trial": {"ai_requests": 20, "web_requests": 4, "photo_diagnostics": 6},',
    "trial limits",
)

usage_anchor = '''def get_usage_period_key(user: Dict[str, Any], plan: str) -> str:\n    if plan == "trial":\n        started_at = user.get("trial_started_at") or user.get("created_at") or datetime.utcnow()\n        return f"trial:{started_at.strftime('%Y-%m-%d')}"\n    return f"pro:{datetime.utcnow().strftime('%Y-%m')}"\n\n\nasync def reserve_ai_usage'''
usage_replacement = '''def get_usage_period_key(user: Dict[str, Any], plan: str) -> str:\n    if plan == "trial":\n        started_at = user.get("trial_started_at") or user.get("created_at") or datetime.utcnow()\n        return f"trial:{started_at.strftime('%Y-%m-%d')}"\n    return f"pro:{datetime.utcnow().strftime('%Y-%m')}"\n\n\nUSAGE_FIELD_LABELS = {\n    "ai_requests": "AI-запросы",\n    "web_requests": "Поиск в интернете",\n    "photo_diagnostics": "Фотодиагностика",\n}\n\n\nasync def build_usage_snapshot(user: Dict[str, Any]) -> Dict[str, Any]:\n    plan = get_user_access_plan(user)\n    period_ends_at = (\n        user.get("trial_ends_at") if plan == "trial"\n        else user.get("pro_until") if plan == "pro"\n        else None\n    )\n\n    if plan == "owner":\n        return {\n            "plan": plan,\n            "unlimited": True,\n            "period_key": "owner",\n            "period_ends_at": None,\n            "items": {\n                field: {\n                    "label": label,\n                    "used": 0,\n                    "limit": None,\n                    "remaining": None,\n                }\n                for field, label in USAGE_FIELD_LABELS.items()\n            },\n        }\n\n    limits = AI_USAGE_LIMITS.get(plan, {field: 0 for field in USAGE_FIELD_LABELS})\n    usage: Dict[str, Any] = {}\n    period_key = None\n    if plan in AI_USAGE_LIMITS:\n        period_key = get_usage_period_key(user, plan)\n        usage_id = f"{user['id']}:{period_key}"\n        usage = await db.ai_usage.find_one({"_id": usage_id}) or {}\n\n    items = {}\n    for field, label in USAGE_FIELD_LABELS.items():\n        limit = int(limits.get(field, 0))\n        used = max(0, int(usage.get(field, 0) or 0))\n        items[field] = {\n            "label": label,\n            "used": used,\n            "limit": limit,\n            "remaining": max(0, limit - used),\n        }\n\n    return {\n        "plan": plan,\n        "unlimited": False,\n        "period_key": period_key,\n        "period_ends_at": period_ends_at,\n        "items": items,\n    }\n\n\nasync def reserve_ai_usage'''
replace_or_skip("backend/server.py", usage_anchor, usage_replacement, "usage snapshot")

replace_or_skip(
    "backend/server.py",
    '''@api_router.get("/auth/me")\nasync def get_auth_account(current_user: Dict[str, Any] = Depends(require_current_user)):\n    return {"user": serialize_user_account(current_user)}''',
    '''@api_router.get("/auth/me")\nasync def get_auth_account(current_user: Dict[str, Any] = Depends(require_current_user)):\n    return {\n        "user": serialize_user_account(current_user),\n        "usage": await build_usage_snapshot(current_user),\n    }\n\n\n@api_router.get("/auth/usage")\nasync def get_auth_usage(current_user: Dict[str, Any] = Depends(require_current_user)):\n    return {"usage": await build_usage_snapshot(current_user)}''',
    "auth usage endpoint",
)

replace_or_skip(
    "frontend/src/auth/AuthContext.tsx",
    "export type AccessPlan = 'free' | 'trial' | 'pro';",
    "export type AccessPlan = 'free' | 'trial' | 'pro' | 'owner';",
    "owner plan type",
)
replace_or_skip(
    "frontend/src/auth/AuthContext.tsx",
    "export interface AuthUser {\n  id: string;",
    "export interface UsageItem {\n  label: string;\n  used: number;\n  limit: number | null;\n  remaining: number | null;\n}\n\nexport interface UsageSummary {\n  plan: AccessPlan;\n  unlimited: boolean;\n  period_key: string | null;\n  period_ends_at?: string | null;\n  items: Record<'ai_requests' | 'web_requests' | 'photo_diagnostics', UsageItem>;\n}\n\nexport interface AuthUser {\n  id: string;",
    "usage types",
)
replace_or_skip(
    "frontend/src/auth/AuthContext.tsx",
    "    can_use_ai: boolean;\n  };",
    "    can_use_ai: boolean;\n    is_owner?: boolean;\n  };",
    "owner flag",
)
replace_or_skip(
    "frontend/src/auth/AuthContext.tsx",
    "  user: AuthUser | null;\n  requestCode:",
    "  user: AuthUser | null;\n  usage: UsageSummary | null;\n  requestCode:",
    "context usage field",
)
replace_or_skip(
    "frontend/src/auth/AuthContext.tsx",
    "  const [token, setToken] = useState<string | null>(null);\n  const [user, setUser] = useState<AuthUser | null>(null);",
    "  const [token, setToken] = useState<string | null>(null);\n  const [user, setUser] = useState<AuthUser | null>(null);\n  const [usage, setUsage] = useState<UsageSummary | null>(null);",
    "usage state",
)
replace_or_skip(
    "frontend/src/auth/AuthContext.tsx",
    "    setToken(null);\n    setUser(null);",
    "    setToken(null);\n    setUser(null);\n    setUsage(null);",
    "clear usage",
)
replace_or_skip(
    "frontend/src/auth/AuthContext.tsx",
    '''    const response = await axios.get(`${API_URL}/api/auth/me`, {\n      headers: { Authorization: `Bearer ${nextToken}` },\n    });\n    setToken(nextToken);\n    setUser(response.data.user);''',
    '''    const response = await axios.get(`${API_URL}/api/auth/me`, {\n      headers: { Authorization: `Bearer ${nextToken}` },\n    });\n    setToken(nextToken);\n    setUser(response.data.user);\n    setUsage(response.data.usage || null);''',
    "load usage",
)
replace_or_skip(
    "frontend/src/auth/AuthContext.tsx",
    "    await setStoredAuthToken(nextToken);\n    setToken(nextToken);\n    setUser(response.data.user);",
    "    await setStoredAuthToken(nextToken);\n    await loadAccount(nextToken);",
    "verify reload account",
)
replace_or_skip(
    "frontend/src/auth/AuthContext.tsx",
    "    token,\n    user,\n    requestCode,",
    "    token,\n    user,\n    usage,\n    requestCode,",
    "expose usage",
)

replace_or_skip(
    "frontend/src/components/AIAuthGate.tsx",
    "export function AIAuthGate({ onBack }: { onBack: () => void }) {",
    "interface AIAuthGateProps {\n  onBack: () => void;\n  detailsTitle?: string;\n  detailsSubtitle?: string;\n}\n\nexport function AIAuthGate({ onBack, detailsTitle, detailsSubtitle }: AIAuthGateProps) {",
    "auth gate props",
)
replace_or_skip(
    "frontend/src/components/AIAuthGate.tsx",
    "{step === 'details' ? 'Откройте bAIkov AI' : 'Введите код из письма'}",
    "{step === 'details' ? (detailsTitle || 'Откройте bAIkov AI') : 'Введите код из письма'}",
    "auth gate title",
)
replace_or_skip(
    "frontend/src/components/AIAuthGate.tsx",
    "? '5 дней профессионального AI-доступа бесплатно. Банковская карта не нужна.'",
    "? (detailsSubtitle || '5 дней профессионального AI-доступа бесплатно. Банковская карта не нужна.')",
    "auth gate subtitle",
)

replace_or_skip(
    "frontend/app/(tabs)/index.tsx",
    "<TouchableOpacity style={styles.profileButton} activeOpacity={0.8}>",
    "<TouchableOpacity\n              style={styles.profileButton}\n              activeOpacity={0.8}\n              onPress={() => router.push('/account')}\n            >",
    "profile navigation",
)
replace_or_skip(
    "frontend/app/_layout.tsx",
    "          <Stack.Screen name=\"photo-diagnosis\" />",
    "          <Stack.Screen name=\"photo-diagnosis\" />\n          <Stack.Screen name=\"account\" />",
    "account route",
)
