import os
import unittest
from unittest.mock import patch

from backend.supabase_auth import (
    build_supabase_headers,
    get_supabase_admin_key,
    get_supabase_read_key,
)


class SupabaseApiKeyTest(unittest.TestCase):
    def test_secret_key_is_preferred_for_server_operations(self):
        with patch.dict(
            os.environ,
            {
                "SUPABASE_SECRET_KEY": "sb_secret_new",
                "SUPABASE_SERVICE_ROLE_KEY": "legacy-service-role",
                "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_public",
            },
            clear=False,
        ):
            self.assertEqual(get_supabase_admin_key(), "sb_secret_new")
            self.assertEqual(get_supabase_read_key(), "sb_secret_new")

    def test_new_opaque_key_is_sent_only_as_apikey(self):
        headers = build_supabase_headers("sb_secret_new")
        self.assertEqual(headers["apikey"], "sb_secret_new")
        self.assertNotIn("Authorization", headers)

    def test_legacy_jwt_keeps_authorization_header(self):
        headers = build_supabase_headers("eyJlegacy")
        self.assertEqual(headers["Authorization"], "Bearer eyJlegacy")

    def test_prefer_header_is_supported_for_upsert(self):
        headers = build_supabase_headers(
            "sb_secret_new",
            prefer="resolution=merge-duplicates,return=minimal",
        )
        self.assertEqual(
            headers["Prefer"],
            "resolution=merge-duplicates,return=minimal",
        )


if __name__ == "__main__":
    unittest.main()
