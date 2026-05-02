"""
技術面強勢股篩選
資料來源：台灣證交所 + 櫃買中心官方 API
條件（嚴格版）：
  1. 均線多頭排列：5MA > 20MA > 60MA
  2. 20MA 向上斜（今日 > 5日前）
  3. RSI(14) 介於 50~80
  4. 近 5 日漲幅 > 0
  5. 今日量 > 5日均量 × 1.5（放量）
  6. 創 20 日新高

執行：uv run --with pandas --with requests python3 tech_screen.py
      uv run --with pandas --with requests python3 tech_screen.py --codes 6706 6147 6187
"""
import requests, time, argparse
from datetime import date, timedelta
import pandas as pd

def fetch_twse(code, ym):
    """證交所（上市）"""
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?stockNo={code}&date={ym}01&response=json"
    r = requests.get(url, timeout=10, verify=False)
    d = r.json()
    if d.get("stat") != "OK" or not d.get("data"):
        return None
    rows = []
    for row in d["data"]:
        try:
            rows.append({
                "date": row[0],
                "open": float(row[3].replace(",", "")),
                "high": float(row[4].replace(",", "")),
                "low":  float(row[5].replace(",", "")),
                "close": float(row[6].replace(",", "")),
                "volume": int(row[0] and row[1].replace(",", "")),
            })
        except:
            continue
    return rows

def fetch_otc(code, ym):
    """櫃買中心（上櫃）"""
    y = int(ym[:4]) - 1911  # 民國年
    m = ym[4:6]
    url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?l=zh-tw&d={y}/{m}&stkno={code}&s=0,asc"
    try:
        r = requests.get(url, timeout=10, verify=False)
        d = r.json()
    except Exception:
        return None
    if not d.get("aaData"):
        return None
    rows = []
    for row in d["aaData"]:
        try:
            rows.append({
                "date": row[0],
                "open": float(row[3].replace(",", "")),
                "high": float(row[4].replace(",", "")),
                "low":  float(row[5].replace(",", "")),
                "close": float(row[6].replace(",", "")),
                "volume": int(row[1].replace(",", "")),
            })
        except:
            continue
    return rows or None

def get_kline(code, months=4):
    """取得近 N 個月的日K，自動判斷上市/上櫃"""
    all_rows = []
    today = date.today()
    for i in range(months - 1, -1, -1):
        # 往前推 i 個月（正確計算跨年）
        total_months = today.year * 12 + today.month - 1 - i
        year = total_months // 12
        month = total_months % 12 + 1
        ym = f"{year}{month:02d}"
        rows = fetch_twse(code, ym)
        if not rows:
            rows = fetch_otc(code, ym)
        if rows:
            all_rows.extend(rows)
        time.sleep(0.3)

    if not all_rows:
        return None
    df = pd.DataFrame(all_rows).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    return df

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def check_strong(code, name=""):
    df = get_kline(code, months=5)
    if df is None or len(df) < 65:
        return None, f"{code} {name}: 資料不足"

    close = df["close"]
    volume = df["volume"]

    ma5  = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    rsi  = calc_rsi(close)

    last = len(df) - 1

    c  = close.iloc[last]
    v  = volume.iloc[last]
    v5 = volume.iloc[last-4:last+1].mean()

    cond = {
        "均線多頭排列": (ma5.iloc[last] > ma20.iloc[last] > ma60.iloc[last]),
        "20MA向上":    (ma20.iloc[last] > ma20.iloc[last - 5]),
        "RSI 50~80":  (50 <= rsi.iloc[last] <= 80),
        "近5日漲幅>0": (c > close.iloc[last - 5]),
        "放量":        (v > v5 * 1.5),
        "創20日新高":  (c >= close.iloc[last-19:last+1].max()),
    }

    passed = sum(cond.values())
    all_pass = all(cond.values())

    return {
        "代號": code, "名稱": name,
        "收盤": c, "RSI": round(rsi.iloc[last], 1),
        "通過條件": f"{passed}/6",
        "強勢": "✅" if all_pass else "❌",
        **{k: "✓" if v else "✗" for k, v in cond.items()}
    }, None

def main(codes_names):
    results = []
    for code, name in codes_names:
        print(f"  分析 {code} {name}...", end=" ", flush=True)
        result, err = check_strong(code, name)
        if err:
            print(f"略過（{err}）")
        else:
            print(f"{'✅ 強勢' if result['強勢'] == '✅' else '❌'} RSI={result['RSI']} {result['通過條件']}")
            results.append(result)

    if not results:
        print("無結果")
        return

    df = pd.DataFrame(results)
    strong = df[df["強勢"] == "✅"]

    print(f"\n{'='*60}")
    print(f"技術面強勢股：{len(strong)}/{len(df)} 支\n")
    if not strong.empty:
        cols = ["代號", "名稱", "收盤", "RSI", "通過條件", "均線多頭排列", "20MA向上", "RSI 50~80", "近5日漲幅>0", "放量", "創20日新高"]
        print(strong[cols].to_string(index=False))
    else:
        print("本次無符合所有條件的強勢股")
        print("\n各股條件明細：")
        cols = ["代號", "名稱", "通過條件", "均線多頭排列", "20MA向上", "RSI 50~80", "近5日漲幅>0", "放量", "創20日新高"]
        print(df[cols].to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--codes", nargs="+", help="指定股票代號，例如 6706 6147")
    args = parser.parse_args()

    if args.codes:
        codes_names = [(c, "") for c in args.codes]
    else:
        # 預設：讀 screen.py 篩出的名單
        import glob, os, csv
        BASE = os.path.dirname(os.path.abspath(__file__))
        files = sorted(glob.glob(os.path.join(BASE, "data", "*.csv")))
        if not files:
            print("找不到投信資料，請先跑 scrape_goodinfo.py")
            exit(1)
        latest = files[-1]
        codes_names = []
        with open(latest, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    if float(row["當日買賣超佔發行張數"]) >= 0.68 and int(row["排名"]) <= 30:
                        codes_names.append((row["代號"], row["名稱"]))
                except:
                    continue

    print(f"分析 {len(codes_names)} 支股票...\n")
    main(codes_names)
