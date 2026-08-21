"""
爬 goodinfo 投信買超排行，存成每日 CSV 並 push 到 GitHub
執行：uv run --with requests --with beautifulsoup4 --with lxml python3 scrape_goodinfo.py
"""
import requests, time, csv, os, subprocess, json
from datetime import date
from bs4 import BeautifulSoup

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

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

def fetch_json(url):
    """使用 curl --http1.1 安全擷取官方 Open API JSON 資料，避免 HTTP/2 connection broken"""
    for _ in range(3):
        try:
            out = subprocess.check_output(
                ["curl", "-s", "--http1.1", "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", url],
                timeout=20
            )
            data = json.loads(out)
            if data:
                return data
        except Exception:
            time.sleep(1)
    return []

def fetch_twse_tpex():
    """當 Goodinfo 被 Cloudflare 防火牆擋住時，自動改用證交所 (TWSE) 與櫃買中心 (TPEX) 官方 Open API"""
    print("Goodinfo 被擋，改用 TWSE/TPEX 官方 API 抓取投信買超佔股本資料...")

    # 1. 抓取上市與上櫃股票的發行張數
    shares_map = {}
    twse_shares = fetch_json("https://openapi.twse.com.tw/v1/opendata/t187ap03_L")
    for row in twse_shares:
        code = row.get("公司代號", "").strip()
        cnt = row.get("已發行普通股數或TDR原股發行股數", "0").strip()
        if code and cnt.isdigit():
            shares_map[code] = int(cnt) // 1000

    tpex_shares = fetch_json("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O")
    for row in tpex_shares:
        code = row.get("SecuritiesCompanyCode", "").strip()
        cnt = row.get("IssueShares", "0").strip()
        if code and cnt.isdigit():
            shares_map[code] = int(cnt) // 1000

    # 2. 抓取 TWSE 三大法人買賣超 (上市)
    r_twse = fetch_json("https://www.twse.com.tw/rwd/zh/fund/T86?response=json&selectType=ALL")
    twse_date = r_twse.get("date", "") if isinstance(r_twse, dict) else ""
    if twse_date:
        mm_dd = f"{twse_date[4:6]}/{twse_date[6:]}"
    else:
        mm_dd = date.today().strftime("%m/%d")

    all_stocks = []
    twse_data = r_twse.get("data", []) if isinstance(r_twse, dict) else []
    for row in twse_data:
        code = row[0].strip()
        name = row[1].strip()
        try:
            close_val = row[2].replace(",", "").strip() if len(row) > 2 else ""
            close = close_val if close_val not in ("--", "0", "") else ""
            trust = int(row[10].replace(",", "")) // 1000
            if trust > 0:
                all_stocks.append({"code": code, "name": name, "close": close, "trust": trust})
        except Exception:
            continue

    # 3. 抓取 TPEX 三大法人買賣超 (上櫃)
    r_tpex = fetch_json("https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading")
    if isinstance(r_tpex, list) and r_tpex:
        # 驗證 TWSE 與 TPEX 資料日期一致性
        tpex_date_roc = r_tpex[0].get("Date", "").strip()
        if len(tpex_date_roc) == 7 and tpex_date_roc.isdigit():
            tpex_date_ad = f"{int(tpex_date_roc[:3]) + 1911}{tpex_date_roc[3:]}"
            if twse_date and twse_date != tpex_date_ad:
                raise ValueError(f"TWSE 日期 ({twse_date}) 與 TPEX 日期 ({tpex_date_ad}) 不一致，資料尚未同步完成")

        for item in r_tpex:
            code = item.get("SecuritiesCompanyCode", "").strip()
            name = item.get("CompanyName", "").strip()
            try:
                trust = int(item.get("SecuritiesInvestmentTrustCompanies-Difference", "0").replace(",", "")) // 1000
                if trust > 0:
                    all_stocks.append({"code": code, "name": name, "close": "", "trust": trust})
            except Exception:
                continue

    # 計算當日買賣超佔發行張數 (%)
    for s in all_stocks:
        issued = shares_map.get(s["code"], 0)
        s["pct"] = round((s["trust"] / issued * 100), 2) if issued > 0 else 0.0

    # 排序取前 300 名
    ranked = sorted(all_stocks, key=lambda x: (x["pct"], x["trust"]), reverse=True)[:300]

    csv_headers = [
        "排名", "代號", "名稱", "成交", "漲跌價", "漲跌幅", "法人買賣日期",
        "當日買賣超佔發行張數", "2日買賣超佔發行張數", "3日買賣超佔發行張數",
        "5日買賣超佔發行張數", "10日買賣超佔發行張數", "1個月買賣超佔發行張數",
        "3個月買賣超佔發行張數", "半年買賣超佔發行張數", "1年買賣超佔發行張數",
        "3年買賣超佔發行張數", "10年買賣超佔發行張數", "今年買賣超佔發行張數"
    ]

    csv_data = []
    for rank, s in enumerate(ranked, 1):
        pct_str = f"+{s['pct']}" if s['pct'] > 0 else str(s['pct'])
        # 缺值顯式填入空字串 "" (Representing null), 絕不填 "0"
        row = [
            str(rank), s["code"], s["name"], s["close"], "", "", mm_dd,
            pct_str, "", "", "", "", "", "", "", "", "", "", ""
        ]
        csv_data.append(row)

    return csv_headers, csv_data

def fetch():
    session = requests.Session()
    # 跳過 index.asp（redirect 鏈不穩定），直接帶 cookie 打 API
    try:
        session.get("https://goodinfo.tw/tw/index.asp", headers=HEADERS, timeout=10,
                    allow_redirects=False)
    except Exception:
        pass  # 取不到也沒關係，直接用固定 cookie
    session.cookies.set("CLIENT_KEY", "2.5|41094.0082828283|46649.5638383838|8|46144.5|46144.5|",
                        domain="goodinfo.tw", path="/")
    time.sleep(1)
    r = session.get(API, headers=HEADERS, timeout=60)
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
    os.makedirs(os.path.join(REPO_DIR, folder), exist_ok=True)
    trade_date = data[0][6] if data else str(date.today())
    year = date.today().year
    if "/" in trade_date:
        month, day = trade_date.split("/")
        filename = f"{folder}/{year}-{month}-{day}.csv"
    else:
        filename = f"{folder}/{trade_date}.csv"
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
    run(["git", "commit", "-m", f"data: {os.path.basename(filename)}"])
    run(["git", "pull", "--rebase", "origin", "main"])
    run(["git", "push", "origin", "main"])
    print(f"已 push 到 GitHub：{filename}")

if __name__ == "__main__":
    print("抓取中...")
    try:
        html = fetch()
        headers, data = parse(html)
    except Exception as e:
        print(f"Goodinfo 抓取失敗 ({e})，自動切換至 TWSE/TPEX 官方 API")
        headers, data = fetch_twse_tpex()

    filename = save(headers, data)
    if filename:
        git_push(filename)

