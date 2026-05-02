"""
今日投信認養推薦清單
整合：投信買超 + 外資同買 + 技術面篩選
入選：買超≥0.68% 且 前30名 且 技術面≥4/6
執行：uv run --with pandas --with requests python3 recommend.py
"""
import os, glob, csv, time, warnings
import pandas as pd
import requests
from datetime import date

warnings.filterwarnings("ignore")
BASE = os.path.dirname(os.path.abspath(__file__))
PCT_COL = "當日買賣超佔發行張數"

# ── 載入投信資料 ──────────────────────────────────────────
def load_trust():
    files = sorted(glob.glob(os.path.join(BASE, "data", "*.csv")))
    if not files:
        return None, None, set()
    dfs = []
    for f in files:
        df = pd.read_csv(f, dtype=str)
        df["日期"] = os.path.basename(f).replace(".csv", "")
        dfs.append(df)
    all_df = pd.concat(dfs, ignore_index=True)
    all_df[PCT_COL] = pd.to_numeric(all_df[PCT_COL], errors="coerce")
    all_df["排名"] = pd.to_numeric(all_df["排名"], errors="coerce")
    dates = [os.path.basename(f).replace(".csv", "") for f in files]
    prev_codes = set(all_df[all_df["日期"] == dates[-2]]["代號"]) if len(dates) >= 2 else set()
    return all_df, dates[-1], prev_codes

def consec_days(all_df, code):
    rows = all_df[all_df["代號"] == code].sort_values("日期")
    count = 0
    for _, r in rows.iloc[::-1].iterrows():
        if pd.notna(r[PCT_COL]) and r[PCT_COL] > 0:
            count += 1
        else:
            break
    return count

# ── 載入外資同買 ──────────────────────────────────────────
def load_foreign():
    files = sorted(glob.glob(os.path.join(BASE, "data_foreign", "*.csv")))
    if not files:
        return set()
    df = pd.read_csv(files[-1], dtype=str)
    return set(df["代號"].str.strip())

# ── 技術面分析 ────────────────────────────────────────────
def fetch_twse(code, ym):
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?stockNo={code}&date={ym}01&response=json"
    try:
        r = requests.get(url, timeout=10, verify=False)
        d = r.json()
        if d.get("stat") != "OK" or not d.get("data"):
            return None
        rows = []
        for row in d["data"]:
            try:
                rows.append({"date": row[0], "close": float(row[6].replace(",", "")),
                             "volume": int(row[1].replace(",", ""))})
            except: continue
        return rows or None
    except: return None

def fetch_otc(code, ym):
    y = int(ym[:4]) - 1911
    m = ym[4:6]
    url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?l=zh-tw&d={y}/{m}&stkno={code}&s=0,asc"
    try:
        r = requests.get(url, timeout=10, verify=False)
        d = r.json()
        if not d.get("aaData"): return None
        rows = []
        for row in d["aaData"]:
            try:
                rows.append({"date": row[0], "close": float(row[6].replace(",", "")),
                             "volume": int(row[1].replace(",", ""))})
            except: continue
        return rows or None
    except: return None

def get_kline(code):
    all_rows = []
    today = date.today()
    for i in range(4, -1, -1):
        total = today.year * 12 + today.month - 1 - i
        ym = f"{total // 12}{total % 12 + 1:02d}"
        rows = fetch_twse(code, ym) or fetch_otc(code, ym)
        if rows: all_rows.extend(rows)
        time.sleep(0.3)
    if not all_rows: return None
    df = pd.DataFrame(all_rows).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    return df

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def tech_score(code):
    df = get_kline(code)
    if df is None or len(df) < 65:
        return 0, "資料不足"
    close, volume = df["close"], df["volume"]
    ma5  = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    rsi  = calc_rsi(close)
    i = len(df) - 1
    c, v = close.iloc[i], volume.iloc[i]
    v5 = volume.iloc[i-4:i+1].mean()
    conds = [
        ma5.iloc[i] > ma20.iloc[i] > ma60.iloc[i],
        ma20.iloc[i] > ma20.iloc[i-5],
        50 <= rsi.iloc[i] <= 80,
        c > close.iloc[i-5],
        v > v5 * 1.5,
        c >= close.iloc[i-19:i+1].max(),
    ]
    score = sum(conds)
    detail = "".join("✓" if c else "✗" for c in conds)
    return score, detail

# ── 主程式 ────────────────────────────────────────────────
def main():
    all_df, latest_date, prev_codes = load_trust()
    if all_df is None:
        print("找不到資料"); return

    foreign_codes = load_foreign()
    today = all_df[all_df["日期"] == latest_date]

    # 基本篩選
    candidates = today[(today[PCT_COL] >= 0.68) & (today["排名"] <= 30)].copy()
    if candidates.empty:
        print(f"[{latest_date}] 無符合基本條件的股票"); return

    print(f"📊 基本篩選通過 {len(candidates)} 支，進行技術面分析...\n")

    results = []
    for _, row in candidates.iterrows():
        code, name = row["代號"], row["名稱"]
        print(f"  {code} {name}...", end=" ", flush=True)
        score, detail = tech_score(code)
        print(f"技術 {score}/6 {detail}")
        results.append({
            "代號": code, "名稱": name,
            "買超%": row[PCT_COL],
            "排名": int(row["排名"]),
            "連買天數": consec_days(all_df, code),
            "首次進榜": code not in prev_codes,
            "外資同買": code in foreign_codes,
            "技術分": score,
            "技術明細": detail,
        })

    df = pd.DataFrame(results)
    # 入選：技術面 >= 4/6
    picks = df[df["技術分"] >= 4].copy()
    picks["_sort"] = picks["外資同買"].apply(lambda x: 0 if x else 1)
    picks = picks.sort_values(["_sort", "連買天數", "技術分", "買超%"], ascending=[True, False, False, False])

    print(f"\n{'='*65}")
    print(f"🏆 {latest_date} 今日推薦清單（技術面≥4/6）\n")

    if picks.empty:
        print("今日無符合所有條件的推薦股票")
        print("\n各股技術明細（均線多頭/20MA向上/RSI50-80/5日漲/放量/20日新高）：")
        for _, r in df.iterrows():
            flags = ("🔥" if r["外資同買"] else "") + ("🆕" if r["首次進榜"] else "")
            print(f"  {r['代號']} {r['名稱']:<10} 技術{r['技術分']}/6 {r['技術明細']} 買超{r['買超%']:+.2f}% {flags}")
    else:
        for _, r in picks.iterrows():
            flags = ("🔥外資同買 " if r["外資同買"] else "") + ("🆕首次進榜 " if r["首次進榜"] else "")
            print(f"  {'⭐' if r['排名'] <= 10 else '  '} {r['代號']} {r['名稱']:<10} "
                  f"買超{r['買超%']:+.2f}%  連買{r['連買天數']}天  技術{r['技術分']}/6  {flags}")
            print(f"     技術明細：{r['技術明細']}（均線多頭/20MA向上/RSI/5日漲/放量/20日新高）")

    print(f"\n共推薦 {len(picks)} 支")

if __name__ == "__main__":
    main()
