import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import urllib.parse
from folium.plugins import LocateControl
import math

# 設定頁面資訊
st.set_page_config(page_title="日本找車位 (Python 版)", page_icon="🅿️", layout="centered")

# --- 數學公式：計算地球上兩點的直線距離 ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000 # 地球半徑 (公尺)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c # 回傳公尺

# 初始化 session state 變數
if "map_center" not in st.session_state:
    st.session_state.map_center = [34.6937, 135.5023] # 預設大阪
if "map_zoom" not in st.session_state:
    st.session_state.map_zoom = 15
if "parking_lots" not in st.session_state:
    st.session_state.parking_lots = []
if "status_text" not in st.session_state:
    st.session_state.status_text = "輸入地點並搜尋，即可尋找附近的停車場。"
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "selected_place" not in st.session_state:
    st.session_state.selected_place = None

# --- CSS 樣式設計 (Glassmorphism) ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
html, body, [class*="css"]  {
    font-family: 'Outfit', sans-serif;
}
.stApp {
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
    color: #f8fafc;
}
.stButton button {
    background: rgba(255, 255, 255, 0.1) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    color: white !important;
    border-radius: 12px !important;
    backdrop-filter: blur(10px) !important;
    font-weight: bold !important;
    transition: all 0.3s ease !important;
}
.stButton button:hover {
    background: #0984e3 !important;
    border: 1px solid #0984e3 !important;
    transform: translateY(-2px);
}
.search-container {
    background: rgba(255,255,255,0.05);
    padding: 15px;
    border-radius: 20px;
    border: 1px solid rgba(255,255,255,0.1);
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h2 style='text-align: center; color: white; margin-bottom: 20px;'>🗾 日本找車位</h2>", unsafe_allow_html=True)

# --- 搜尋邏輯 ---
def fetch_search_results(query):
    data = []
    error_msgs = []
    try:
        # 1. 嘗試使用 Nominatim API (加上完整的 Header 避免被阻擋，務必填寫看起來真實的 email)
        headers = {
            'User-Agent': 'JapanParkingFinderApp/1.1 (mark.parking.app@proton.me)',
            'Accept-Language': 'zh-TW,zh;q=0.9,ja;q=0.8'
        }
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(query)}"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # 檢查是否為 200 OK
        data = response.json()
    except Exception as e:
        error_msgs.append(f"Nominatim: {str(e)}")
        # 2. 如果 Nominatim 失敗 (例如雲端 IP 被封鎖)，自動切換到 Photon API 備用方案
        try:
            photon_url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(query)}&limit=10"
            p_res = requests.get(photon_url, timeout=10)
            p_res.raise_for_status()
            p_data = p_res.json()
            for f in p_data.get('features', []):
                coords = f['geometry']['coordinates']
                props = f['properties']
                name = props.get('name', '未知地點')
                state = props.get('state', '')
                city = props.get('city', '')
                district = props.get('district', '')
                display_name = f"{name} ({state} {city} {district})".strip()
                data.append({
                    'lat': str(coords[1]),
                    'lon': str(coords[0]),
                    'display_name': display_name,
                    'name': name
                })
        except Exception as e2:
            error_msgs.append(f"Photon: {str(e2)}")
            st.session_state.search_results = []
            st.session_state.status_text = f"伺服器忙碌中，請稍後再試。錯誤代碼: {' | '.join(error_msgs)}"
            return

    if data:
        # 過濾掉同名的選項，避免 Streamlit 下拉選單因為重複選項而報錯
        unique_data = []
        seen_names = set()
        for item in data:
            d_name = item.get('display_name', '')
            if d_name not in seen_names:
                seen_names.add(d_name)
                unique_data.append(item)

        st.session_state.search_results = unique_data
        st.session_state.status_text = f"找到 {len(unique_data)} 個相符的地點，請在下方清單選擇正確的目的地。"
    else:
        st.session_state.search_results = []
        st.session_state.status_text = "找不到這個地點，請試試看其他關鍵字。"

def fetch_parking_around(lat, lon):
    # 呼叫 Overpass API 尋找方圓 1 公里的停車場
    query = f"""
        [out:json];
        (
          node["amenity"="parking"](around:1000,{lat},{lon});
          way["amenity"="parking"](around:1000,{lat},{lon});
        );
        out center;
    """
    url = f"https://overpass.kumi.systems/api/interpreter?data={urllib.parse.quote(query)}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        lots = []
        for el in data.get('elements', []):
            plat = el.get('lat') or el.get('center', {}).get('lat')
            plon = el.get('lon') or el.get('center', {}).get('lon')
            
            if not plat or not plon: continue
            
            name = "停車場"
            if 'tags' in el:
                name = el['tags'].get('name', name)
                if name == "停車場" and el['tags'].get('fee') == 'yes':
                    name = "收費停車場"
                    
            # 計算距離與時間
            dist_m = haversine(lat, lon, plat, plon)
            walk_time = math.ceil(dist_m / 80) # 步速 80公尺/分鐘
            
            lots.append({
                'lat': plat, 'lon': plon, 
                'name': name, 
                'dist': round(dist_m),
                'walk_time': walk_time
            })
        
        st.session_state.parking_lots = lots
        st.session_state.status_text = f"目的地周圍 1 公里內找到了 {len(lots)} 個停車場！"
    except Exception as e:
        st.session_state.status_text = "網路異常，抓取停車場失敗。"

# 搜尋列區塊
st.markdown("<div class='search-container'>", unsafe_allow_html=True)
col1, col2 = st.columns([4, 1], gap="small")
with col1:
    search_query = st.text_input("搜尋", placeholder="輸入想去的地點，例如：美山", label_visibility="collapsed")
with col2:
    if st.button("🔍 搜尋", use_container_width=True):
        if search_query:
            st.session_state.selected_place = None
            st.session_state.parking_lots = []
            fetch_search_results(search_query)

# 如果有搜尋結果，顯示類似 Google Maps 的下拉選單
if st.session_state.search_results:
    options = {item['display_name']: item for item in st.session_state.search_results}
    selected_name = st.selectbox("👉 請選擇正確的地點：", list(options.keys()))
    
    if st.button("📍 確認前往此地並尋找車位", use_container_width=True):
        place = options[selected_name]
        lat, lon = float(place['lat']), float(place['lon'])
        
        st.session_state.selected_place = {
            'lat': lat, 
            'lon': lon, 
            'name': place.get('name', '目的地')
        }
        st.session_state.map_center = [lat, lon]
        st.session_state.map_zoom = 16
        
        fetch_parking_around(lat, lon)
        # 清空搜尋結果以收合選單
        st.session_state.search_results = []
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# 狀態顯示文字
st.markdown(f"<div style='text-align: center; color: #94a3b8; font-size: 14px; margin-bottom: 10px;'>{st.session_state.status_text}</div>", unsafe_allow_html=True)

# 建立 Folium 地圖物件
m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)
LocateControl().add_to(m) # 加入 GPS 定位按鈕

# 如果有設定目的地，畫上紅色的目的地標記
if st.session_state.selected_place:
    slat = st.session_state.selected_place['lat']
    slon = st.session_state.selected_place['lon']
    sname = st.session_state.selected_place['name']
    folium.Marker(
        [slat, slon],
        tooltip=f"📍 目的地：{sname}",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

# 將周圍的停車場畫上藍色的 P
for lot in st.session_state.parking_lots:
    lat = lot['lat']
    lon = lot['lon']
    name = lot['name']
    dist = lot['dist']
    walk_time = lot['walk_time']
    
    # Google Maps 導航與搜尋連結
    nav_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
    search_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(name)}+{lat},{lon}"
    
    popup_html = f"""
    <div style="text-align:center; min-width:180px; font-family:sans-serif;">
        <h4 style="margin-bottom:5px; color:#2f3542; font-size:16px;">{name}</h4>
        <div style="margin-bottom:12px; color:#576574; font-size:13px;">
            <div>📏 距離目的地：<b>{dist} 公尺</b></div>
            <div>🚶‍♂️ 走路約：<b>{walk_time} 分鐘</b></div>
        </div>
        <a href="{nav_url}" target="_blank" style="display:block; margin-bottom:6px; padding:8px; background:#0984e3; color:white; text-decoration:none; border-radius:6px; font-weight:bold; font-size:14px;">🗺️ 開始導航</a>
        <a href="{search_url}" target="_blank" style="display:block; padding:8px; background:#f1f2f6; color:#2f3542; text-decoration:none; border-radius:6px; font-weight:bold; border:1px solid #dfe4ea; font-size:14px;">📸 查看照片/收費</a>
    </div>
    """
    
    # 自訂藍色 P 圖示
    icon_html = '<div style="background:#0984e3; color:white; width:24px; height:24px; border-radius:50%; display:flex; justify-content:center; align-items:center; font-weight:bold; border:2px solid white; box-shadow:0 2px 5px rgba(0,0,0,0.3); font-size: 14px;">P</div>'
    icon = folium.DivIcon(html=icon_html, class_name="custom-icon")
    
    folium.Marker(
        [lat, lon],
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=name,
        icon=icon
    ).add_to(m)

# 渲染地圖 (取消了 returned_objects 避免不必要的重整)
st_folium(m, width="100%", height=450)
