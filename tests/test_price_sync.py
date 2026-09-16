import unittest

from erpnext_sevdesk_sync.price_sync import gross_to_net, sync_prices


class FakeERPNextClient:
    def __init__(self, prices):
        self._prices = prices

    def get_price_list_rates(self, price_list):
        return dict(self._prices)


class FakeSevDeskClient:
    def __init__(self, parts):
        self._parts = parts
        self.updates = []

    def get_parts_by_number(self):
        return {key: dict(value) for key, value in self._parts.items()}

    def update_part_price(self, part_id, *, net_price, gross_price, tax_rate):
        self.updates.append((part_id, net_price, gross_price, tax_rate))


class GrossToNetTests(unittest.TestCase):
    def test_removes_vat(self):
        self.assertAlmostEqual(gross_to_net(119.0, 19), 100.0)

    def test_zero_tax_rate_is_noop(self):
        self.assertAlmostEqual(gross_to_net(50.0, 0), 50.0)


class SyncPricesTests(unittest.TestCase):
    def test_updates_part_with_net_price_from_sevdesk_tax_rate(self):
        erp = FakeERPNextClient({"ITEM-1": 119.0})
        sevdesk = FakeSevDeskClient({"ITEM-1": {"id": "42", "price": 90.0, "taxRate": 19}})

        results = sync_prices(erp, sevdesk, price_list="Standard Selling")

        self.assertEqual(len(sevdesk.updates), 1)
        part_id, net_price, gross_price, tax_rate = sevdesk.updates[0]
        self.assertEqual(part_id, "42")
        self.assertAlmostEqual(net_price, 100.0)
        self.assertAlmostEqual(gross_price, 119.0)
        self.assertEqual(tax_rate, 19.0)
        self.assertTrue(results[0].updated)

    def test_skips_already_in_sync_part(self):
        erp = FakeERPNextClient({"ITEM-1": 119.0})
        sevdesk = FakeSevDeskClient({"ITEM-1": {"id": "42", "price": 100.0, "taxRate": 19}})

        results = sync_prices(erp, sevdesk, price_list="Standard Selling")

        self.assertEqual(sevdesk.updates, [])
        self.assertFalse(results[0].updated)

    def test_dry_run_does_not_update(self):
        erp = FakeERPNextClient({"ITEM-1": 119.0})
        sevdesk = FakeSevDeskClient({"ITEM-1": {"id": "42", "price": 90.0, "taxRate": 19}})

        results = sync_prices(erp, sevdesk, price_list="Standard Selling", dry_run=True)

        self.assertEqual(sevdesk.updates, [])
        self.assertFalse(results[0].updated)
        self.assertAlmostEqual(results[0].net_price, 100.0)

    def test_uses_default_tax_rate_when_part_has_none(self):
        erp = FakeERPNextClient({"ITEM-1": 119.0})
        sevdesk = FakeSevDeskClient({"ITEM-1": {"id": "42", "price": None, "taxRate": None}})

        results = sync_prices(
            erp, sevdesk, price_list="Standard Selling", default_tax_rate=19.0
        )

        self.assertEqual(len(sevdesk.updates), 1)
        self.assertAlmostEqual(results[0].net_price, 100.0)

    def test_skips_item_without_matching_part(self):
        erp = FakeERPNextClient({"ITEM-1": 119.0, "ITEM-2": 50.0})
        sevdesk = FakeSevDeskClient({"ITEM-1": {"id": "42", "price": 90.0, "taxRate": 19}})

        results = sync_prices(erp, sevdesk, price_list="Standard Selling")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].item_code, "ITEM-1")

    def test_skips_item_without_tax_rate_and_no_default(self):
        erp = FakeERPNextClient({"ITEM-1": 119.0})
        sevdesk = FakeSevDeskClient({"ITEM-1": {"id": "42", "price": None, "taxRate": None}})

        results = sync_prices(erp, sevdesk, price_list="Standard Selling")

        self.assertEqual(results, [])
        self.assertEqual(sevdesk.updates, [])


if __name__ == "__main__":
    unittest.main()
