"""
單元測試：驗證爬蟲處理函式之正確性 (數值解析、Decimal 財務比率精度、缺值處理、兩市場同為舊日期校驗)
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
        """直接呼叫正式函式：測試真實數字 0 的解析，必須傳回 0"""
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

    def test_decimal_pct_precision(self):
        """直接呼叫正式函式 calculate_pct：測試 Decimal 財務比例精度，驗證零股計算不失真"""
        trust_shares = 500       # 500 股（不足 1 張）
        issued_shares = 10_000_000 # 10,000,000 股

        # 呼叫正式 calculate_pct
        pct = calculate_pct(trust_shares, issued_shares)
        self.assertIsInstance(pct, Decimal)
        self.assertEqual(pct, Decimal("0.01")) # (500 / 10000000)*100 = 0.005 -> ROUND_HALF_UP -> 0.01%

    def test_verify_dates_success(self):
        """直接呼叫正式函式 verify_dates：當 TWSE, TPEX 與目標交易日均相同，驗證通過"""
        self.assertTrue(verify_dates("20260821", "20260821", "20260821"))

    def test_verify_dates_mismatch_market(self):
        """直接呼叫正式函式 verify_dates：當 TWSE 與 TPEX 市場日期不一致時，拋出 ValueError"""
        with self.assertRaises(ValueError) as ctx:
            verify_dates("20260821", "20260820", "20260821")
        self.assertIn("不一致", str(ctx.exception))

    def test_verify_dates_stale_target(self):
        """直接呼叫正式函式 verify_dates：測試「兩邊同為舊日期」情境，必須拋出 ValueError，不得視為最新資料"""
        twse_date = "20260820"  # 舊日期 (昨日)
        tpex_date = "20260820"  # 舊日期 (昨日)
        target_date = "20260821" # 今日目標交易日

        with self.assertRaises(ValueError) as ctx:
            verify_dates(twse_date, tpex_date, target_date)
        self.assertIn("同為舊日期", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
