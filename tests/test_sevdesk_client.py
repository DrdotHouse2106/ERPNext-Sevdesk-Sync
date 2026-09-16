import unittest
from unittest.mock import MagicMock

from sevdesk_sync.sevdesk_client import SevDeskClient, SevDeskError


def make_response(status_code=200, json_data=None, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.text = text
    return response


class SevDeskClientTests(unittest.TestCase):
    def test_get_parts_by_number_single_page(self):
        session = MagicMock()
        session.get.return_value = make_response(
            json_data={
                "objects": [
                    {"id": "1", "partNumber": "ITEM-1", "price": 100.0, "taxRate": 19},
                    {"id": "2", "partNumber": "ITEM-2", "price": 50.0, "taxRate": 7},
                    {"id": "3", "partNumber": None, "price": 10.0, "taxRate": 19},
                ]
            }
        )
        client = SevDeskClient("https://my.sevdesk.de/api/v1", "token", session=session)

        parts = client.get_parts_by_number()

        self.assertEqual(set(parts), {"ITEM-1", "ITEM-2"})
        self.assertEqual(parts["ITEM-1"]["id"], "1")

    def test_get_parts_by_number_paginates(self):
        session = MagicMock()
        first_page = make_response(
            json_data={
                "objects": [
                    {"id": str(i), "partNumber": f"ITEM-{i}"} for i in range(100)
                ]
            }
        )
        second_page = make_response(
            json_data={"objects": [{"id": "100", "partNumber": "ITEM-100"}]}
        )
        session.get.side_effect = [first_page, second_page]
        client = SevDeskClient("https://my.sevdesk.de/api/v1", "token", session=session)

        parts = client.get_parts_by_number()

        self.assertEqual(len(parts), 101)
        self.assertEqual(session.get.call_count, 2)

    def test_get_parts_error_response_raises(self):
        session = MagicMock()
        session.get.return_value = make_response(status_code=401, text="unauthorized")
        client = SevDeskClient("https://my.sevdesk.de/api/v1", "token", session=session)

        with self.assertRaises(SevDeskError):
            client.get_parts_by_number()

    def test_update_part_price_sends_expected_payload(self):
        session = MagicMock()
        session.put.return_value = make_response(status_code=200)
        client = SevDeskClient("https://my.sevdesk.de/api/v1", "token", session=session)

        client.update_part_price("42", net_price=100.004, gross_price=119.0, tax_rate=19)

        session.put.assert_called_once()
        args, kwargs = session.put.call_args
        self.assertEqual(args[0], "https://my.sevdesk.de/api/v1/Part/42")
        self.assertEqual(
            kwargs["json"], {"price": 100.0, "priceGross": 119.0, "taxRate": 19}
        )

    def test_update_part_price_error_response_raises(self):
        session = MagicMock()
        session.put.return_value = make_response(status_code=400, text="bad request")
        client = SevDeskClient("https://my.sevdesk.de/api/v1", "token", session=session)

        with self.assertRaises(SevDeskError):
            client.update_part_price("42", net_price=100.0, gross_price=119.0, tax_rate=19)


if __name__ == "__main__":
    unittest.main()
