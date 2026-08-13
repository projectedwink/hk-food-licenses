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

def parse_kml_text(xml_text, category_key):
    features = []
    try:
        clean_xml = re.sub(r'\sxmlns="[^"]+"', '', xml_text)
        clean_xml = re.sub(r'\sxmlns:[a-z]+="[^"]+"', '', clean_xml)
        
        root = ET.fromstring(clean_xml)
        placemarks = root.findall('.//Placemark')
        
        for pm in placemarks:
            simple_data = {}
            for sd in pm.findall('.//SimpleData'):
                key = sd.get('name')
                if key:
                    simple_data[key] = sd.text.strip() if sd.text else ""

            shop_name = simple_data.get("NSEARCH03_TC", "")      # 店名/商號
            license_type = simple_data.get("NAME_TC", "")         # 牌照種類
            dataset_name = simple_data.get("DATASET_TC", "")     # 數據集名稱
            address = simple_data.get("ADDRESS_TC", "")           # 地址
            district = simple_data.get("SEARCH01_TC", "未知地區") # 地區
            license_no = simple_data.get("SEARCH02_TC", "")      # 牌照號碼 (唯一鍵)
            expiry_date = simple_data.get("NSEARCH04_TC", "")    # 到期日
            last_update = simple_data.get("LASTUPDATE", "")       # 更新日

            display_name = shop_name if shop_name else license_type
            if not display_name:
                name_elem = pm.find('name')
                display_name = name_elem.text.strip() if name_elem is not None and name_elem.text else "無名處所"

            uid = license_no if license_no else f"{display_name}_{address}"
            final_license_type = license_type if license_type else dataset_name

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
                                    "uid": uid,
                                    "Name": display_name,
                                    "shop_name": shop_name,
                                    "license_type": final_license_type,
                                    "license_no": license_no,
                                    "address": address,
                                    "district": district,
                                    "expiry_date": expiry_date,
                                    "last_update": last_update
                                }
                            })
                        except ValueError:
                            continue
    except Exception as e:
        print(f"[{category_key}] XML Parsing Exception: {e}")
        
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

# 讀取昨日歷史數據 (用於比對刪除項)
yesterday_map = {}
yesterday_file = "previous_data.geojson"
has_valid_uid_history = False

if os.path.exists(yesterday_file):
    try:
        with open(yesterday_file, "r", encoding="utf-8") as f:
            prev_data = json.load(f)
            for feat in prev_data.get("features", []):
                uid = feat.get("properties", {}).get("uid")
                if uid:
                    yesterday_map[uid] = feat
                    has_valid_uid_history = True
    except Exception as e:
        print(f"Error reading previous_data: {e}")

yesterday_uids = set(yesterday_map.keys())
today_uids = set(f["properties"]["uid"] for f in today_features)

if has_valid_uid_history:
    new_uids = today_uids - yesterday_uids
    deleted_uids = yesterday_uids - today_uids
else:
    new_uids = set()
    deleted_uids = set()

# 組合最終輸出列表
final_export_features = []

# 1. 處理今日存在處所 (NEW / EXISTING)
for feat in today_features:
    uid = feat["properties"]["uid"]
    feat["properties"]["status"] = "NEW" if (has_valid_uid_history and uid in new_uids) else "EXISTING"
    final_export_features.append(feat)

# 2. 【核心修復】將註銷/移除的處所從昨日資料抓回，並標記為 REMOVED 寫入 data.json
for uid in deleted_uids:
    deleted_feat = yesterday_map[uid]
    deleted_feat["properties"]["status"] = "REMOVED"
    final_export_features.append(deleted_feat)

# 輸出給地圖前端使用 (包含今日 + 今日註銷)
today_geojson = {
    "type": "FeatureCollection",
    "features": final_export_features
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(today_geojson, f, ensure_ascii=False)

# 保存基準檔 (僅保存今天依然有效的處所，供明天比對使用)
existing_geojson = {
    "type": "FeatureCollection",
    "features": today_features
}

with open("previous_data.geojson", "w", encoding="utf-8") as f:
    json.dump(existing_geojson, f, ensure_ascii=False)

# 生成報告
report = f"## 每日牌照更新報告 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
if has_valid_uid_history:
    report += f"- 🟢 **今日新增處所**: {len(new_uids)} 間\n"
    report += f"- 🔴 **今日註銷/移除處所**: {len(deleted_uids)} 間\n"
    report += f"- 🔵 **總處所數量**: {len(today_features)} 間\n"
else:
    report += f"系統已自動重設數據基準標籤，成功載入 {len(today_features)} 筆記錄。"

with open("report.md", "w", encoding="utf-8") as f:
    f.write(report)

print("Done successfully!")
