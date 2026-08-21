"""
單元測試：驗證爬蟲處理函式之正確性 (數值解析、Decimal 財務比率精度、缺值/真零/無效分母處置、兩市場同為舊日期校驗)
執行方式：.venv/bin/python test_scraper.py
"""
import unittest
from decimal import Decimal
from scrape_goodinfo import parse_int, calculate_pct, verify_dates

class TestScraperFunctions(unittest.TestCase):

    def test_parse_int_valid(self):
        """直接呼叫正式函式：測試正常整數與千分位逗號解析"""
        self.assertEqual(parse_int("1,234,567"), 1234567)
        self.assertEqual(parse_int("100"), 100)
        self.assertEqual(parse_int("-500"), -500)

    def test_parse_int_true_zero(self):
        """直接呼叫正式函式：測試真實數字 0 的解析，必須傳回 0，不能被當作 None"""
        self.assertEqual(parse_int("0"), 0)
        self.assertEqual(parse_int(0), 0)

    def test_parse_int_missing_null(self):
        """直接呼叫正式函式：測試缺值、空字串、--、None 的解析，必須傳回 None"""
        self.assertIsNone(parse_int(""))
        self.assertIsNone(parse_int("   "))
        self.assertIsNone(parse_int("--"))
        self.assertIsNone(parse_int(None))
        self.assertIsNone(parse_int("null"))
        self.assertIsNone(parse_int("None"))

    def test_calculate_pct_missing(self):
        """直接呼叫正式 calculate_pct：缺值測試 (分子或分母為 None) 必須傳回 None"""
        self.assertIsNone(calculate_pct(None, 10_000_000))
        self.assertIsNone(calculate_pct(500, None))
        self.assertIsNone(calculate_pct(None, None))

    def test_calculate_pct_true_zero(self):
        """直接呼叫正式 calculate_pct：官方真零測試 (分子為 0 且分母有效) 必須傳回 Decimal("0")"""
        pct = calculate_pct(0, 10_000_000)
        self.assertIsInstance(pct, Decimal)
        self.assertEqual(pct, Decimal("0"))

    def test_calculate_pct_invalid_denominator(self):
        """直接呼叫正式 calculate_pct：無效分母測試 (分母 <= 0) 必須拋出 ValueError"""
        with self.assertRaises(ValueError) as ctx1:
            calculate_pct(500, 0)
        self.assertIn("positive", str(ctx1.exception))

        with self.assertRaises(ValueError) as ctx2:
            calculate_pct(500, -1000)
        self.assertIn("positive", str(ctx2.exception))

    def test_calculate_pct_no_premature_truncation(self):
        """直接呼叫正式 calculate_pct：驗證核心不提前做 quantize(0.01)，保留完整 Decimal 精度供前30名排序」"""
        trust_shares = 1234
        issued_shares = 100_000_000
        # 1234 / 100000000 * 100 = 0.001234
        pct = calculate_pct(trust_shares, issued_shares)
        self.assertIsInstance(pct, Decimal)
        self.assertEqual(pct, Decimal("1234") / Decimal("100000000") * Decimal("100"))
        self.assertEqual(pct, Decimal("0.001234"))

    def test_verify_dates_success(self):
        """直接呼叫正式函式 verify_dates：當 TWSE, TPEX 與目標交易日均相同，驗證通過"""
        self.assertTrue(verify_dates("20260821", "20260821", "20260821"))

    def test_verify_dates_mismatch_market(self):
        """直接呼叫正式函式 verify_dates：當 TWSE 與 TPEX 市場日期不一致時，拋出 ValueError"""
        with self.assertRaises(ValueError) as ctx:
            verify_dates("20260821", "20260820", "20260821")
        self.assertIn("不一致", str(ctx.exception))

    def test_verify_dates_stale_target(self):
        """直接呼叫正式函式 verify_dates：測試「兩邊同為舊日期」情境，必須拋出 ValueError"""
        twse_date = "20260820"   # 舊日期 (昨日)
        tpex_date = "20260820"   # 舊日期 (昨日)
        target_date = "20260821"  # 今日目標交易日

        with self.assertRaises(ValueError) as ctx:
            verify_dates(twse_date, tpex_date, target_date)
        self.assertIn("同為舊日期", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
