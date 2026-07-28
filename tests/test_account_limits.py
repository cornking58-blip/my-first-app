from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
AUTH = (ROOT / "frontend" / "src" / "auth" / "AuthContext.tsx").read_text(encoding="utf-8")
HOME = (ROOT / "frontend" / "app" / "(tabs)" / "index.tsx").read_text(encoding="utf-8")
LAYOUT = (ROOT / "frontend" / "app" / "_layout.tsx").read_text(encoding="utf-8")
ACCOUNT = (ROOT / "frontend" / "app" / "account.tsx").read_text(encoding="utf-8")


class AccountLimitsRegressionTest(unittest.TestCase):
    def test_trial_limits_are_approved_values(self):
        self.assertIn(
            '"trial": {"ai_requests": 20, "web_requests": 4, "photo_diagnostics": 6}',
            SERVER,
        )
        self.assertIn(
            '"pro": {"ai_requests": 80, "web_requests": 10, "photo_diagnostics": 15}',
            SERVER,
        )

    def test_account_endpoint_returns_usage_snapshot(self):
        self.assertIn('async def build_usage_snapshot', SERVER)
        self.assertIn('@api_router.get("/auth/usage")', SERVER)
        self.assertIn('"usage": await build_usage_snapshot(current_user)', SERVER)
        for label in ('AI-запросы', 'Поиск в интернете', 'Фотодиагностика'):
            self.assertIn(label, SERVER)

    def test_frontend_supports_owner_and_usage(self):
        self.assertIn("'owner'", AUTH)
        self.assertIn('usage: UsageSummary | null', AUTH)
        self.assertIn('setUsage(response.data.usage || null)', AUTH)

    def test_profile_opens_account(self):
        self.assertIn("onPress={() => router.push('/account')}", HOME)
        self.assertIn('<Stack.Screen name="account" />', LAYOUT)

    def test_account_shows_status_limits_and_logout(self):
        for text in (
            'Личный кабинет',
            'Текущий статус',
            'itemKey="ai_requests"',
            'itemKey="web_requests"',
            'itemKey="photo_diagnostics"',
            'Оформить bAIkov PRO',
            '740 ₽ в месяц',
            'Выйти из аккаунта',
        ):
            self.assertIn(text, ACCOUNT)


if __name__ == "__main__":
    unittest.main()
