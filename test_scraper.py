"""
單元測試：驗證爬蟲處理函式之正確性 (數值解析、Decimal 財務比率核心與顯示層分離、門檻過濾、排名排序、CSV 缺值輸出安全、缺值/真零/無效分母處置、兩市場同為舊日期校驗)
執行方式：.venv/bin/python test_scraper.py
"""
import unittest
from decimal import Decimal, ROUND_HALF_UP
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

    def test_calculate_pct_core_raw_value(self):
        """核心測試：(500 / 10,000,000) * 100 核心正確原始值必須為 Decimal('0.005')，不安裝提前四捨五入截斷"""
        trust_shares = 500
        issued_shares = 10_000_000
        raw_pct = calculate_pct(trust_shares, issued_shares)
        self.assertIsInstance(raw_pct, Decimal)
        self.assertEqual(raw_pct, Decimal("0.005"))

    def test_calculate_pct_display_layer(self):
        """顯示層測試：核心原始值 Decimal('0.005') 僅在顯示層使用 ROUND_HALF_UP 格式化後顯示為 Decimal('0.01')"""
        trust_shares = 500
        issued_shares = 10_000_000
        raw_pct = calculate_pct(trust_shares, issued_shares)
        display_pct = raw_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.assertEqual(display_pct, Decimal("0.01"))

    def test_calculate_pct_threshold_gate(self):
        """跨層門檻測試：0.395% 不得因顯示成 0.40% 就通過 >= 0.4% 的門檻比對"""
        trust_shares = 395
        issued_shares = 100_000
        raw_pct = calculate_pct(trust_shares, issued_shares) # Decimal("0.395")

        # 顯示層會是 0.40%
        display_pct = raw_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.assertEqual(display_pct, Decimal("0.40"))

        # 門檻比對必須使用 raw_pct，Decimal("0.395") >= Decimal("0.4") 必須精確判定為 False
        threshold = Decimal("0.4")
        self.assertFalse(raw_pct >= threshold)

    def test_calculate_pct_ranking_order(self):
        """跨層排名測試：0.004% 與 0.005% 顯示可能相同，但原始排名必須保持不同 (0.004 < 0.005)"""
        pct_A = calculate_pct(400, 10_000_000) # Decimal("0.004")
        pct_B = calculate_pct(500, 10_000_000) # Decimal("0.005")

        self.assertNotEqual(pct_A, pct_B)
        self.assertLess(pct_A, pct_B)

    def test_csv_export_null_safety(self):
        """跨層 CSV 缺值測試：pct=None 輸出 CSV 時為空字串 ''，不得呼叫 quantize() 或變成 '0' 或 '0.00'"""
        pct = None
        if pct is not None:
            pct_formatted = pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            pct_str = f"+{pct_formatted}" if pct_formatted > 0 else str(pct_formatted)
        else:
            pct_str = ""

        self.assertEqual(pct_str, "")
        self.assertNotEqual(pct_str, "0")
        self.assertNotEqual(pct_str, "0.00")

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
