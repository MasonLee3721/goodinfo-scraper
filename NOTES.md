# 踩坑與注意事項

## 1. Goodinfo 的防爬機制

### 第一層：JS Cookie 驗證
網站首次載入時，會用 JavaScript 設定 `CLIENT_KEY` cookie，然後 redirect 到真正的頁面。
直接用 `requests` 打 URL 只會拿到空的 HTML（body 是空的）。

**解法：** 先訪問首頁讓 server 設定 `CLIENT_ID` cookie，再手動補上 `CLIENT_KEY`。

```python
session.get("https://goodinfo.tw/tw/index.asp", ...)  # 取得 CLIENT_ID
session.cookies.set("CLIENT_KEY", "2.5|...", domain="goodinfo.tw", path="/")
```

### 第二層：資料是 AJAX 動態載入
原始 HTML 裡沒有股票資料表，資料是頁面載入後才透過 AJAX 請求取得的。

**解法：** 直接打 AJAX endpoint，加上 `STEP=DATA` 參數，並改用 `tw2` 子域：

```
https://goodinfo.tw/tw2/StockList.asp?STEP=DATA&...
```

> 注意：打 `tw/StockList.asp?STEP=DATA` 會被 redirect 到 `tw2`，直接打 `tw2` 比較快。

---

## 2. Playwright / Selenium 在此環境無法使用

此 server 環境缺少 Chromium 所需的系統套件（`libglib-2.0.so.0` 等），且沒有 root 權限安裝。

```
chrome-headless-shell: error while loading shared libraries: libglib-2.0.so.0
```

**結論：** 用純 `requests` 即可，不需要瀏覽器。

---

## 3. 請求頻率

Goodinfo 對爬蟲有頻率限制，建議：
- 每次請求之間 `time.sleep(1)` 以上
- 不要短時間內大量請求，否則 IP 可能被暫時封鎖

---

## 4. 資料表 ID

資料表的 HTML id 是 `tblStockList`，用這個直接定位最穩：

```python
table = soup.find("table", id="tblStockList")
```

---

## 5. 編碼

回應需手動設定 `r.encoding = "utf-8"`，否則中文會亂碼。
