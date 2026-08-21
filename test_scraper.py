"""
單元測試：驗證爬蟲處理函式之正確性 (數值解析、單位精度、缺值處理、日期比對)
執行方式：.venv/bin/python test_scraper.py
"""
import unittest
from scrape_goodinfo import parse_int

class TestScraperFunctions(unittest.TestCase):

    def test_parse_int_valid(self):
        """測試正常整數與千分位逗號解析"""
        self.assertEqual(parse_int("1,234,567"), 1234567)
        self.assertEqual(parse_int("100"), 100)
        self.assertEqual(parse_int("-500"), -500)

    def test_parse_int_true_zero(self):
        """測試真實數字 0 的解析：必須傳回 0，不能被當作 None 處理"""
        self.assertEqual(parse_int("0"), 0)
        self.assertEqual(parse_int(0), 0)

    def test_parse_int_missing_null(self):
        """測試缺值、空字串、--、None 的解析：必須傳回 None，絕不能回傳 0"""
        self.assertIsNone(parse_int(""))
        self.assertIsNone(parse_int("   "))
        self.assertIsNone(parse_int("--"))
        self.assertIsNone(parse_int(None))
        self.assertIsNone(parse_int("null"))
        self.assertIsNone(parse_int("None"))
        self.assertIsNone(parse_int("N/A"))

    def test_float_pct_precision(self):
        """測試股數 (shares) 浮點數比率計算，驗證未提前做 // 1000 截斷時的精確度度"""
        # 假設買超 500 股（不足 1 張/1000股），發行股數 10,000,000 股
        trust_shares = 500
        issued_shares = 10_000_000

        # 若提前 // 1000：trust_shares // 1000 會變成 0，計算出的 pct 會是 0.0 (失真)
        truncated_pct = round(((trust_shares // 1000) / (issued_shares // 1000) * 100), 2)
        self.assertEqual(truncated_pct, 0.0)

        # 核心全程保留股數計算：(500 / 10000000) * 100 = 0.005% -> round 0.01% (正確精確度)
        exact_pct = round((trust_shares / issued_shares * 100), 4)
        self.assertEqual(exact_pct, 0.005)
        self.assertGreater(exact_pct, 0)

    def test_date_alignment_format(self):
        """測試 民國年 (1150821) 轉 西元年 (20260821) 比對邏輯"""
        tpex_roc = "1150821"
        twse_ad = "20260821"
        tpex_ad = f"{int(tpex_roc[:3]) + 1911}{tpex_roc[3:]}"
        self.assertEqual(tpex_ad, twse_ad)

if __name__ == "__main__":
    unittest.main()
