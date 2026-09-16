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


class GetPriceListItemsTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("frappe", None)
        sys.modules.pop("sevdesk_sync.erpnext_source", None)

    def test_returns_item_code_to_item_mapping(self):
        _install_fake_frappe(
            [
                {"item_code": "ITEM-1", "price_list_rate": 119.0, "item_name": "Widget"},
                {"item_code": "ITEM-2", "price_list_rate": 59.5, "item_name": "Gadget"},
            ]
        )
        from sevdesk_sync.erpnext_source import get_price_list_items

        items = get_price_list_items("Standard Selling")

        self.assertEqual(
            items,
            {
                "ITEM-1": {"item_name": "Widget", "gross_price": 119.0},
                "ITEM-2": {"item_name": "Gadget", "gross_price": 59.5},
            },
        )

    def test_falls_back_to_item_code_when_name_missing(self):
        _install_fake_frappe(
            [{"item_code": "ITEM-1", "price_list_rate": 119.0, "item_name": None}]
        )
        from sevdesk_sync.erpnext_source import get_price_list_items

        items = get_price_list_items("Standard Selling")

        self.assertEqual(items["ITEM-1"]["item_name"], "ITEM-1")

    def test_filters_incomplete_rows(self):
        _install_fake_frappe(
            [
                {"item_code": "ITEM-1", "price_list_rate": None, "item_name": "X"},
                {"item_code": None, "price_list_rate": 5.0, "item_name": "Y"},
                {"item_code": "ITEM-2", "price_list_rate": 5.0, "item_name": "Z"},
            ]
        )
        from sevdesk_sync.erpnext_source import get_price_list_items

        items = get_price_list_items("Standard Selling")

        self.assertEqual(set(items), {"ITEM-2"})

    def test_passes_expected_filters(self):
        fake = _install_fake_frappe([])
        from sevdesk_sync.erpnext_source import get_price_list_items

        get_price_list_items("Standard Selling")

        self.assertEqual(
            fake.calls,
            [
                (
                    "Item Price",
                    {"price_list": "Standard Selling", "selling": 1},
                    [
                        "item_code",
                        "price_list_rate",
                        "item_code.item_name as item_name",
                        "item_code.item_group as item_group",
                    ],
                )
            ],
        )

    def test_excludes_items_in_excluded_item_groups(self):
        _install_fake_frappe(
            [
                {
                    "item_code": "ITEM-1",
                    "price_list_rate": 100.0,
                    "item_name": "A",
                    "item_group": "Rohstoffe",
                },
                {
                    "item_code": "ITEM-2",
                    "price_list_rate": 50.0,
                    "item_name": "B",
                    "item_group": "Verkaufsartikel",
                },
            ]
        )
        from sevdesk_sync.erpnext_source import get_price_list_items

        items = get_price_list_items(
            "Standard Selling", excluded_item_groups=["Rohstoffe"]
        )

        self.assertEqual(set(items), {"ITEM-2"})

    def test_no_exclusion_when_not_configured(self):
        _install_fake_frappe(
            [
                {
                    "item_code": "ITEM-1",
                    "price_list_rate": 100.0,
                    "item_name": "A",
                    "item_group": "Rohstoffe",
                }
            ]
        )
        from sevdesk_sync.erpnext_source import get_price_list_items

        items = get_price_list_items("Standard Selling")

        self.assertEqual(set(items), {"ITEM-1"})


if __name__ == "__main__":
    unittest.main()
