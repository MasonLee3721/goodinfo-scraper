"""
分析多天投信買超資料
- 找出連續買入的股票
- 觀察買超幅度趨勢（增加/減少/持平）

執行：uv run --with pandas python3 analyze.py
      uv run --with pandas python3 analyze.py --days 5 --min-days 3
"""
import os, glob, argparse
import pandas as pd

def load_all(folder="data"):
    files = sorted(glob.glob(f"{folder}/*.csv"))
    if not files:
        print("找不到資料，請先執行 scrape_goodinfo.py")
        return None
    dfs = []
    for f in files:
        df = pd.read_csv(f, dtype=str)
        # 從檔名取日期
        date_str = os.path.basename(f).replace(".csv", "")
        df["日期"] = date_str
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

def analyze(days=None, min_days=2):
    df = load_all()
    if df is None:
        return

    # 統一欄位名（取買超幅度欄）
    pct_col = "當日買賣超佔發行張數"
    df[pct_col] = pd.to_numeric(df[pct_col], errors="coerce")
    df["成交"] = pd.to_numeric(df["成交"], errors="coerce")

    # 只看最近 N 天
    all_dates = sorted(df["日期"].unique())
    if days:
        all_dates = all_dates[-days:]
        df = df[df["日期"].isin(all_dates)]

    print(f"分析日期範圍：{all_dates[0]} ~ {all_dates[-1]}（共 {len(all_dates)} 個交易日）\n")

    # 每支股票出現幾天
    summary = (
        df.groupby(["代號", "名稱"])
        .agg(
            出現天數=("日期", "count"),
            平均買超幅度=(pct_col, "mean"),
            最新買超幅度=(pct_col, "last"),
            最新成交=("成交", "last"),
        )
        .reset_index()
    )

    # 只留連續出現 >= min_days 天的
    summary = summary[summary["出現天數"] >= min_days].sort_values("出現天數", ascending=False)

    # 計算趨勢：最後兩天的幅度差
    def trend(code):
        rows = df[df["代號"] == code].sort_values("日期")[pct_col].dropna().tolist()
        if len(rows) < 2:
            return "—"
        diff = rows[-1] - rows[-2]
        if diff > 0.05:   return "📈 增加"
        if diff < -0.05:  return "📉 減少"
        return "➡️ 持平"

    summary["趨勢"] = summary["代號"].apply(trend)
    summary["平均買超幅度"] = summary["平均買超幅度"].round(3)
    summary["最新買超幅度"] = summary["最新買超幅度"].round(3)

    print(f"連續 {min_days} 天以上出現在排行的股票（共 {len(summary)} 支）：\n")
    print(summary[["代號", "名稱", "出現天數", "最新買超幅度", "平均買超幅度", "趨勢", "最新成交"]].to_string(index=False))

    # 印出每支股票的每日明細
    print("\n\n--- 每日明細 ---")
    for _, row in summary.iterrows():
        code = row["代號"]
        name = row["名稱"]
        detail = df[df["代號"] == code].sort_values("日期")[["日期", pct_col, "成交"]].to_string(index=False)
        print(f"\n{code} {name}：")
        print(detail)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None, help="只看最近幾個交易日（預設全部）")
    parser.add_argument("--min-days", type=int, default=2, help="至少連續幾天（預設 2）")
    args = parser.parse_args()
    analyze(days=args.days, min_days=args.min_days)
