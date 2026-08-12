import requests
import json
import os
import io
import zipfile
import re
import xml.etree.ElementTree as ET
from datetime import datetime

URLS = {
    "food_premise": "https://static.csdi.gov.hk/csdi-webpage/download/e6240fd3ee2c5292b1132d9e76013e34/kml",
    "restricted_food": "https://static.csdi.gov.hk/csdi-webpage/download/fa294e5facf2568c988c4180c9f4341a/kml",
    "restaurant": "https://static.csdi.gov.hk/csdi-webpage/download/6c96cc7a6e225dfd822a3c2cdefc3d2a/kml"
}

def parse_kml_text(xml_text, category):
    features = []
    try:
        # 清除所有 XML Namespace (修復 findall 找不到 Placemark 的問題)
        clean_xml = re.sub(r'\sxmlns="[^"]+"', '', xml_text)
        clean_xml = re.sub(r'\sxmlns:[a-z]+="[^"]+"', '', clean_xml)
        
        root = ET.fromstring(clean_xml)
        
        placemarks = root.findall('.//Placemark')
        print(f"[{category}] Found {len(placemarks)} <Placemark> elements.")
        
        for pm in placemarks:
            name_elem = pm.find('name')
            name = name_elem.text.strip() if name_elem is not None and name_elem.text else "未知處所"
            
            coord_elem = pm.find('.//coordinates')
            if coord_elem is not None and coord_elem.text:
                raw_coords = coord_elem.text.strip().split()
                if raw_coords:
                    coords = raw_coords[0].split(',')
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
        print(f"[{category}] XML Parsing Exception: {e}")
        
    return features

def fetch_all_data():
    all_features = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for cat, url in URLS.items():
        print(f"\n--- Fetching {cat} ---")
        try:
            res = requests.get(url, headers=headers, timeout=60)
            print(f"[{cat}] HTTP Status: {res.status_code}, Length: {len(res.content)} bytes")
            
            content_bytes = res.content
            
            # 檢查是否為 KMZ / ZIP
            if content_bytes.startswith(b'PK'):
                print(f"[{cat}] KMZ Zip format detected. Extracting...")
                with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
                    for filename in z.namelist():
                        if filename.endswith('.kml'):
                            content_bytes = z.read(filename)
                            break
            
            xml_text = content_bytes.decode('utf-8', errors='ignore')
            feats = parse_kml_text(xml_text, cat)
            print(f"[{cat}] Successfully parsed {len(feats)} locations.")
            all_features.extend(feats)
            
        except Exception as e:
            print(f"[{cat}] Fetch error: {e}")
            
    return all_features

print("Processing daily data...")
today_features = fetch_all_data()
print(f"\nTOTAL FEATURES EXTRACTED: {len(today_features)}")

# 比對與輸出邏輯
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
        print(f"Error reading previous_data: {e}")

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

print("Processing finished successfully!")
