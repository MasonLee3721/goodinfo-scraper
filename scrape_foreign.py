"""
爬取 Goodinfo 外資、投信同步買超當日排行，存成每日 CSV 並 push 到 GitHub
執行：uv run --with requests --with beautifulsoup4 --with lxml python3 scrape_foreign.py
"""
import requests, time, csv, os, subprocess
from datetime import date
from bs4 import BeautifulSoup

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

API = (
    "https://goodinfo.tw/tw2/StockList.asp?STEP=DATA"
    "&MARKET_CAT=%E6%99%BA%E6%85%A7%E9%81%B8%E8%82%A1"
    "&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E3%80%81%E6%8A%95%E4%BF%A1%E5%90%8C%E6%AD%A5%E8%B2%B7%E8%B6%85%E2%80%93%E7%95%B6%E6%97%A5%40%40%E5%A4%96%E8%B3%87%E3%80%81%E6%8A%95%E4%BF%A1%E5%90%8C%E6%AD%A5%E8%B2%B7%E8%B6%85%40%40%E7%95%B6%E6%97%A5"
    "&SHEET=%E6%B3%95%E4%BA%BA%E8%B2%B7%E8%B3%A3%5F%E4%B8%89%E5%A4%A7"
    "&SHEET2=%E6%B3%95%E4%BA%BA%E8%B2%B7%E8%B3%A3%E5%BC%B5%E6%95%B8%28%E6%97%A5%29"
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

def save(headers, data, folder="data_foreign"):
    os.makedirs(os.path.join(REPO_DIR, folder), exist_ok=True)
    trade_date = data[0][6] if len(data[0]) > 6 else str(date.today())
    # 有些欄位排列不同，嘗試從第一筆找日期格式 MM/DD
    for cell in data[0]:
        if "/" in cell and len(cell) == 5:
            trade_date = cell
            break
    year = date.today().year
    month, day = trade_date.split("/")
    filename = f"{folder}/{year}-{month}-{day}.csv"
    filepath = os.path.join(REPO_DIR, filename)

    if os.path.exists(filepath):
        print(f"今日資料已存在：{filename}，略過")
        return None

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data)
    print(f"已存檔：{filename}（{len(data)} 筆）")
    return filename

def git_push(filename):
    token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    remote = f"https://{token}@github.com/MasonLee3721/goodinfo-scraper.git"

    def run(cmd):
        subprocess.run(cmd, cwd=REPO_DIR, check=True)

    run(["git", "remote", "set-url", "origin", remote])
    run(["git", "add", filename])
    run(["git", "commit", "-m", f"data(foreign): {os.path.basename(filename)}"])
    run(["git", "push"])
    print(f"已 push 到 GitHub：{filename}")

if __name__ == "__main__":
    print("抓取外資投信同買...")
    html = fetch()
    headers, data = parse(html)
    print(f"共 {len(data)} 筆，欄位：{headers[:6]}")
    filename = save(headers, data)
    if filename:
        git_push(filename)
