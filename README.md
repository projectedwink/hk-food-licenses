# hk-food-licenses
構建一套自動化數據處理流水線（ETL Automation Pipeline）。
利用 Python Script + GitHub Actions 每日自動下載並解析 KML、進行空間關聯（Spatial Join，將座標歸類至 18 區）與增量比對（Diff Engine）
最後生成互動式地圖（Web Map）及每日變更報告（Email / Webhook 報表)
