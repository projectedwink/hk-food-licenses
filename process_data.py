import requests
import geopandas as gpd
import pandas as pd
import json
import os
from datetime import datetime

# 政府 CSDI 三大 KML 數據源
URLS = {
    "food_premise": "https://static.csdi.gov.hk/csdi-webpage/download/e6240fd3ee2c5292b1132d9e76013e34/kml",
    "restricted_food": "https://static.csdi.gov.hk/csdi-webpage/download/fa294e5facf2568c988c4180c9f4341a/kml",
    "restaurant": "https://static.csdi.gov.hk/csdi-webpage/download/6c96cc7a6e225dfd822a3c2cdefc3d2a/kml"
}

gpd.io.file.fiona.drvsupport.supported_drivers['KML'] = 'rw'

def fetch_data():
    all_gdfs = []
    for cat, url in URLS.items():
        res = requests.get(url)
        temp_file = f"{cat}.kml"
        with open(temp_file, "wb") as f:
            f.write(res.content)
        try:
            gdf = gpd.read_file(temp_file, driver='KML')
            gdf['category'] = cat
            all_gdfs.append(gdf)
        except Exception as e:
            print(f"Error reading {cat}: {e}")
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    return pd.concat(all_gdfs, ignore_index=True) if all_gdfs else gpd.GeoDataFrame()

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
