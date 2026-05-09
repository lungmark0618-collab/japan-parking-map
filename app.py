import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import urllib.parse
from folium.plugins import LocateControl

# 設定頁面資訊
st.set_page_config(page_title="日本找車位 (Python 版)", page_icon="🅿️", layout="centered")

# 初始化 session state 變數
if "map_center" not in st.session_state:
    st.session_state.map_center = [34.6937, 135.5023] # 預設大阪
if "map_zoom" not in st.session_state:
    st.session_state.map_zoom = 15
if "parking_lots" not in st.session_state:
    st.session_state.parking_lots = []
if "last_bounds" not in st.session_state:
    st.session_state.last_bounds = None
if "status_text" not in st.session_state:
    st.session_state.status_text = "移動地圖來搜尋這區的車位，或點擊下方快速跳轉。"

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

# --- 共用搜尋邏輯 ---
def perform_search(query):
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(query)}"
        response = requests.get(url, headers={'User-Agent': 'JapanParkingFinder/1.0'})
        data = response.json()
        if data:
            st.session_state.map_center = [float(data[0]['lat']), float(data[0]['lon'])]
            st.session_state.map_zoom = 16
            st.session_state.status_text = f"找到「{query}」！"
            st.session_state.last_bounds = None # 重設邊界強制重新抓取
            st.rerun()
        else:
            st.session_state.status_text = "找不到這個地點，請試試看其他關鍵字。"
    except Exception as e:
        st.session_state.status_text = "搜尋失敗，請確認網路連線。"

# 搜尋列區塊
st.markdown("<div class='search-container'>", unsafe_allow_html=True)
col1, col2 = st.columns([4, 1], gap="small")
with col1:
    search_query = st.text_input("搜尋", placeholder="輸入想去的地點，例如：清水寺", label_visibility="collapsed")
with col2:
    if st.button("🔍 搜尋", use_container_width=True):
        if search_query:
            perform_search(search_query)

# 熱門推薦搜尋標籤
st.markdown("<div style='font-size: 0.85rem; color: #94a3b8; margin-bottom: 8px;'>✨ 熱門推薦搜尋：</div>", unsafe_allow_html=True)
sc1, sc2, sc3, sc4 = st.columns(4)
hot_spots = ["清水寺", "心齋橋", "黑門市場", "環球影城"]
for col, spot in zip([sc1, sc2, sc3, sc4], hot_spots):
    with col:
        if st.button(spot, use_container_width=True, key=f"hot_{spot}"):
            perform_search(spot)
st.markdown("</div>", unsafe_allow_html=True)

# 建立 Folium 地圖物件
m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)
LocateControl().add_to(m) # 加入 GPS 定位按鈕

# 將 Session State 裡面的停車場資料畫到地圖上
for lot in st.session_state.parking_lots:
    lat = lot['lat']
    lon = lot['lon']
    name = lot.get('name', '停車場')
    
    # Google Maps 連結
    nav_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
    search_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(name)}+{lat},{lon}"
    
    popup_html = f"""
    <div style="text-align:center; min-width:180px; font-family:sans-serif;">
        <h4 style="margin-bottom:8px; color:#2f3542;">{name}</h4>
        <a href="{nav_url}" target="_blank" style="display:block; margin-bottom:5px; padding:6px; background:#0984e3; color:white; text-decoration:none; border-radius:4px; font-weight:bold;">🗺️ 開始導航</a>
        <a href="{search_url}" target="_blank" style="display:block; padding:6px; background:#f1f2f6; color:#2f3542; text-decoration:none; border-radius:4px; font-weight:bold; border:1px solid #dfe4ea;">📸 查詢照片/收費</a>
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
    ).addTo(m)

# 渲染地圖，並取得使用者操作後的狀態 (包含滑動後的邊界 bounds)
map_data = st_folium(m, width="100%", height=450, returned_objects=["bounds", "center", "zoom"])

# 狀態顯示文字
st.markdown(f"<div style='text-align: center; color: #94a3b8; font-size: 14px; margin-top: 10px; margin-bottom: 10px;'>{st.session_state.status_text}</div>", unsafe_allow_html=True)

# 快速跳轉按鈕
col_b1, col_b2, col_b3 = st.columns(3)
with col_b1:
    if st.button("📍 京都", use_container_width=True):
        st.session_state.map_center = [35.0116, 135.7681]
        st.session_state.map_zoom = 15
        st.session_state.last_bounds = None
        st.rerun()
with col_b2:
    if st.button("📍 大阪", use_container_width=True):
        st.session_state.map_center = [34.6937, 135.5023]
        st.session_state.map_zoom = 15
        st.session_state.last_bounds = None
        st.rerun()
with col_b3:
    if st.button("📍 奈良", use_container_width=True):
        st.session_state.map_center = [34.6851, 135.8048]
        st.session_state.map_zoom = 15
        st.session_state.last_bounds = None
        st.rerun()

# --- Overpass API 自動抓取邏輯 ---
# 只有當地圖有回傳資料，而且包含邊界時才觸發
if map_data and map_data.get("bounds"):
    current_bounds = map_data["bounds"]
    current_zoom = map_data.get("zoom", 15)
    
    # 儲存最新的中心點跟縮放，才不會在重新渲染時跳回原點
    if map_data.get("center"):
        st.session_state.map_center = [map_data["center"]["lat"], map_data["center"]["lng"]]
    if map_data.get("zoom"):
        st.session_state.map_zoom = map_data["zoom"]

    # 為了避免無限重新整理，我們計算邊界的近似值
    rounded_bounds = (
        round(current_bounds["_southWest"]["lat"], 4),
        round(current_bounds["_southWest"]["lng"], 4),
        round(current_bounds["_northEast"]["lat"], 4),
        round(current_bounds["_northEast"]["lng"], 4)
    )
    
    # 如果使用者真的移動了地圖 (邊界改變了)
    if st.session_state.last_bounds != rounded_bounds:
        st.session_state.last_bounds = rounded_bounds
        
        # 縮放太小時不抓資料
        if current_zoom < 14:
            st.session_state.status_text = "請把地圖放大一點，才會顯示停車場喔！"
            st.session_state.parking_lots = []
            st.rerun()
        else:
            # 呼叫 Overpass API
            s, w = current_bounds["_southWest"]["lat"], current_bounds["_southWest"]["lng"]
            n, e = current_bounds["_northEast"]["lat"], current_bounds["_northEast"]["lng"]
            
            query = f"""
                [out:json];
                (
                  node["amenity"="parking"]({s},{w},{n},{e});
                  way["amenity"="parking"]({s},{w},{n},{e});
                );
                out center;
            """
            
            # 改用 kumi.systems 節點，對亞洲連線較穩定且較少被限流
            url = f"https://overpass.kumi.systems/api/interpreter?data={urllib.parse.quote(query)}"
            try:
                response = requests.get(url, timeout=10)
                data = response.json()
                
                lots = []
                for el in data.get('elements', []):
                    lat = el.get('lat') or el.get('center', {}).get('lat')
                    lon = el.get('lon') or el.get('center', {}).get('lon')
                    
                    if not lat or not lon: continue
                    
                    name = "停車場"
                    if 'tags' in el:
                        name = el['tags'].get('name', name)
                        if name == "停車場" and el['tags'].get('fee') == 'yes':
                            name = "收費停車場"
                            
                    lots.append({'lat': lat, 'lon': lon, 'name': name})
                
                # 更新狀態並強制重新整理網頁，把剛剛抓到的 P 圖示畫上去
                st.session_state.parking_lots = lots
                st.session_state.status_text = f"找到了 {len(lots)} 個停車場！"
                st.rerun()
            except Exception as e:
                # 如果因為網路不穩或 API 限流而報錯，我們選擇「靜默失敗」(不顯示紅色文字)
                # 這樣就不會打擾到使用者拖曳地圖的體驗
                pass
