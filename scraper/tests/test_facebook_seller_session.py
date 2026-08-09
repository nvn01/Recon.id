from __future__ import annotations

import unittest

from scraper.scheduler import build_jobs
from scraper.shared.config import DEFAULT_CONFIG_PATH, load_config


class FacebookSellerSessionTests(unittest.TestCase):
    def test_marketplace_is_anonymous_headless_and_ephemeral(self):
        config = load_config(DEFAULT_CONFIG_PATH)
        marketplace = config["facebook"]["marketplace"]

        self.assertTrue(marketplace["headless"])
        self.assertEqual(marketplace["session_mode"], "ephemeral")

    def test_reconciliation_does_not_receive_an_authenticated_session(self):
        config = load_config(DEFAULT_CONFIG_PATH)
        [job] = [item for item in build_jobs(config) if item.id == "facebook-marketplace:reconcile"]

        self.assertIn("--headless", job.args)
        self.assertNotIn("--session-mode", job.args)
        self.assertNotIn("persistent", job.args)


if __name__ == "__main__":
    unittest.main()
