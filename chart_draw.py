"""
自繪 K 線圖：從證交所/櫃買抓資料，用 mplfinance 畫出含均線、KD、MACD 的技術圖
用法：python3 chart_draw.py 6706
"""
import sys, warnings, requests, time
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from datetime import date, timedelta
from pathlib import Path

warnings.filterwarnings('ignore')

# 載入中文字型
_font_path = '/home/agent/fonts/NotoSansCJK.otf'
if Path(_font_path).exists():
    fm.fontManager.addfont(_font_path)
    plt.rcParams['font.family'] = ['Noto Sans CJK TC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

STOCK_ID = sys.argv[1] if len(sys.argv) > 1 else '6706'
OUT_DIR = Path(__file__).parent / 'charts'
OUT_DIR.mkdir(exist_ok=True)

# ── 抓資料（TWSE 上市 / OTC 上櫃）──────────────────────────────────────────
def fetch_twse(stock_id, ym):
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?stockNo={stock_id}&date={ym}01&response=json"
    r = requests.get(url, verify=False, timeout=10)
    d = r.json()
    if d.get('stat') != 'OK' or not d.get('data'):
        return []
    return d['data']

def fetch_otc(stock_id, ym):
    try:
        y = int(ym[:4]) - 1911
        m = ym[4:]
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?l=zh-tw&d={y}/{m}&stkno={stock_id}"
        r = requests.get(url, verify=False, timeout=10)
        d = r.json()
        return d.get('aaData', [])
    except:
        return []

def roc_to_ad(s):
    """民國年 115/04/01 → 2026-04-01"""
    p = s.replace('-', '/').split('/')
    return f"{int(p[0])+1911}-{p[1]}-{p[2]}"

def get_kline(stock_id, months=5):
    rows = []
    today = date.today()
    for i in range(months, -1, -1):
        d = today - timedelta(days=30 * i)
        ym = d.strftime('%Y%m')
        data = fetch_twse(stock_id, ym)
        if not data:
            data = fetch_otc(stock_id, ym)
            if data:
                # OTC 格式轉換
                for row in data:
                    try:
                        rows.append({
                            'Date': roc_to_ad(row[0]),
                            'Open': float(row[3].replace(',', '')),
                            'High': float(row[4].replace(',', '')),
                            'Low':  float(row[5].replace(',', '')),
                            'Close': float(row[6].replace(',', '')),
                            'Volume': int(row[1].replace(',', '')) // 1000  # 股→張
                        })
                    except: pass
        else:
            for row in data:
                try:
                    rows.append({
                        'Date': roc_to_ad(row[0]),
                        'Open': float(row[3].replace(',', '')),
                        'High': float(row[4].replace(',', '')),
                        'Low':  float(row[5].replace(',', '')),
                        'Close': float(row[6].replace(',', '')),
                        'Volume': int(row[1].replace(',', '')) // 1000  # 股→張
                    })
                except: pass
        time.sleep(0.3)

    if not rows:
        return None

    df = pd.DataFrame(rows).drop_duplicates('Date')
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').set_index('Date')
    return df

# ── 計算指標 ────────────────────────────────────────────────────────────────
def calc_rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(n).mean()
    loss = (-delta.clip(upper=0)).rolling(n).mean()
    rs = gain / loss
    return 100 - 100 / (1 + rs)

def calc_macd(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = (dif - dea) * 2
    return dif, dea, hist

def calc_kd(high, low, close, n=9):
    low_n  = low.rolling(n).min()
    high_n = high.rolling(n).max()
    rsv = (close - low_n) / (high_n - low_n) * 100
    K = rsv.ewm(com=2, adjust=False).mean()
    D = K.ewm(com=2, adjust=False).mean()
    return K, D

# ── 畫圖 ────────────────────────────────────────────────────────────────────
def draw_chart(stock_id):
    print(f"抓取 {stock_id} 資料中...")
    df = get_kline(stock_id)
    if df is None or len(df) < 30:
        print(f"資料不足，無法畫圖")
        return None

    # 只取最近 90 天
    df = df.tail(90).copy()

    # 計算指標
    rsi = calc_rsi(df['Close'])
    dif, dea, hist = calc_macd(df['Close'])
    K, D = calc_kd(df['High'], df['Low'], df['Close'])
    ma5  = df['Close'].rolling(5).mean()
    ma20 = df['Close'].rolling(20).mean()
    ma60 = df['Close'].rolling(60).mean()

    # 用 matplotlib 直接畫，完全控制格式
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle

    fig, axes = plt.subplots(5, 1, figsize=(14, 12),
                             gridspec_kw={'height_ratios': [4, 1, 1.2, 1.2, 1.5]},
                             sharex=True)
    fig.subplots_adjust(hspace=0.05)

    ax_k, ax_vol, ax_rsi, ax_kd, ax_macd = axes

    # ── K 線 ──
    dates = mdates.date2num(df.index.to_pydatetime())
    w = 0.6
    for i, (dt, row) in enumerate(df.iterrows()):
        color = '#ef233c' if row['Close'] >= row['Open'] else '#4cc9f0'
        # 實體
        ax_k.add_patch(Rectangle(
            (dates[i] - w/2, min(row['Open'], row['Close'])),
            w, abs(row['Close'] - row['Open']),
            color=color, zorder=3
        ))
        # 影線
        ax_k.plot([dates[i], dates[i]], [row['Low'], row['High']], color=color, lw=0.8, zorder=2)

    ax_k.plot(dates, ma5,  color='#ff6b6b', lw=1.2, label='MA5')
    ax_k.plot(dates, ma20, color='#ffd93d', lw=1.2, label='MA20')
    ax_k.plot(dates, ma60, color='#00cfff', lw=1.2, label='MA60')
    ax_k.set_ylabel('Price', fontsize=9)
    ax_k.legend(loc='upper left', fontsize=8)
    ax_k.set_title(f'Stock {stock_id}  Daily K-Chart  (MA5/20/60 · RSI · KD · MACD)', fontsize=12, color='#dddddd')
    ax_k.xaxis_date()

    # ── 成交量 ──
    for i, (dt, row) in enumerate(df.iterrows()):
        color = '#ef233c' if row['Close'] >= row['Open'] else '#4cc9f0'
        ax_vol.bar(dates[i], row['Volume'], width=w, color=color, alpha=0.8)
    ax_vol.set_ylabel('量(張)', fontsize=9)
    ax_vol.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x/10000:.1f}萬' if x >= 10000 else f'{x:.0f}'))

    # ── RSI ──
    ax_rsi.plot(dates, rsi, color='#845ec2', lw=1.2)
    ax_rsi.axhline(70, color='gray', ls='--', lw=0.8)
    ax_rsi.axhline(30, color='gray', ls='--', lw=0.8)
    ax_rsi.set_ylim(0, 100)
    ax_rsi.set_yticks([30, 50, 70])
    ax_rsi.set_ylabel('RSI', fontsize=9)

    # ── KD ──
    ax_kd.plot(dates, K, color='#f9844a', lw=1.2, label='K')
    ax_kd.plot(dates, D, color='#4d908e', lw=1.2, label='D')
    ax_kd.axhline(80, color='gray', ls='--', lw=0.8)
    ax_kd.axhline(20, color='gray', ls='--', lw=0.8)
    ax_kd.set_ylim(0, 100)
    ax_kd.set_yticks([20, 50, 80])
    ax_kd.set_ylabel('KD', fontsize=9)
    ax_kd.legend(loc='upper left', fontsize=8)

    # ── MACD ──
    ax_macd.plot(dates, dif, color='#f9844a', lw=1.2, label='DIF')
    ax_macd.plot(dates, dea, color='#4d908e', lw=1.2, label='DEA')
    bar_colors = ['#ef233c' if v >= 0 else '#4cc9f0' for v in hist.fillna(0)]
    ax_macd.bar(dates, hist, width=w, color=bar_colors, alpha=0.8)
    ax_macd.axhline(0, color='gray', lw=0.8)
    ax_macd.set_ylabel('MACD', fontsize=9)
    ax_macd.legend(loc='upper left', fontsize=8)

    # X 軸日期格式（西元年）
    ax_macd.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax_macd.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0, interval=2))
    plt.setp(ax_macd.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=8)

    # 背景
    for ax in axes:
        ax.set_facecolor('#1a1a2e')
        ax.tick_params(colors='#aaa', labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor('#333')
    fig.patch.set_facecolor('#0f0f1a')

    out_path = str(OUT_DIR / f'{stock_id}.png')
    plt.savefig(out_path, dpi=120, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    print(f"圖表已儲存：{out_path}")
    return out_path

if __name__ == '__main__':
    draw_chart(STOCK_ID)
