# hk-food-licenses

# 香港食物業處所每日地圖 (HK Food License Daily Map)
## 開發紀錄與技術架構文件 (Technical Documentation)

---

## 📋 1. 項目概述 (Project Overview)

* **項目名稱**：香港食物業處所每日地圖 (HK Food License Daily Map)
* **核心目的**：自動化抓取香港政府空間數據共享平台（CSDI）的食物業牌照數據，每日進行比對（Diffing），實時標示**新增**及**註銷**處所，並以互動式地圖呈現與發送 Telegram 推播通知。
* **部署平台**：GitHub Pages + GitHub Actions (完全零成本、免伺服器架構)

---

## 🛠️ 2. 技術棧與選型 (Tech Stack)

| 模組 | 採用技術 | 選擇原因 / 優勢 |
| :--- | :--- | :--- |
| **數據處理 (Engine)** | Python 3, `requests`, `zipfile`, `xml.etree` | 輕量且能高效解析大體積 KML/KMZ 壓縮檔 |
| **地圖渲染 (Frontend)** | Leaflet.js + OpenStreetMap | **100% 免費開源**、免 API Key、免綁信用卡，避免帳號風控風險 |
| **排程自動化 (CI/CD)** | GitHub Actions | 每日定時自動執行，實現零人工干預 |
| **即時通知 (Notification)** | Telegram Bot API | 免費、設定簡單，手機端可秒級接收最新更新報告 |

---

## ⚙️ 3. 核心模組與技術細節

### 模組 A：數據抓取與比對引擎 (`process_data.py`)

1. **數據源擷取 (Data Fetching)**：
   * 透過官方靜態 URL 實時下載三大類別數據（食物業處所 `food_premise`、受限制食物 `restricted_food`、食肆 `restaurant`）。
   * 自動判斷並解壓縮 ZIP/KMZ 檔案，轉換為 UTF-8 格式之 KML XML 文本。

2. **精準欄位抽取 (XML Parsing)**：
   * 清除 XML Namespace 障礙後，動態提取 `<SimpleData>` 標籤中的核心資訊：
     * **`SEARCH02_TC`**：牌照號碼（作為唯一主鍵 **UID**）
     * **`NSEARCH03_TC`**：商號 / 店名
     * **`NAME_TC` / `DATASET_TC`**：牌照種類（例如：普通食肆、工廠食堂、食物製造廠等）
     * **`SEARCH01_TC`**：18區地區名稱（例如：屯門區、中西區）
     * **`ADDRESS_TC`**：中文詳細地址
     * **`NSEARCH04_TC`**：牌照到期日
     * **`LASTUPDATE`**：政府數據更新日期

3. **增量比對引擎 (Diff Engine)**：
   * **修復連鎖店重複問題**：棄用店名 (`Name`) 作為比對標籤，改用**「牌照號碼 (`license_no`)」**作為獨一無二的 `uid`。
   * **比對邏輯**：
     * 今日 `UID` - 昨日 `UID` = 🟢 **今日新增處所 (`NEW`)**
     * 昨日 `UID` - 今日 `UID` = 🔴 **今日註銷/移除處所 (`DELETED`)**
   * 生成 `data.json`（地圖用 GeoJSON）、`previous_data.geojson`（歷史備份）及 `report.md`（日誌報告）。

---

### 模組 B：響應式前端互動地圖 (`index.html`)

1. **雙重選單聯動篩選 (Dual-Filter Logic)**：
   * 支持**「地區 (`SEARCH01_TC`)」**與**「牌照類別 (`NAME_TC`)」**雙重選單。
   * 採交集邏輯 (AND Condition) 篩選標籤，例如：可精確篩選出「屯門區」內所有的「食物製造廠」。

2. **流動端優化 (Mobile-Responsive Design)**：
   * 利用 `@media (max-width: 768px)` 實現電腦與手機版自動適應：
     * **電腦端 (Desktop)**：經典左側控制欄 (360px 寬度)。
     * **手機端 (Mobile)**：轉換為**底部抽屜式面板**（最多佔用 40% 螢幕高度），上方 60% 保持清晰可見的地圖視野，且放大縮小按鈕自動遷移至右上方。

3. **自訂視覺化標籤 (Custom Markers & Popups)**：
   * **🟢 綠色標籤**：今日新增處所 (`NEW`)。
   * **🔵 藍色標籤**：既有處所 (`EXISTING`)。
   * **點擊彈窗 (Popup)**：直觀呈現店名、牌照號碼、類別、地區、詳細地址及**紅色粗體牌照到期日**。

---

### 模組 C：自動化 CI/CD 與 Telegram 通知 (`daily.yml`)

1. **時區轉換與排程 (Cron Scheduling)**：
   * 設定 Cron 觸發時間為 `30 2 * * *` (UTC 02:30)，準確對應**香港時間每日 10:30 AM (HKT)**。

2. **安全資安控制 (Security & Secrets)**：
   * 使用 **GitHub Repository Secrets** 加密儲存 `TELEGRAM_TOKEN` 及 `TELEGRAM_TO`，確保代碼庫公開時不會外洩敏感的金鑰與權限。

3. **Telegram 即時推播**：
   * 先將 `report.md` 內容讀取並匯入 GitHub Actions 的環境變數 `$GITHUB_ENV`。
   * 調用 `appleboy/telegram-action` 插件發送 Markdown 格式訊息至 Telegram 手機端。

---

## 🚨 4. 技術避坑與關鍵問題修復紀錄 (Troubleshooting Log)

1. **Google Maps 帳號資安限制 / API Key 失敗**：
   * *問題*：新註冊 Google 帳號因 GCP 操作限制導致無法順利調用地圖 API。
   * *解決*：果斷切換至 **Leaflet.js + OpenStreetMap**，徹底擺脫對 GCP 服務與 API Key 的依賴。

2. **數據統計異常（新增/註銷數量暴增）**：
   * *問題*：以「店名」比對時，連鎖店（如麥當勞）或無名處所會被重複歸類，導致數據錯亂。
   * *解決*：改用政府給予的硬體唯一碼 **`SEARCH02_TC` (牌照號碼)** 作為 `uid`，徹底解決重複問題。

3. **Telegram 訊息自動跳轉至 `www.report.md` 網址**：
   * *問題*：`.md` 是摩爾多瓦的國家頂級網域，Telegram 將檔名錯判為超連結。
   * *解決*：在 GitHub Actions 中改以 `env.REPORT_TEXT` 讀取並替換報告內文，不再將檔名作為純文字傳送。
