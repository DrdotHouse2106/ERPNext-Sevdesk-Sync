import unittest

from sevdesk_sync.price_sync import net_to_gross, sync_prices


class FakeSevDeskClient:
    def __init__(self, parts):
        self._parts = parts
        self.updates = []
        self.creates = []
        self._next_id = 1000

    def get_parts_by_number(self):
        return {key: dict(value) for key, value in self._parts.items()}

    def update_part_price(self, part_id, *, net_price, gross_price, tax_rate, status):
        self.updates.append((part_id, net_price, gross_price, tax_rate, status))

    def create_part(self, *, name, part_number, net_price, gross_price, tax_rate, unity_id):
        self._next_id += 1
        self.creates.append(
            {
                "name": name,
                "part_number": part_number,
                "net_price": net_price,
                "gross_price": gross_price,
                "tax_rate": tax_rate,
                "unity_id": unity_id,
            }
        )
        return {"id": str(self._next_id)}


def erpnext_item(gross_price, item_name="Widget", disabled=False):
    return {"item_name": item_name, "gross_price": gross_price, "disabled": disabled}


def sevdesk_part(**overrides):
    part = {"id": "42", "price": 100.0, "taxRate": 19, "status": 100}
    part.update(overrides)
    return part


class NetToGrossTests(unittest.TestCase):
    def test_adds_vat(self):
        self.assertAlmostEqual(net_to_gross(100.0, 19), 119.0)

    def test_zero_tax_rate_is_noop(self):
        self.assertAlmostEqual(net_to_gross(50.0, 0), 50.0)


class SyncPricesUpdateTests(unittest.TestCase):
    def test_erpnext_price_becomes_sevdesk_net_price(self):
        """100 EUR gross in ERPNext must become 100 EUR *net* in sevDesk (119 EUR gross at 19%)."""
        sevdesk = FakeSevDeskClient({"ITEM-1": sevdesk_part(price=90.0)})

        results = sync_prices({"ITEM-1": erpnext_item(100.0)}, sevdesk)

        self.assertEqual(len(sevdesk.updates), 1)
        part_id, net_price, gross_price, tax_rate, status = sevdesk.updates[0]
        self.assertEqual(part_id, "42")
        self.assertAlmostEqual(net_price, 100.0)
        self.assertAlmostEqual(gross_price, 119.0)
        self.assertEqual(tax_rate, 19.0)
        self.assertEqual(status, 100)
        self.assertEqual(results[0].action, "updated")

    def test_skips_already_in_sync_part(self):
        sevdesk = FakeSevDeskClient({"ITEM-1": sevdesk_part(price=100.0)})

        results = sync_prices({"ITEM-1": erpnext_item(100.0)}, sevdesk)

        self.assertEqual(sevdesk.updates, [])
        self.assertEqual(results[0].action, "unchanged")

    def test_dry_run_does_not_update(self):
        sevdesk = FakeSevDeskClient({"ITEM-1": sevdesk_part(price=90.0)})

        results = sync_prices({"ITEM-1": erpnext_item(100.0)}, sevdesk, dry_run=True)

        self.assertEqual(sevdesk.updates, [])
        self.assertEqual(results[0].action, "updated")
        self.assertAlmostEqual(results[0].net_price, 100.0)
        self.assertAlmostEqual(results[0].gross_price, 119.0)

    def test_uses_default_tax_rate_when_part_has_none(self):
        sevdesk = FakeSevDeskClient(
            {"ITEM-1": sevdesk_part(price=None, taxRate=None)}
        )

        results = sync_prices(
            {"ITEM-1": erpnext_item(100.0)}, sevdesk, default_tax_rate=19.0
        )

        self.assertEqual(len(sevdesk.updates), 1)
        self.assertAlmostEqual(results[0].net_price, 100.0)
        self.assertAlmostEqual(results[0].gross_price, 119.0)

    def test_skips_item_without_tax_rate_and_no_default(self):
        sevdesk = FakeSevDeskClient(
            {"ITEM-1": sevdesk_part(price=None, taxRate=None)}
        )

        results = sync_prices({"ITEM-1": erpnext_item(100.0)}, sevdesk)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, "skipped")
        self.assertTrue(results[0].reason)
        self.assertEqual(sevdesk.updates, [])


class SyncPricesStatusTests(unittest.TestCase):
    def test_deactivates_part_when_item_disabled(self):
        sevdesk = FakeSevDeskClient({"ITEM-1": sevdesk_part(price=100.0, status=100)})

        results = sync_prices(
            {"ITEM-1": erpnext_item(100.0, disabled=True)}, sevdesk
        )

        self.assertEqual(len(sevdesk.updates), 1)
        _, _, _, _, status = sevdesk.updates[0]
        self.assertEqual(status, 50)
        self.assertEqual(results[0].action, "updated")

    def test_reactivates_part_when_item_enabled_again(self):
        sevdesk = FakeSevDeskClient({"ITEM-1": sevdesk_part(price=100.0, status=50)})

        results = sync_prices(
            {"ITEM-1": erpnext_item(100.0, disabled=False)}, sevdesk
        )

        self.assertEqual(len(sevdesk.updates), 1)
        _, _, _, _, status = sevdesk.updates[0]
        self.assertEqual(status, 100)
        self.assertEqual(results[0].action, "updated")

    def test_disabled_and_already_inactive_stays_unchanged(self):
        sevdesk = FakeSevDeskClient({"ITEM-1": sevdesk_part(price=100.0, status=50)})

        results = sync_prices(
            {"ITEM-1": erpnext_item(100.0, disabled=True)}, sevdesk
        )

        self.assertEqual(sevdesk.updates, [])
        self.assertEqual(results[0].action, "unchanged")

    def test_skips_creation_for_disabled_item_without_existing_part(self):
        sevdesk = FakeSevDeskClient({})

        results = sync_prices(
            {"ITEM-1": erpnext_item(100.0, disabled=True)},
            sevdesk,
            default_tax_rate=19.0,
            default_unity_id="1",
        )

        self.assertEqual(sevdesk.creates, [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, "skipped")
        self.assertTrue(results[0].reason)


class SyncPricesCreateTests(unittest.TestCase):
    def test_creates_missing_part_with_net_price_and_computed_gross(self):
        sevdesk = FakeSevDeskClient({})

        results = sync_prices(
            {"ITEM-1": erpnext_item(100.0, item_name="Widget")},
            sevdesk,
            default_tax_rate=19.0,
            default_unity_id="1",
        )

        self.assertEqual(len(sevdesk.creates), 1)
        created = sevdesk.creates[0]
        self.assertEqual(created["name"], "Widget")
        self.assertEqual(created["part_number"], "ITEM-1")
        self.assertAlmostEqual(created["net_price"], 100.0)
        self.assertAlmostEqual(created["gross_price"], 119.0)
        self.assertEqual(created["tax_rate"], 19.0)
        self.assertEqual(created["unity_id"], "1")
        self.assertEqual(results[0].action, "created")

    def test_dry_run_does_not_create(self):
        sevdesk = FakeSevDeskClient({})

        results = sync_prices(
            {"ITEM-1": erpnext_item(100.0)},
            sevdesk,
            default_tax_rate=19.0,
            default_unity_id="1",
            dry_run=True,
        )

        self.assertEqual(sevdesk.creates, [])
        self.assertEqual(results[0].action, "created")

    def test_skips_creation_without_default_tax_rate(self):
        sevdesk = FakeSevDeskClient({})

        results = sync_prices(
            {"ITEM-1": erpnext_item(100.0)}, sevdesk, default_unity_id="1"
        )

        self.assertEqual(sevdesk.creates, [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, "skipped")
        self.assertTrue(results[0].reason)

    def test_skips_creation_without_default_unity_id(self):
        sevdesk = FakeSevDeskClient({})

        results = sync_prices(
            {"ITEM-1": erpnext_item(100.0)}, sevdesk, default_tax_rate=19.0
        )

        self.assertEqual(sevdesk.creates, [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, "skipped")
        self.assertTrue(results[0].reason)

    def test_uses_item_code_as_name_fallback(self):
        sevdesk = FakeSevDeskClient({})

        sync_prices(
            {"ITEM-1": {"gross_price": 100.0}},
            sevdesk,
            default_tax_rate=19.0,
            default_unity_id="1",
        )

        self.assertEqual(sevdesk.creates[0]["name"], "ITEM-1")


if __name__ == "__main__":
    unittest.main()
