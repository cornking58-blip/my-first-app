import base64
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.photo_diagnosis import (
    MAX_PHOTO_BYTES,
    PHOTO_DIAGNOSIS_SYSTEM_PROMPT,
    validate_photo_data_url,
)


ROOT = Path(__file__).resolve().parents[1]
SERVER_SOURCE = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
PHOTO_SOURCE = (ROOT / "backend" / "photo_diagnosis.py").read_text(encoding="utf-8")
PHOTO_SCREEN = (ROOT / "frontend" / "app" / "photo-diagnosis.tsx").read_text(encoding="utf-8")
HOME_SCREEN = (ROOT / "frontend" / "app" / "(tabs)" / "index.tsx").read_text(encoding="utf-8")
LAYOUT_SOURCE = (ROOT / "frontend" / "app" / "_layout.tsx").read_text(encoding="utf-8")


class PhotoDiagnosisTest(unittest.TestCase):
    def test_valid_jpeg_data_url_is_accepted(self):
        payload = base64.b64encode(b"small-jpeg-test").decode("ascii")
        value = f"data:image/jpeg;base64,{payload}"
        self.assertEqual(validate_photo_data_url(value), value)

    def test_unsupported_image_type_is_rejected(self):
        payload = base64.b64encode(b"gif-test").decode("ascii")
        with self.assertRaises(HTTPException) as context:
            validate_photo_data_url(f"data:image/gif;base64,{payload}")
        self.assertEqual(context.exception.status_code, 400)

    def test_invalid_base64_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            validate_photo_data_url("data:image/jpeg;base64,not-valid-@@@")
        self.assertEqual(context.exception.status_code, 400)

    def test_photo_size_limit_is_defined(self):
        self.assertEqual(MAX_PHOTO_BYTES, 6 * 1024 * 1024)

    def test_prompt_requires_uncertainty_and_field_checks(self):
        self.assertIn("Не выдавай предположение за окончательный диагноз", PHOTO_DIAGNOSIS_SYSTEM_PROMPT)
        self.assertIn("Что проверить в поле", PHOTO_DIAGNOSIS_SYSTEM_PROMPT)
        self.assertIn("Не выдумывай торговые препараты", PHOTO_DIAGNOSIS_SYSTEM_PROMPT)

    def test_openai_request_contains_image_input(self):
        self.assertIn('"type": "input_image"', PHOTO_SOURCE)
        self.assertIn('"detail": "high"', PHOTO_SOURCE)
        self.assertIn("AI_VISION_MODEL", PHOTO_SOURCE)

    def test_endpoint_requires_auth_and_photo_limit(self):
        self.assertIn('@api_router.post("/ai/photo-diagnosis")', SERVER_SOURCE)
        self.assertIn("Depends(require_current_user)", SERVER_SOURCE)
        self.assertIn("reserve_photo_usage", SERVER_SOURCE)
        self.assertIn('field = "photo_diagnostics"', SERVER_SOURCE)
        self.assertIn("rollback_ai_usage(reservation)", SERVER_SOURCE)

    def test_frontend_photo_flow_is_wired(self):
        self.assertIn("expo-image-picker", PHOTO_SCREEN)
        self.assertIn("expo-image-manipulator", PHOTO_SCREEN)
        self.assertIn("/api/ai/photo-diagnosis", PHOTO_SCREEN)
        self.assertIn("router.push('/photo-diagnosis')", HOME_SCREEN)
        self.assertIn('<Stack.Screen name="photo-diagnosis" />', LAYOUT_SOURCE)


if __name__ == "__main__":
    unittest.main()
