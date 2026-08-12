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
        # 清除 XML Namespace 以便 ElementTree 解析
        clean_xml = re.sub(r'\sxmlns="[^"]+"', '', xml_text)
        clean_xml = re.sub(r'\sxmlns:[a-z]+="[^"]+"', '', clean_xml)
        
        root = ET.fromstring(clean_xml)
        placemarks = root.findall('.//Placemark')
        
        for pm in placemarks:
            # 解析 SimpleData 欄位
            simple_data = {}
            for sd in pm.findall('.//SimpleData'):
                key = sd.get('name')
                if key:
                    simple_data[key] = sd.text.strip() if sd.text else ""

            # 提取關鍵欄位
            shop_name = simple_data.get("NSEARCH03_TC", "")      # 商號/店名 (例如: Fusion)
            license_type = simple_data.get("NAME_TC", "")         # 牌照種類 (例如: 售賣冰凍甜點)
            dataset_name = simple_data.get("DATASET_TC", "")     # 數據集名稱
            address = simple_data.get("ADDRESS_TC", "")           # 中文地址
            district = simple_data.get("SEARCH01_TC", "未知地區") # 18區地區名稱 (例如: 中西區)
            expiry_date = simple_data.get("NSEARCH04_TC", "")    # 牌照到期日 (NSEARCH04_TC)
            last_update = simple_data.get("LASTUPDATE", "")       # 資料更新日期

            # 地圖主標題：優先使用店名，無店名則使用牌照種類
            display_name = shop_name if shop_name else license_type
            if not display_name:
                name_elem = pm.find('name')
                display_name = name_elem.text.strip() if name_elem is not None and name_elem.text else "無名處所"

            # 座標解析
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
                                    "Name": display_name,
                                    "shop_name": shop_name,
                                    "license_type": license_type,
                                    "dataset_name": dataset_name,
                                    "address": address,
                                    "district": district,             # 用於地區分類
                                    "expiry_date": expiry_date,       # 到期日
                                    "last_update": last_update,
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
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for cat, url in URLS.items():
        try:
            res = requests.get(url, headers=headers, timeout=60)
            content_bytes = res.content
            
            if content_bytes.startswith(b'PK'):
                with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
                    for filename in z.namelist():
                        if filename.endswith('.kml'):
                            content_bytes = z.read(filename)
                            break
            
            xml_text = content_bytes.decode('utf-8', errors='ignore')
            feats = parse_kml_text(xml_text, cat)
            all_features.extend(feats)
        except Exception as e:
            print(f"[{cat}] Fetch error: {e}")
            
    return all_features

print("Processing daily data...")
today_features = fetch_all_data()

# 比對邏輯 (Diff Engine)
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

# 寫入檔案
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(today_geojson, f, ensure_ascii=False)

with open("previous_data.geojson", "w", encoding="utf-8") as f:
    json.dump(today_geojson, f, ensure_ascii=False)

# 產生報告
report = f"## 每日牌照更新報告 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
if yesterday_names:
    report += f"- 🟢 **今日新增處所**: {len(new_items)} 間\n"
    report += f"- 🔴 **今日註銷/移除處所**: {len(deleted_items)} 間\n"
    report += f"- 🔵 **總處所數量**: {len(today_features)} 間\n"
else:
    report += f"系統初始化完成，已載入 {len(today_features)} 筆歷史數據。"

with open("report.md", "w", encoding="utf-8") as f:
    f.write(report)

print(f"Complete! Extracted {len(today_features)} records.")
