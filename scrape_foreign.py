"""
爬取 Goodinfo 外資、投信同步買超當日排行，存成每日 CSV 並 push 到 GitHub
執行：uv run --with requests --with beautifulsoup4 --with lxml python3 scrape_foreign.py
"""
import requests, time, csv, os, subprocess, json
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

def parse_int(val):
    """將字串解析為整數。若為空值、None、-- 或非數字，明確回傳 None（表示 missing null），絕不回傳 0"""
    if val is None:
        return None
    val_str = str(val).replace(",", "").strip()
    if not val_str or val_str in ("--", "null", "None"):
        return None
    try:
        return int(val_str)
    except ValueError:
        return None

def fetch_twse_tpex():
    """當 Goodinfo 被 Cloudflare 防火牆擋住時，自動改用證交所 (TWSE) 與櫃買中心 (TPEX) 官方 Open API 抓取外資投信同買"""
    print("Goodinfo 被擋，改用 TWSE/TPEX 官方 API 抓取外資投信同買資料...")

    # 1. 抓取 TWSE 三大法人買賣超 (上市)
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
            # 保留精確買賣超股數 (shares)
            foreign_shares = parse_int(row[4])
            trust_shares = parse_int(row[10])
            dealer_shares = parse_int(row[11])
            total_shares = parse_int(row[18])
            if foreign_shares is not None and foreign_shares > 0 and trust_shares is not None and trust_shares > 0:
                all_stocks.append({
                    "code": code, "name": name, "close": close,
                    "foreign_shares": foreign_shares,
                    "trust_shares": trust_shares,
                    "dealer_shares": dealer_shares or 0,
                    "total_shares": total_shares or 0
                })
        except Exception:
            continue

    # 2. 抓取 TPEX 三大法人買賣超 (上櫃)
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
                foreign_shares = parse_int(item.get("ForeignInvestorsIncludeMainlandAreaInvestors-Difference"))
                trust_shares = parse_int(item.get("SecuritiesInvestmentTrustCompanies-Difference"))
                dealer_shares = parse_int(item.get("Dealers-Difference"))
                total_shares = parse_int(item.get("TotalDifference"))
                if foreign_shares is not None and foreign_shares > 0 and trust_shares is not None and trust_shares > 0:
                    all_stocks.append({
                        "code": code, "name": name, "close": "",
                        "foreign_shares": foreign_shares,
                        "trust_shares": trust_shares,
                        "dealer_shares": dealer_shares or 0,
                        "total_shares": total_shares or 0
                    })
            except Exception:
                continue

    # 按精確投信買超股數 (shares) 降序排序取前 300 名
    ranked = sorted(all_stocks, key=lambda x: (x["trust_shares"], x["foreign_shares"]), reverse=True)[:300]

    csv_headers = [
        "代號", "名稱", "成交", "漲跌價", "漲跌幅", "成交張數", "法人買賣日期",
        "外資買進張數", "外資賣出張數", "外資買賣超張數",
        "投信買進張數", "投信賣出張數", "投信買賣超張數",
        "自營買進張數", "自營賣出張數", "自營買賣超張數",
        "合計買進張數", "合計賣出張數", "合計買賣超張數", "法人買賣超註記"
    ]

    csv_data = []
    for s in ranked:
        foreign_lots = s["foreign_shares"] // 1000
        trust_lots = s["trust_shares"] // 1000
        dealer_lots = s["dealer_shares"] // 1000
        total_lots = s["total_shares"] // 1000
        # 缺值顯式填入空字串 "" (Representing null), 絕不填 "0"
        row = [
            s["code"], s["name"], s["close"], "", "", "", mm_dd,
            "", "", f"+{foreign_lots}" if foreign_lots > 0 else str(foreign_lots),
            "", "", f"+{trust_lots}" if trust_lots > 0 else str(trust_lots),
            "", "", f"+{dealer_lots}" if dealer_lots > 0 else str(dealer_lots),
            "", "", f"+{total_lots}" if total_lots > 0 else str(total_lots),
            "＋＋＋"
        ]
        csv_data.append(row)

    return csv_headers, csv_data

def fetch():
    session = requests.Session()
    try:
        session.get("https://goodinfo.tw/tw/index.asp", headers=HEADERS, timeout=10,
                    allow_redirects=False)
    except Exception:
        pass
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

def save(headers, data, folder="data_foreign"):
    os.makedirs(os.path.join(REPO_DIR, folder), exist_ok=True)
    trade_date = data[0][6] if len(data[0]) > 6 else str(date.today())
    # 有些欄位排列不同，嘗試從第一筆找日期格式 MM/DD
    for cell in data[0]:
        if "/" in cell and len(cell) == 5:
            trade_date = cell
            break
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
    run(["git", "commit", "-m", f"data(foreign): {os.path.basename(filename)}"])
    run(["git", "pull", "--rebase", "origin", "main"])
    run(["git", "push", "origin", "main"])
    print(f"已 push 到 GitHub：{filename}")

if __name__ == "__main__":
    print("抓取外資投信同買...")
    try:
        html = fetch()
        headers, data = parse(html)
    except Exception as e:
        print(f"Goodinfo 抓取失敗 ({e})，自動切換至 TWSE/TPEX 官方 API")
        headers, data = fetch_twse_tpex()

    print(f"共 {len(data)} 筆，欄位：{headers[:6]}")
    filename = save(headers, data)
    if filename:
        git_push(filename)

