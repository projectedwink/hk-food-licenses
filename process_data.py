import requests
import json
import os
import io
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

# 三個 CSDI 數據源
URLS = {
    "food_premise": "https://static.csdi.gov.hk/csdi-webpage/download/e6240fd3ee2c5292b1132d9e76013e34/kml",
    "restricted_food": "https://static.csdi.gov.hk/csdi-webpage/download/fa294e5facf2568c988c4180c9f4341a/kml",
    "restaurant": "https://static.csdi.gov.hk/csdi-webpage/download/6c96cc7a6e225dfd822a3c2cdefc3d2a/kml"
}

def parse_kml_bytes(content_bytes, category):
    features = []
    
    # 檢查是否為 KMZ (Zip 壓縮格式)
    if content_bytes.startswith(b'PK'):
        try:
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
                for filename in z.namelist():
                    if filename.endswith('.kml'):
                        content_bytes = z.read(filename)
                        break
        except Exception as e:
            print(f"Zip extraction error: {e}")

    try:
        root = ET.fromstring(content_bytes)
        
        # 移除 XML Namespace 前綴以方便查詢
        for elem in root.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]
        
        # 搜尋所有 Placemark 節點
        for pm in root.findall('.//Placemark'):
            name_elem = pm.find('name')
            name = name_elem.text.strip() if name_elem is not None and name_elem.text else "未知處所"
            
            coord_elem = pm.find('.//coordinates')
            if coord_elem is not None and coord_elem.text:
                coords = coord_elem.text.strip().split(',')
                if len(coords) >= 2:
                    try:
                        lng = float(coords[0])
                        lat = float(coords[1])
                        features.append({
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [lng, lat]
                            },
                            "properties": {
                                "Name": name,
                                "category": category
                            }
                        })
                    except ValueError:
                        continue
    except Exception as e:
        print(f"Error parsing KML XML for {category}: {e}")
        
    return features

def fetch_all_data():
    all_features = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for cat, url in URLS.items():
        print(f"Downloading {cat}...")
        try:
            res = requests.get(url, headers=headers, timeout=60)
            if res.status_code == 200:
                feats = parse_kml_bytes(res.content, cat)
                print(f"-> Successfully extracted {len(feats)} locations from {cat}")
                all_features.extend(feats)
            else:
                print(f"Failed to fetch {cat}, status: {res.status_code}")
        except Exception as e:
            print(f"Request error for {cat}: {e}")
            
    return all_features

print("Processing daily data...")
today_features = fetch_all_data()

# 增量比對 (Diff Engine)
yesterday_names = set()
yesterday_file = "previous_data.geojson"
if os.path.exists(yesterday_file):
    try:
        with open(yesterday_file, "r", encoding="utf-8") as f:
            prev_data = json.load(f)
            for feat in prev_data.get("features", []):
                name = feat.get("properties", {}).get("Name")
                if name:
                    yesterday_names.add(name)
    except Exception as e:
        print(f"Error loading previous data: {e}")

today_names = set(f["properties"]["Name"] for f in today_features)
new_items = today_names - yesterday_names if yesterday_names else set()
deleted_items = yesterday_names - today_names if yesterday_names else set()

for feat in today_features:
    name = feat["properties"]["Name"]
    feat["properties"]["status"] = "NEW" if name in new_items else "EXISTING"

today_geojson = {
    "type": "FeatureCollection",
    "features": today_features
}

# 輸出 GeoJSON 與報告
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(today_geojson, f, ensure_ascii=False)

with open("previous_data.geojson", "w", encoding="utf-8") as f:
    json.dump(today_geojson, f, ensure_ascii=False)

report = f"## 每日牌照更新報告 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
if yesterday_names:
    report += f"- 🟢 **今日新增處所**: {len(new_items)} 間\n"
    report += f"- 🔴 **今日註銷/移除處所**: {len(deleted_items)} 間\n"
    report += f"- 🔵 **總處所數量**: {len(today_features)} 間\n"
else:
    report += f"系統初始化完成，已載入 {len(today_features)} 筆歷史數據。"

with open("report.md", "w", encoding="utf-8") as f:
    f.write(report)

print(f"Done! Saved {len(today_features)} total features to data.json.")
