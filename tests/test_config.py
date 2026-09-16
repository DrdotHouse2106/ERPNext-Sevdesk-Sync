import unittest

from erpnext_sevdesk_sync.config import Config, ConfigError


class ConfigTests(unittest.TestCase):
    def _env(self, **overrides):
        base = {
            "ERPNEXT_URL": "https://erp.example.com/",
            "ERPNEXT_API_KEY": "key",
            "ERPNEXT_API_SECRET": "secret",
            "SEVDESK_API_TOKEN": "token",
        }
        base.update(overrides)
        return base

    def test_defaults(self):
        config = Config.from_env(self._env())
        self.assertEqual(config.erpnext_url, "https://erp.example.com")
        self.assertEqual(config.erpnext_price_list, "Standard Selling")
        self.assertEqual(config.sevdesk_base_url, "https://my.sevdesk.de/api/v1")
        self.assertIsNone(config.default_tax_rate)
        self.assertFalse(config.dry_run)

    def test_overrides(self):
        config = Config.from_env(
            self._env(
                ERPNEXT_PRICE_LIST="Standard Verkauf",
                SEVDESK_BASE_URL="https://example.com/api/v1/",
                DEFAULT_TAX_RATE="19",
                DRY_RUN="true",
            )
        )
        self.assertEqual(config.erpnext_price_list, "Standard Verkauf")
        self.assertEqual(config.sevdesk_base_url, "https://example.com/api/v1")
        self.assertEqual(config.default_tax_rate, 19.0)
        self.assertTrue(config.dry_run)

    def test_missing_required_raises(self):
        env = self._env()
        del env["SEVDESK_API_TOKEN"]
        with self.assertRaises(ConfigError):
            Config.from_env(env)

    def test_invalid_default_tax_rate_raises(self):
        env = self._env(DEFAULT_TAX_RATE="not-a-number")
        with self.assertRaises(ConfigError):
            Config.from_env(env)


if __name__ == "__main__":
    unittest.main()
