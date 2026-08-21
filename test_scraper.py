"""
單元測試與端到端測試：驗證爬蟲處理函式與完整數據鏈路 (數值解析、Decimal 財務比率核心與顯示層分離、門檻過濾強型別檢查、高精度與三級穩定排序、端到端 CSV 產出、缺值/真零/無效分母處置、兩市場同為舊日期校驗)
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
        - None -> '' (空字串，不變成 0 或 0.00)
        - 非 Decimal 型別 -> 拋出 TypeError
        """
        self.assertEqual(format_pct_for_csv(Decimal("0.005")), "+0.01")
        self.assertEqual(format_pct_for_csv(Decimal("0")), "0.00")
        self.assertEqual(format_pct_for_csv(None), "")
        with self.assertRaises(TypeError):
            format_pct_for_csv(0.005)

    def test_filter_by_pct_threshold_strict_types(self):
        """直接呼叫正式門檻篩選函式 filter_by_pct_threshold 驗證：
        - 原始值 Decimal('0.395') 即使顯示層顯示為 '+0.40'，門檻比對 >= Decimal('0.4') 時仍不得通過
        - 自動將 float/str threshold 轉為 Decimal 比對
        - 遇到非 Decimal/None 的 pct 拋出 TypeError
        """
        stocks = [
            {"code": "2330", "pct": Decimal("0.395")},
            {"code": "2317", "pct": Decimal("0.400")}
        ]
        filtered = filter_by_pct_threshold(stocks, threshold=0.4)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["code"], "2317")

        invalid_stocks = [{"code": "9999", "pct": "0.5"}]
        with self.assertRaises(TypeError):
            filter_by_pct_threshold(invalid_stocks, threshold=Decimal("0.4"))

    def test_rank_stocks_secondary_and_tertiary_sorting(self):
        """直接呼叫正式高精度排序函式 rank_stocks 驗證三級確定性穩定排序：
        1. pct (降序)
        2. trust_shares (降序)
        3. code (升序，如 2317 優先於 2330)
        """
        stocks = [
            {"code": "2330", "pct": Decimal("0.5"), "trust_shares": 500},  # 同 pct, 同 trust_shares
            {"code": "2317", "pct": Decimal("0.5"), "trust_shares": 500},  # 同 pct, 同 trust_shares -> 2317 應優先
            {"code": "2454", "pct": Decimal("0.5"), "trust_shares": 1000}, # 同 pct, trust_shares 較大 -> 應排第一
            {"code": "3008", "pct": Decimal("0.8"), "trust_shares": 100}   # pct 最高 -> 第一名
        ]
        ranked = rank_stocks(stocks, top_n=4)
        self.assertEqual([s["code"] for s in ranked], ["3008", "2454", "2317", "2330"])

    def test_rank_stocks_none_safety(self):
        """直接呼叫正式高精度排序函式 rank_stocks 驗證：
        當候選股票清單包含 pct=None 缺值個股時，不會引發 TypeError 崩潰，且缺值股票被安全排除不編列排名
        """
        stocks = [
            {"code": "2330", "pct": None, "trust_shares": 400},
            {"code": "2317", "pct": Decimal("0.005"), "trust_shares": 500},
            {"code": "2454", "pct": Decimal("0"), "trust_shares": 0}
        ]
        ranked = rank_stocks(stocks, top_n=2)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["code"], "2317")

    def test_end_to_end_pipeline_from_fixture(self):
        """端到端測試 (End-to-End Pipeline Test)：
        模擬官方 Open API JSON 輸入 -> 經由 parse_int -> calculate_pct -> rank_stocks -> format_pct_for_csv 產出 CSV 資料
        驗證全鏈路計算、過濾、穩定排序與顯示格式化正確性
        """
        # 1. 模擬發行股數 API 資料 Fixture
        raw_shares = [
            {"公司代號": "2330", "已發行普通股數或TDR原股發行股數": "10,000,000"},
            {"公司代號": "2317", "已發行普通股數或TDR原股發行股數": "5,000,000"},
            {"公司代號": "9999", "已發行普通股數或TDR原股發行股數": "--"} # 無效發行股數
        ]
        shares_map = {}
        for r in raw_shares:
            code = r["公司代號"]
            cnt = parse_int(r["已發行普通股數或TDR原股發行股數"])
            if code and cnt is not None and cnt > 0:
                shares_map[code] = cnt

        # 2. 模擬法人買賣超 API 資料 Fixture
        raw_trading = [
            {"code": "2330", "name": "台積電", "close": "1000", "trust_str": "500"},  # pct = 0.005%
            {"code": "2317", "name": "鴻海", "close": "200", "trust_str": "500"},   # pct = 0.010%
            {"code": "9999", "name": "缺值股", "close": "50", "trust_str": "100"}   # issued_shares missing
        ]

        stocks = []
        for r in raw_trading:
            trust_shares = parse_int(r["trust_str"])
            issued_shares = shares_map.get(r["code"], None)
            try:
                pct = calculate_pct(trust_shares, issued_shares)
            except ValueError:
                pct = None
            stocks.append({
                "code": r["code"], "name": r["name"], "close": r["close"],
                "trust_shares": trust_shares, "pct": pct
            })

        # 3. 呼叫正式 rank_stocks 高精度穩定排序
        ranked = rank_stocks(stocks, top_n=10)
        self.assertEqual(len(ranked), 2) # 缺值股 (9999) 排除
        self.assertEqual(ranked[0]["code"], "2317") # pct 0.01% 第一
        self.assertEqual(ranked[1]["code"], "2330") # pct 0.005% 第二

        # 4. 呼叫正式 format_pct_for_csv 端到端格式化 CSV 列
        csv_rows = []
        for rank, s in enumerate(ranked, 1):
            pct_str = format_pct_for_csv(s["pct"])
            csv_rows.append([str(rank), s["code"], s["name"], s["close"], pct_str])

        self.assertEqual(csv_rows[0], ["1", "2317", "鴻海", "200", "+0.01"])
        self.assertEqual(csv_rows[1], ["2", "2330", "台積電", "1000", "+0.01"])

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
