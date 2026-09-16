"""Tests for erpnext_source.py using a stubbed-out ``frappe`` module.

The real ``frappe`` package is only available inside a bench site, so these
tests inject a minimal fake module into ``sys.modules`` before import instead
of requiring a full Frappe installation.
"""

import sys
import types
import unittest


class _FakeFrappeModule(types.ModuleType):
    def __init__(self, rows):
        super().__init__("frappe")
        self.calls = []
        self._rows = rows

    def get_all(self, doctype, filters=None, fields=None):
        self.calls.append((doctype, filters, fields))
        return self._rows


def _install_fake_frappe(rows):
    fake = _FakeFrappeModule(rows)
    sys.modules["frappe"] = fake
    return fake


class GetPriceListRatesTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("frappe", None)
        sys.modules.pop("sevdesk_sync.erpnext_source", None)

    def test_returns_item_code_to_rate_mapping(self):
        _install_fake_frappe(
            [
                {"item_code": "ITEM-1", "price_list_rate": 119.0},
                {"item_code": "ITEM-2", "price_list_rate": 59.5},
            ]
        )
        from sevdesk_sync.erpnext_source import get_price_list_rates

        prices = get_price_list_rates("Standard Selling")

        self.assertEqual(prices, {"ITEM-1": 119.0, "ITEM-2": 59.5})

    def test_filters_incomplete_rows(self):
        _install_fake_frappe(
            [
                {"item_code": "ITEM-1", "price_list_rate": None},
                {"item_code": None, "price_list_rate": 5.0},
                {"item_code": "ITEM-2", "price_list_rate": 5.0},
            ]
        )
        from sevdesk_sync.erpnext_source import get_price_list_rates

        prices = get_price_list_rates("Standard Selling")

        self.assertEqual(prices, {"ITEM-2": 5.0})

    def test_passes_expected_filters(self):
        fake = _install_fake_frappe([])
        from sevdesk_sync.erpnext_source import get_price_list_rates

        get_price_list_rates("Standard Selling")

        self.assertEqual(
            fake.calls,
            [
                (
                    "Item Price",
                    {"price_list": "Standard Selling", "selling": 1},
                    ["item_code", "price_list_rate"],
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
