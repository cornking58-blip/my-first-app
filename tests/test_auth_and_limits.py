import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_SOURCE = (ROOT / "backend" / "server.py").read_text()
AUTH_CONTEXT_SOURCE = (ROOT / "frontend" / "src" / "auth" / "AuthContext.tsx").read_text()
AUTH_GATE_SOURCE = (ROOT / "frontend" / "src" / "components" / "AIAuthGate.tsx").read_text()
ROOT_LAYOUT_SOURCE = (ROOT / "frontend" / "app" / "_layout.tsx").read_text()


class AuthAndLimitsStaticTest(unittest.TestCase):
    def test_email_code_and_account_routes_exist(self):
        self.assertIn('"/auth/request-code"', SERVER_SOURCE)
        self.assertIn('"/auth/verify-code"', SERVER_SOURCE)
        self.assertIn('"/auth/me"', SERVER_SOURCE)
        self.assertIn("code_hash", SERVER_SOURCE)
        auth_code_document = SERVER_SOURCE.split("document = {", 1)[1].split(
            "await db.auth_codes.insert_one(document)", 1
        )[0]
        self.assertNotIn('"code":', auth_code_document)

    def test_agreed_trial_and_limits_are_enforced_server_side(self):
        self.assertIn("TRIAL_DURATION_DAYS = 5", SERVER_SOURCE)
        self.assertIn('"trial": {"ai_requests": 10, "web_requests": 2, "photo_diagnostics": 2}', SERVER_SOURCE)
        self.assertIn('"pro": {"ai_requests": 80, "web_requests": 10, "photo_diagnostics": 15}', SERVER_SOURCE)
        self.assertIn("reserve_ai_usage(current_user, use_web_search)", SERVER_SOURCE)

    def test_chats_migrate_from_device_to_account(self):
        self.assertIn('"client_id": client_id', SERVER_SOURCE)
        self.assertIn('"user_id": user["id"]', SERVER_SOURCE)
        self.assertIn('"migrated_at": now', SERVER_SOURCE)

    def test_optional_marketing_consent_is_recorded(self):
        self.assertIn("marketing_consent: bool = False", SERVER_SOURCE)
        self.assertIn('MARKETING_CONSENT_VERSION = "2026-07-23-v1"', SERVER_SOURCE)
        self.assertIn('"marketing_consent_at"', SERVER_SOURCE)
        self.assertIn('"marketing_consent_version"', SERVER_SOURCE)
        self.assertIn('"marketing_consent_revoked_at"', SERVER_SOURCE)
        self.assertIn("marketing_consent: marketingConsent", AUTH_CONTEXT_SOURCE)
        self.assertIn("Это необязательно", AUTH_GATE_SOURCE)
        self.assertNotIn(
            "marketingConsent) && styles.buttonDisabled",
            AUTH_GATE_SOURCE,
        )

    def test_mobile_session_uses_secure_storage(self):
        self.assertIn("expo-secure-store", AUTH_CONTEXT_SOURCE + AUTH_GATE_SOURCE + (
            ROOT / "frontend" / "src" / "auth" / "sessionStorage.ts"
        ).read_text())
        self.assertIn("<AuthProvider>", ROOT_LAYOUT_SOURCE)
        self.assertIn("5 дней профессионального AI-доступа бесплатно", AUTH_GATE_SOURCE)
        self.assertNotIn("Осталось", AUTH_GATE_SOURCE)


if __name__ == "__main__":
    unittest.main()
