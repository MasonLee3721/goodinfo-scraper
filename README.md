# goodinfo-scraper

爬取 [Goodinfo 台灣股市資訊網](https://goodinfo.tw) 投信買超佔發行張數排行。

## 功能

- 爬取投信買超佔發行張數當日排行（前 300 名）
- 欄位：排名、代號、名稱、成交、漲跌價、漲跌幅、法人買賣日期、買賣超佔發行張數

## 環境需求

- Python 3.8+
- [uv](https://github.com/astral-sh/uv)（推薦）或 pip

## 安裝與執行

### 用 uv（推薦）

```bash
uv run --with requests --with beautifulsoup4 --with lxml python3 scrape_goodinfo.py
```

### 用 pip

```bash
pip install -r requirements.txt
python3 scrape_goodinfo.py
```

## 輸出範例

```
抓取中...
共 300 筆

排名 | 代號 | 名稱 | 成交 | 漲跌價 | 漲跌幅 | 法人買賣日期 | 當日買賣超佔發行張數
--------------------------------------------------------------------------------
1 | 6706 | 惠特 | 151.5 | +4.5 | +3.06 | 04/30 | +2.01
2 | 6147 | 頎邦 | 163 | +5 | +3.16 | 04/30 | +1.03
...
```

## 注意事項

詳見 [NOTES.md](NOTES.md)

## 每日追蹤流程

### 步驟 1：每天跑一次爬蟲（存成 data/YYYY-MM-DD.csv）
```bash
uv run --with requests --with beautifulsoup4 --with lxml python3 scrape_goodinfo.py
```

### 步驟 2：分析連續買入的股票
```bash
# 看所有資料，至少連續 2 天
uv run --with pandas python3 analyze.py

# 只看最近 5 個交易日，至少連續 3 天
uv run --with pandas python3 analyze.py --days 5 --min-days 3
```

### 輸出說明
- **出現天數**：這支股票在排行榜出現幾天
- **最新買超幅度**：最新一天的買超佔發行張數 %
- **平均買超幅度**：這段期間的平均值
- **趨勢**：📈 增加 / 📉 減少 / ➡️ 持平（與前一天比較）
