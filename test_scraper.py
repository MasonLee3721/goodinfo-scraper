"""
單元測試：驗證爬蟲處理函式之正確性 (數值解析、Decimal 財務比率核心與顯示層分離、門檻過濾正式函式、高精度排序正式函式、CSV 缺值輸出安全、缺值/真零/無效分母處置、兩市場同為舊日期校驗)
執行方式：.venv/bin/python test_scraper.py
"""
import unittest
from decimal import Decimal
from scrape_goodinfo import parse_int, calculate_pct, format_pct_for_csv, filter_by_pct_threshold, rank_stocks, verify_dates

class TestScraperFunctions(unittest.TestCase):

    def test_parse_int_valid(self):
        """直接呼叫正式函式 parse_int：測試正常整數與千分位逗號解析"""
        self.assertEqual(parse_int("1,234,567"), 1234567)
        self.assertEqual(parse_int("100"), 100)
        self.assertEqual(parse_int("-500"), -500)

    def test_parse_int_true_zero(self):
        """直接呼叫正式函式 parse_int：測試真實數字 0 的解析，必須傳回 0，不能被當作 None"""
        self.assertEqual(parse_int("0"), 0)
        self.assertEqual(parse_int(0), 0)

    def test_parse_int_missing_null(self):
        """直接呼叫正式函式 parse_int：測試缺值、空字串、--、None 的解析，必須傳回 None"""
        self.assertIsNone(parse_int(""))
        self.assertIsNone(parse_int("   "))
        self.assertIsNone(parse_int("--"))
        self.assertIsNone(parse_int(None))
        self.assertIsNone(parse_int("null"))
        self.assertIsNone(parse_int("None"))

    def test_calculate_pct_core_raw_value(self):
        """直接呼叫正式函式 calculate_pct：(500 / 10,000,000) * 100 核心正確原始值必須為 Decimal('0.005')，不安裝提前四捨五入截斷"""
        trust_shares = 500
        issued_shares = 10_000_000
        raw_pct = calculate_pct(trust_shares, issued_shares)
        self.assertIsInstance(raw_pct, Decimal)
        self.assertEqual(raw_pct, Decimal("0.005"))

    def test_format_pct_for_csv_formal_function(self):
        """直接呼叫正式顯示層函式 format_pct_for_csv 驗證輸出規格：
        - Decimal('0.005') -> '+0.01'
        - Decimal('0') -> '0.00'
        - None -> '' (空字串)
        """
        self.assertEqual(format_pct_for_csv(Decimal("0.005")), "+0.01")
        self.assertEqual(format_pct_for_csv(Decimal("0")), "0.00")
        self.assertEqual(format_pct_for_csv(None), "")

    def test_filter_by_pct_threshold_formal_function(self):
        """直接呼叫正式門檻篩選函式 filter_by_pct_threshold 驗證：
        原始值 Decimal('0.395') 即使顯示層顯示為 '+0.40'，門檻比對 >= Decimal('0.4') 時仍不得通過！
        """
        stocks = [
            {"code": "2330", "pct": Decimal("0.395")},
            {"code": "2317", "pct": Decimal("0.400")}
        ]
        filtered = filter_by_pct_threshold(stocks, threshold=Decimal("0.4"))
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["code"], "2317")

    def test_rank_stocks_formal_function(self):
        """直接呼叫正式高精度排序函式 rank_stocks 驗證：
        0.004% 與 0.005% 在高精度 Decimal 排序下，0.005% 的股票必須精確排在 0.004% 前面
        """
        stocks = [
            {"code": "2330", "pct": Decimal("0.004"), "trust_shares": 400},
            {"code": "2317", "pct": Decimal("0.005"), "trust_shares": 500}
        ]
        ranked = rank_stocks(stocks, top_n=2)
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0]["code"], "2317")
        self.assertEqual(ranked[1]["code"], "2330")

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
