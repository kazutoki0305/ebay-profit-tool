import unittest

from ebay_tool.calculations import calculate_profit
from ebay_tool.constants import DEFAULT_FEE_SETTINGS, DEFAULT_GRADING_RULES


class CalculationTests(unittest.TestCase):
    def test_profitable_low_risk_candidate_gets_a(self):
        candidate = {
            "destination_country": "アメリカ",
            "purchase_price_jpy": 2000,
            "domestic_shipping_jpy": 0,
            "packaging_cost_jpy": 100,
            "packed_weight_g": 400,
            "length_cm": 10,
            "width_cm": 10,
            "height_cm": 5,
            "expected_sale_price": 40,
            "sold_count_90d": 4,
            "promoted_listing_percent": 2,
            "risk_flags": {},
        }
        result = calculate_profit(
            candidate,
            DEFAULT_FEE_SETTINGS["アメリカ"],
            {"raw_rate": 150, "calculation_rate": 145.5},
            [
                {
                    "destination_country": "アメリカ",
                    "service_name": "test",
                    "weight_min_g": 0,
                    "weight_max_g": 500,
                    "shipping_cost_jpy": 1000,
                    "tracking": True,
                    "ddp_supported": True,
                }
            ],
            DEFAULT_GRADING_RULES,
        )
        self.assertTrue(result["calculation_complete"])
        self.assertEqual(result["grade"], "A")

    def test_missing_shipping_blocks_calculation(self):
        candidate = {
            "destination_country": "アメリカ",
            "purchase_price_jpy": 1000,
            "domestic_shipping_jpy": 0,
            "packaging_cost_jpy": 100,
            "packed_weight_g": 9999,
            "expected_sale_price": 30,
            "sold_count_90d": 3,
            "risk_flags": {},
        }
        result = calculate_profit(
            candidate,
            DEFAULT_FEE_SETTINGS["アメリカ"],
            {"raw_rate": 150, "calculation_rate": 145.5},
            [],
            DEFAULT_GRADING_RULES,
        )
        self.assertFalse(result["calculation_complete"])
        self.assertEqual(result["grade"], "送料未登録")

    def test_grade_uses_profit_only(self):
        candidate = {
            "destination_country": "アメリカ",
            "purchase_price_jpy": 2000,
            "domestic_shipping_jpy": 0,
            "packaging_cost_jpy": 100,
            "packed_weight_g": 400,
            "expected_sale_price": 40,
            "sold_count_90d": 0,
            "risk_flags": {"brand_logo": True},
        }
        result = calculate_profit(
            candidate,
            DEFAULT_FEE_SETTINGS["アメリカ"],
            {"raw_rate": 150, "calculation_rate": 145.5},
            [
                {
                    "destination_country": "アメリカ",
                    "service_name": "test",
                    "weight_min_g": 0,
                    "weight_max_g": 500,
                    "shipping_cost_jpy": 1000,
                    "tracking": True,
                    "ddp_supported": True,
                }
            ],
            DEFAULT_GRADING_RULES,
        )
        self.assertEqual(result["grade"], "A")


if __name__ == "__main__":
    unittest.main()
