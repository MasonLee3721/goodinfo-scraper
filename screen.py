"""
投信認養篩選器
條件：
  基本：買超佔股本比 >= 0.68 且 排名前 30
  加分：首次進榜、連買次數、前 30 名

執行：uv run --with pandas python3 screen.py
"""
import os, glob, argparse
import pandas as pd

PCT_COL = "當日買賣超佔發行張數"
MIN_PCT = 0.68
TOP_N = 30

def load_all(folder="data"):
    files = sorted(glob.glob(os.path.join(folder, "*.csv")))
    if not files:
        print("找不到資料，請先執行 scrape_goodinfo.py")
        return None, []
    dfs = []
    for f in files:
        df = pd.read_csv(f, dtype=str)
        df["日期"] = os.path.basename(f).replace(".csv", "")
        dfs.append(df)
    dates = [os.path.basename(f).replace(".csv", "") for f in files]
    return pd.concat(dfs, ignore_index=True), dates

def screen():
    df, dates = load_all(os.path.join(os.path.dirname(__file__), "data"))
    if df is None:
        return

    df[PCT_COL] = pd.to_numeric(df[PCT_COL], errors="coerce")
    df["排名"] = pd.to_numeric(df["排名"], errors="coerce")

    latest_date = dates[-1]
    prev_date = dates[-2] if len(dates) >= 2 else None

    today = df[df["日期"] == latest_date].copy()
    prev_codes = set(df[df["日期"] == prev_date]["代號"]) if prev_date else set()

    # 基本篩選：買超 >= 0.68 且 排名前 30
    filtered = today[
        (today[PCT_COL] >= MIN_PCT) &
        (today["排名"] <= TOP_N)
    ].copy()

    if filtered.empty:
        print(f"[{latest_date}] 無符合條件的股票（買超≥{MIN_PCT}% 且 前{TOP_N}名）")
        return

    # 連買次數
    def consec_days(code):
        rows = df[df["代號"] == code].sort_values("日期")
        count = 0
        for _, r in rows.iloc[::-1].iterrows():
            if pd.notna(r[PCT_COL]) and r[PCT_COL] > 0:
                count += 1
            else:
                break
        return count

    filtered["連買天數"] = filtered["代號"].apply(consec_days)

    # 首次進榜（昨天不在榜上）
    filtered["首次進榜"] = filtered["代號"].apply(
        lambda c: "🆕" if c not in prev_codes else ""
    )

    # 前 30 名加分標記
    filtered["前30名"] = filtered["排名"].apply(lambda r: "⭐" if r <= 30 else "")

    # 排序：連買天數多 > 買超幅度大
    filtered = filtered.sort_values(["連買天數", PCT_COL], ascending=[False, False])

    print(f"\n📅 {latest_date}  投信認養名單")
    print(f"條件：買超佔股本比 ≥ {MIN_PCT}%  且  排名前 {TOP_N}\n")
    print(f"{'排名':>4} {'代號':<8} {'名稱':<12} {'買超%':>6} {'連買':>4} {'首次':>4} {'前30':>4}")
    print("─" * 55)
    for _, r in filtered.iterrows():
        print(f"{int(r['排名']):>4} {r['代號']:<8} {r['名稱']:<12} "
              f"{r[PCT_COL]:>+6.2f} {int(r['連買天數']):>4}天 "
              f"{r['首次進榜']:>4} {r['前30名']:>4}")

    print(f"\n共 {len(filtered)} 支")

if __name__ == "__main__":
    screen()
