from datetime import datetime, timedelta
from pathlib import Path
import unittest

from backend.payments import (
    PRO_DURATION_DAYS,
    PRO_PRICE_RUB,
    get_pro_usage_period_key,
    normalize_payment_mode,
)


ROOT = Path(__file__).resolve().parents[1]
PAYMENTS = (ROOT / "backend" / "payments.py").read_text(encoding="utf-8")
PAYMENT_SCREEN = (ROOT / "frontend" / "app" / "payment.tsx").read_text(encoding="utf-8")
ACCOUNT = (ROOT / "frontend" / "app" / "account.tsx").read_text(encoding="utf-8")
LAYOUT = (ROOT / "frontend" / "app" / "_layout.tsx").read_text(encoding="utf-8")
SERVER = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")


class PaymentRegressionTest(unittest.TestCase):
    def test_tariff_values(self):
        self.assertEqual(PRO_PRICE_RUB, 740)
        self.assertEqual(PRO_DURATION_DAYS, 30)

    def test_payment_mode_defaults_to_mock(self):
        self.assertEqual(normalize_payment_mode("mock"), "mock")
        self.assertEqual(normalize_payment_mode("yookassa"), "yookassa")
        self.assertEqual(normalize_payment_mode("invalid"), "mock")

    def test_pro_usage_period_changes_every_30_days(self):
        started = datetime(2026, 8, 14, 12, 0, 0)
        user = {"pro_started_at": started}
        first = get_pro_usage_period_key(user, started + timedelta(days=29))
        second = get_pro_usage_period_key(user, started + timedelta(days=30))
        self.assertEqual(first, "pro:2026-08-14")
        self.assertEqual(second, "pro:2026-09-13")

    def test_yookassa_payment_is_created_on_server(self):
        self.assertIn("https://api.yookassa.ru/v3/payments", PAYMENTS)
        self.assertIn('"Idempotence-Key"', PAYMENTS)
        self.assertIn('"capture": True', PAYMENTS)
        self.assertIn('"type": "redirect"', PAYMENTS)

    def test_webhook_rechecks_payment_with_provider(self):
        self.assertIn('body.get("event") != "payment.succeeded"', PAYMENTS)
        self.assertIn("await _get_yookassa_payment(provider_payment_id)", PAYMENTS)
        self.assertIn("_validate_successful_provider_payment", PAYMENTS)

    def test_mock_payment_and_history_exist(self):
        self.assertIn('/mock/{payment_id}/complete', PAYMENTS)
        self.assertIn('/history', PAYMENTS)
        self.assertIn('Подтвердить тестовую оплату', PAYMENT_SCREEN)
        self.assertIn('История платежей', PAYMENT_SCREEN)

    def test_app_routes_and_account_button(self):
        self.assertIn('<Stack.Screen name="payment" />', LAYOUT)
        self.assertIn("router.push('/payment')", ACCOUNT)
        self.assertIn("create_payments_router", SERVER)
        self.assertIn("get_pro_usage_period_key", SERVER)


if __name__ == "__main__":
    unittest.main()
