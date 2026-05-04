"""
投信連買趨勢觀察
功能：找出連買中的股票，並判斷買超幅度趨勢（遞增/遞減/持平）
執行：uv run --with pandas python3 trust_trend.py
"""
import os, glob
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
PCT_COL = "當日買賣超佔發行張數"

def load_all():
    files = sorted(glob.glob(os.path.join(BASE, "data", "*.csv")))
    if not files:
        print("找不到資料，請先執行 scrape_goodinfo.py")
        return None, []
    dfs = []
    for f in files:
        df = pd.read_csv(f, dtype=str)
        df["日期"] = os.path.basename(f).replace(".csv", "")
        dfs.append(df)
    all_df = pd.concat(dfs, ignore_index=True)
    all_df[PCT_COL] = pd.to_numeric(all_df[PCT_COL], errors="coerce")
    all_df["排名"] = pd.to_numeric(all_df["排名"], errors="coerce")
    dates = sorted(set(all_df["日期"]))
    return all_df, dates

def get_trend(values):
    """判斷最近幾天的趨勢方向"""
    if len(values) < 2:
        return "➡️"
    ups = sum(1 for i in range(1, len(values)) if values[i] > values[i-1])
    downs = sum(1 for i in range(1, len(values)) if values[i] < values[i-1])
    if ups > downs:
        return "📈"
    elif downs > ups:
        return "📉"
    return "➡️"

def main():
    all_df, dates = load_all()
    if all_df is None:
        return

    latest = dates[-1]
    today = all_df[all_df["日期"] == latest].copy()

    # 找出今日有買超的股票
    today_buys = today[today[PCT_COL] > 0][["代號", "名稱", PCT_COL, "排名"]].copy()

    results = []
    for _, row in today_buys.iterrows():
        code = row["代號"]
        # 取該股票所有歷史紀錄，按日期排序
        hist = all_df[all_df["代號"] == code].sort_values("日期")
        hist = hist[hist[PCT_COL] > 0]  # 只看買超 > 0 的天

        # 計算連買天數（從最新往前連續）
        all_dates_sorted = hist["日期"].tolist()
        all_vals = hist[PCT_COL].tolist()

        # 從最後一天往前找連續天數
        consec = 0
        consec_vals = []
        for d, v in zip(reversed(all_dates_sorted), reversed(all_vals)):
            consec += 1
            consec_vals.insert(0, v)
            # 檢查是否連續（中間沒有斷）
            idx = dates.index(d) if d in dates else -1
            if consec > 1:
                prev_d = consec_vals  # 已在連續中
            # 簡單判斷：只要在有資料的日期裡連續出現就算
            if consec >= 2:
                break  # 先取最近幾天即可

        # 重新計算：取最近連續買超的天數和數值
        consec = 0
        consec_vals = []
        prev_idx = None
        for d, v in zip(reversed(all_dates_sorted), reversed(all_vals)):
            cur_idx = dates.index(d) if d in dates else None
            if prev_idx is not None and cur_idx is not None:
                if prev_idx - cur_idx != 1:
                    break  # 中間有斷
            consec += 1
            consec_vals.insert(0, v)
            prev_idx = cur_idx

        if consec < 1:
            continue

        trend = get_trend(consec_vals)
        avg = sum(consec_vals) / len(consec_vals)
        latest_val = consec_vals[-1]

        results.append({
            "代號": code,
            "名稱": row["名稱"],
            "排名": int(row["排名"]) if pd.notna(row["排名"]) else 999,
            "今日買超%": latest_val,
            "連買天數": consec,
            "趨勢": trend,
            "平均買超%": avg,
            "近期數值": consec_vals,
        })

    if not results:
        print(f"[{latest}] 今日無連買股票")
        return

    df = pd.DataFrame(results)

    # 方向三篩選：📈遞增 + 連買≥2天 + 買超≥0.2%
    df = df[(df["趨勢"] == "📈") & (df["連買天數"] >= 2) & (df["今日買超%"] >= 0.2)].copy()

    if df.empty:
        print(f"[{latest}] 無符合條件的股票（📈遞增 + 連買≥2天 + 買超≥0.2%）")
        return

    df = df.sort_values(["連買天數", "今日買超%"], ascending=[False, False]).reset_index(drop=True)

    print(f"\n📅 {latest}  投信連買趨勢觀察")
    print(f"篩選條件：📈遞增 + 連買≥2天 + 買超≥0.2%")
    print(f"{'─'*65}")
    print(f"{'排名':>4} {'代號':<6} {'名稱':<10} {'今日買超%':>8} {'連買':>4} {'趨勢':>4} {'平均%':>6}  近期走勢")
    print(f"{'─'*65}")

    for _, r in df.iterrows():
        vals_str = " → ".join(f"{v:+.2f}" for v in r["近期數值"])
        print(f"{r['排名']:>4} {r['代號']:<6} {r['名稱']:<10} "
              f"{r['今日買超%']:>+8.2f} {r['連買天數']:>3}天 "
              f"{r['趨勢']:>4} {r['平均買超%']:>+6.2f}  {vals_str}")

    print(f"\n共 {len(df)} 支符合條件（📈遞增 + 連買≥2天 + 買超≥0.2%）")

if __name__ == "__main__":
    main()
