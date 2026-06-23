import unittest
from unittest.mock import patch

from ebay_tool.fx import fetch_rate_from_frankfurter


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return [{"date": "2026-06-23", "base": "USD", "quote": "JPY", "rate": 161.68}]


class FxTests(unittest.TestCase):
    def test_frankfurter_list_response_is_supported(self):
        with patch("ebay_tool.fx.requests.get", return_value=FakeResponse()):
            result = fetch_rate_from_frankfurter("USD", "JPY")

        self.assertEqual(result["base_currency"], "USD")
        self.assertEqual(result["target_currency"], "JPY")
        self.assertEqual(result["raw_rate"], 161.68)


if __name__ == "__main__":
    unittest.main()
