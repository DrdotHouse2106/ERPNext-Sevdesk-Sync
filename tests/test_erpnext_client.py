import unittest
from unittest.mock import MagicMock

from erpnext_sevdesk_sync.erpnext_client import ERPNextClient, ERPNextError


def make_response(status_code=200, json_data=None, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.text = text
    return response


class ERPNextClientTests(unittest.TestCase):
    def test_get_price_list_rates_single_page(self):
        session = MagicMock()
        session.get.return_value = make_response(
            json_data={
                "data": [
                    {"item_code": "ITEM-1", "price_list_rate": 119.0},
                    {"item_code": "ITEM-2", "price_list_rate": 59.5},
                ]
            }
        )
        client = ERPNextClient("https://erp.example.com", "key", "secret", session=session)

        prices = client.get_price_list_rates("Standard Selling")

        self.assertEqual(prices, {"ITEM-1": 119.0, "ITEM-2": 59.5})
        session.get.assert_called_once()
        called_url = session.get.call_args.args[0]
        self.assertIn("Item%20Price", called_url)

    def test_get_price_list_rates_paginates(self):
        session = MagicMock()
        first_page = make_response(
            json_data={
                "data": [
                    {"item_code": f"ITEM-{i}", "price_list_rate": 10.0}
                    for i in range(200)
                ]
            }
        )
        second_page = make_response(
            json_data={"data": [{"item_code": "ITEM-200", "price_list_rate": 10.0}]}
        )
        session.get.side_effect = [first_page, second_page]
        client = ERPNextClient("https://erp.example.com", "key", "secret", session=session)

        prices = client.get_price_list_rates("Standard Selling")

        self.assertEqual(len(prices), 201)
        self.assertEqual(session.get.call_count, 2)

    def test_error_response_raises(self):
        session = MagicMock()
        session.get.return_value = make_response(status_code=500, text="boom")
        client = ERPNextClient("https://erp.example.com", "key", "secret", session=session)

        with self.assertRaises(ERPNextError):
            client.get_price_list_rates("Standard Selling")

    def test_rows_missing_fields_are_skipped(self):
        session = MagicMock()
        session.get.return_value = make_response(
            json_data={
                "data": [
                    {"item_code": "ITEM-1", "price_list_rate": None},
                    {"item_code": None, "price_list_rate": 12.0},
                    {"item_code": "ITEM-2", "price_list_rate": 5.0},
                ]
            }
        )
        client = ERPNextClient("https://erp.example.com", "key", "secret", session=session)

        prices = client.get_price_list_rates("Standard Selling")

        self.assertEqual(prices, {"ITEM-2": 5.0})


if __name__ == "__main__":
    unittest.main()
