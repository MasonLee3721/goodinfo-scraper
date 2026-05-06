"""
用 TWSE/OTC API 抓資料畫 K 線圖（不依賴 yfinance）
用法：python3 chart_draw_twse.py 8155
"""
import sys, time, warnings, requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from pathlib import Path

warnings.filterwarnings('ignore')

# 中文字型
_font_path = '/home/agent/fonts/NotoSansCJK.otf'
if Path(_font_path).exists():
    import matplotlib.font_manager as fm
    fm.fontManager.addfont(_font_path)
    plt.rcParams['font.family'] = ['Noto Sans CJK TC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

STOCK_ID = sys.argv[1] if len(sys.argv) > 1 else '8155'
OUT_DIR = Path(__file__).parent / 'charts'
OUT_DIR.mkdir(exist_ok=True)

def fetch_twse(code, ym):
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={ym}01&stockNo={code}"
    try:
        r = requests.get(url, timeout=10, verify=False)
        d = r.json()
        if d.get('stat') != 'OK': return []
        rows = []
        for row in d['data']:
            try:
                date_str = row[0].replace('/', '-')
                y, m, day = date_str.split('-')
                date = f"{int(y)+1911}-{m}-{day}"
                rows.append({
                    'date': pd.to_datetime(date),
                    'Open':   float(row[3].replace(',', '')),
                    'High':   float(row[4].replace(',', '')),
                    'Low':    float(row[5].replace(',', '')),
                    'Close':  float(row[6].replace(',', '')),
                    'Volume': int(row[1].replace(',', '')) // 1000,
                })
            except: continue
        return rows
    except: return []

def fetch_otc(code, ym):
    y = int(ym[:4]) - 1911
    m = int(ym[4:])
    url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?l=zh-tw&d={y}/{m:02d}&stkno={code}"
    try:
        r = requests.get(url, timeout=10, verify=False)
        d = r.json()
        if not d.get('aaData'): return []
        rows = []
        for row in d['aaData']:
            try:
                parts = row[0].split('/')
                date = f"{int(parts[0])+1911}-{parts[1]}-{parts[2]}"
                rows.append({
                    'date': pd.to_datetime(date),
                    'Open':   float(row[3].replace(',', '')),
                    'High':   float(row[4].replace(',', '')),
                    'Low':    float(row[5].replace(',', '')),
                    'Close':  float(row[6].replace(',', '')),
                    'Volume': int(row[1].replace(',', '')) // 1000,
                })
            except: continue
        return rows
    except: return []

def get_kline(code, months=5):
    from datetime import date
    today = date.today()
    all_rows = []
    for i in range(months - 1, -1, -1):
        total = today.year * 12 + today.month - 1 - i
        ym = f"{total // 12}{total % 12 + 1:02d}"
        rows = fetch_twse(code, ym) or fetch_otc(code, ym)
        if rows: all_rows.extend(rows)
        time.sleep(0.3)
    if not all_rows: return None
    df = pd.DataFrame(all_rows).drop_duplicates('date').sort_values('date').reset_index(drop=True)
    df = df.set_index('date')
    df.index.name = 'Date'
    return df

def calc_rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(n).mean()
    loss = (-delta.clip(upper=0)).rolling(n).mean()
    rs = gain / loss
    return 100 - 100 / (1 + rs)

def calc_macd(close, fast=12, slow=26, signal=9):
    dif = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    dea = dif.ewm(span=signal, adjust=False).mean()
    return dif, dea, (dif - dea) * 2

def calc_kd(high, low, close, n=9):
    low_n  = low.rolling(n).min()
    high_n = high.rolling(n).max()
    rsv = (close - low_n) / (high_n - low_n) * 100
    K = rsv.ewm(com=2, adjust=False).mean()
    D = K.ewm(com=2, adjust=False).mean()
    return K, D

def draw_chart(stock_id):
    print(f"抓取 {stock_id} 資料中...")
    df = get_kline(stock_id)
    if df is None or len(df) < 20:
        print(f"資料不足，無法畫圖")
        return None

    df = df.tail(90).copy()
    rsi = calc_rsi(df['Close'])
    dif, dea, hist = calc_macd(df['Close'])
    K, D = calc_kd(df['High'], df['Low'], df['Close'])
    ma5  = df['Close'].rolling(5).mean()
    ma20 = df['Close'].rolling(20).mean()
    ma60 = df['Close'].rolling(60).mean()

    fig, axes = plt.subplots(5, 1, figsize=(14, 12),
                             gridspec_kw={'height_ratios': [4, 1, 1.2, 1.2, 1.5]},
                             sharex=True)
    fig.subplots_adjust(hspace=0.05)
    ax_k, ax_vol, ax_rsi, ax_kd, ax_macd = axes

    dates = mdates.date2num(df.index.to_pydatetime())
    w = 0.6
    for i, (dt, row) in enumerate(df.iterrows()):
        color = '#ef233c' if row['Close'] >= row['Open'] else '#4cc9f0'
        ax_k.add_patch(Rectangle(
            (dates[i] - w/2, min(row['Open'], row['Close'])),
            w, abs(row['Close'] - row['Open']), color=color, zorder=3
        ))
        ax_k.plot([dates[i], dates[i]], [row['Low'], row['High']], color=color, lw=0.8, zorder=2)

    ax_k.plot(dates, ma5,  color='#ff6b6b', lw=1.2, label='MA5')
    ax_k.plot(dates, ma20, color='#ffd93d', lw=1.2, label='MA20')
    ax_k.plot(dates, ma60, color='#00cfff', lw=1.2, label='MA60')
    ax_k.set_ylabel('Price', fontsize=9)
    ax_k.legend(loc='upper left', fontsize=8)
    ax_k.set_title(f'Stock {stock_id}  Daily K-Chart  (MA5/20/60 · RSI · KD · MACD)', fontsize=12, color='#dddddd')
    ax_k.xaxis_date()

    for i, (dt, row) in enumerate(df.iterrows()):
        color = '#ef233c' if row['Close'] >= row['Open'] else '#4cc9f0'
        ax_vol.bar(dates[i], row['Volume'], width=w, color=color, alpha=0.8)
    ax_vol.set_ylabel('量(張)', fontsize=9)

    ax_rsi.plot(dates, rsi, color='#845ec2', lw=1.2)
    ax_rsi.axhline(70, color='gray', ls='--', lw=0.8)
    ax_rsi.axhline(30, color='gray', ls='--', lw=0.8)
    ax_rsi.set_ylim(0, 100); ax_rsi.set_yticks([30, 50, 70]); ax_rsi.set_ylabel('RSI', fontsize=9)

    ax_kd.plot(dates, K, color='#f9844a', lw=1.2, label='K')
    ax_kd.plot(dates, D, color='#4d908e', lw=1.2, label='D')
    ax_kd.axhline(80, color='gray', ls='--', lw=0.8)
    ax_kd.axhline(20, color='gray', ls='--', lw=0.8)
    ax_kd.set_ylim(0, 100); ax_kd.set_yticks([20, 50, 80]); ax_kd.set_ylabel('KD', fontsize=9)
    ax_kd.legend(loc='upper left', fontsize=8)

    ax_macd.plot(dates, dif, color='#f9844a', lw=1.2, label='DIF')
    ax_macd.plot(dates, dea, color='#4d908e', lw=1.2, label='DEA')
    bar_colors = ['#ef233c' if v >= 0 else '#4cc9f0' for v in hist.fillna(0)]
    ax_macd.bar(dates, hist, width=w, color=bar_colors, alpha=0.8)
    ax_macd.axhline(0, color='gray', lw=0.8)
    ax_macd.set_ylabel('MACD', fontsize=9)
    ax_macd.legend(loc='upper left', fontsize=8)

    ax_macd.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax_macd.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0, interval=2))
    plt.setp(ax_macd.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=8)

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
