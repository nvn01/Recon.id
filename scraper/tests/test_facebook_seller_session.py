from __future__ import annotations

import unittest

from scraper.facebook.facebook_marketplace import DEFAULT_PROFILE_DIR
from scraper.scheduler import build_jobs
from scraper.shared.config import DEFAULT_CONFIG_PATH, load_config


class FacebookSellerSessionTests(unittest.TestCase):
    def test_marketplace_uses_the_persisted_authenticated_profile(self):
        config = load_config(DEFAULT_CONFIG_PATH)

        self.assertEqual(config["facebook"]["marketplace"]["session_mode"], "persistent")
        self.assertEqual(DEFAULT_PROFILE_DIR.name, ".facebook-profile")

    def test_reconciliation_reuses_the_marketplace_session(self):
        config = load_config(DEFAULT_CONFIG_PATH)
        [job] = [item for item in build_jobs(config) if item.id == "facebook-marketplace:reconcile"]

        self.assertIn("--session-mode", job.args)
        self.assertIn("persistent", job.args)


if __name__ == "__main__":
    unittest.main()
