import requests
import geopandas as gpd
import pandas as pd
import json
import os
import fiona
from datetime import datetime

# 直接啟用 fiona 的 KML 驅動支援 (修復 AttributeError)
fiona.drvsupport.supported_drivers['KML'] = 'rw'

# 三個 CSDI 數據源
URLS = {
    "food_premise": "https://static.csdi.gov.hk/csdi-webpage/download/e6240fd3ee2c5292b1132d9e76013e34/kml",
    "restricted_food": "https://static.csdi.gov.hk/csdi-webpage/download/fa294e5facf2568c988c4180c9f4341a/kml",
    "restaurant": "https://static.csdi.gov.hk/csdi-webpage/download/6c96cc7a6e225dfd822a3c2cdefc3d2a/kml"
}

def fetch_data():
    all_gdfs = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for cat, url in URLS.items():
        try:
            res = requests.get(url, headers=headers, timeout=30)
            temp_file = f"{cat}.kml"
            with open(temp_file, "wb") as f:
                f.write(res.content)
            
            # 使用 fiona 作為引擎讀取 KML
            gdf = gpd.read_file(temp_file, driver='KML', engine='fiona')
            gdf['category'] = cat
            all_gdfs.append(gdf)
        except Exception as e:
            print(f"Error reading {cat}: {e}")
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
    if all_gdfs:
        return pd.concat(all_gdfs, ignore_index=True)
    return gpd.GeoDataFrame()

print("Processing daily data...")
gdf_today = fetch_data()

# 增量比對 (Diff Engine)
yesterday_file = "previous_data.geojson"
if os.path.exists(yesterday_file):
    gdf_yesterday = gpd.read_file(yesterday_file)
    today_names = set(gdf_today['Name'])
    yesterday_names = set(gdf_yesterday['Name'])
    
    new_items = today_names - yesterday_names
    deleted_items = yesterday_names - today_names
    
    gdf_today['status'] = gdf_today['Name'].apply(lambda x: 'NEW' if x in new_items else 'EXISTING')
    
    report = f"## 每日牌照更新報告 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
    report += f"- 🟢 **今日新增處所**: {len(new_items)} 間\n"
    report += f"- 🔴 **今日註銷/移除處所**: {len(deleted_items)} 間\n"
    report += f"- 🔵 **總處所數量**: {len(gdf_today)} 間\n"
else:
    gdf_today['status'] = 'EXISTING'
    report = f"## 每日牌照更新報告 ({datetime.now().strftime('%Y-%m-%d')})\n\n系統初始化完成，已載入 {len(gdf_today)} 筆歷史數據。"

# 匯出資料
gdf_today.to_file("data.json", driver="GeoJSON")
gdf_today.to_file("previous_data.geojson", driver="GeoJSON")

with open("report.md", "w", encoding="utf-8") as f:
    f.write(report)

print("Data processing complete.")
