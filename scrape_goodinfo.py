"""
爬 goodinfo 投信買超排行，並存成每日 CSV
執行：uv run --with requests --with beautifulsoup4 --with lxml python3 scrape_goodinfo.py
"""
import requests, time, csv, os
from datetime import date
from bs4 import BeautifulSoup

API = (
    "https://goodinfo.tw/tw2/StockList.asp?STEP=DATA"
    "&MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C"
    "&INDUSTRY_CAT=%E6%8A%95%E4%BF%A1%E8%B2%B7%E8%B6%85%E4%BD%94%E7%99%BC%E8%A1%8C%E5%BC%B5%E6%95%B8+%E2%80%93+%E7%95%B6%E6%97%A5%40%40%E6%8A%95%E4%BF%A1%E8%B2%B7%E8%B6%85%E4%BD%94%E7%99%BC%E8%A1%8C%E5%BC%B5%E6%95%B8%40%40%E6%8A%95%E4%BF%A1+%E2%80%93+%E7%95%B6%E6%97%A5"
    "&SHEET=%E6%B3%95%E4%BA%BA%E8%B2%B7%E8%B3%A3%E7%B5%B1%E8%A8%88%5F%E6%8A%95%E4%BF%A1"
    "&SHEET2=%E8%B2%B7%E8%B3%A3%E8%B6%85%E4%BD%94%E7%99%BC%E8%A1%8C%E5%BC%B5%E6%95%B8"
    "&RPT_TIME=%E6%9C%80%E6%96%B0%E8%B3%87%E6%96%99"
    "&RANK_RANGE=300"
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Referer": "https://goodinfo.tw/tw/StockList.asp",
}

def fetch():
    session = requests.Session()
    session.get("https://goodinfo.tw/tw/index.asp", headers=HEADERS, timeout=15)
    session.cookies.set("CLIENT_KEY", "2.5|41094.0082828283|46649.5638383838|8|46144.5|46144.5|",
                        domain="goodinfo.tw", path="/")
    time.sleep(1)
    r = session.get(API, headers=HEADERS, timeout=30)
    r.encoding = "utf-8"
    return r.text

def parse(html):
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="tblStockList")
    if not table:
        raise ValueError("找不到資料表，可能被擋了")
    rows = table.find_all("tr")
    headers, data = [], []
    for row in rows:
        ths = row.find_all("th")
        tds = row.find_all("td")
        if ths and not headers:
            headers = [h.get_text(strip=True) for h in ths]
        elif tds:
            data.append([d.get_text(strip=True) for d in tds])
    return headers, data

def save(headers, data, folder="data"):
    os.makedirs(folder, exist_ok=True)
    # 用法人買賣日期當檔名（從第一筆資料取），避免非交易日覆蓋
    trade_date = data[0][6] if data else str(date.today())  # 欄位6 = 法人買賣日期
    # 轉成 YYYY-MM-DD 格式（原始是 MM/DD）
    year = date.today().year
    month, day = trade_date.split("/")
    filename = f"{folder}/{year}-{month}-{day}.csv"

    if os.path.exists(filename):
        print(f"今日資料已存在：{filename}，略過")
        return filename

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data)
    print(f"已存檔：{filename}（{len(data)} 筆）")
    return filename

if __name__ == "__main__":
    print("抓取中...")
    html = fetch()
    headers, data = parse(html)
    save(headers, data)
