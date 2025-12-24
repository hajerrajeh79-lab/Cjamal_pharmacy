import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import os
import math
from datetime import datetime, time

# ---------------- إعداد الصفحة ----------------
st.set_page_config(page_title="نظام صيدليات الجميل", layout="wide")
DATA_FILE = "pharmacies_data.json"

# ---------------- تحميل / حفظ البيانات ----------------
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ---------------- حساب المسافة ----------------
def calc_dist(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ---------------- التحقق من حالة الصيدلية (مفتوحة/مغلقة) ----------------
def is_open(open_t_str, close_t_str):
    now = datetime.now().time()
    try:
        open_t = datetime.strptime(open_t_str, "%H:%M").time()
        close_t = datetime.strptime(close_t_str, "%H:%M").time()
        if open_t > close_t:
            return now >= open_t or now <= close_t
        else:
            return open_t <= now <= close_t
    except (ValueError, TypeError):
        return False

# ---------------- تحديد اليوم الحالي ----------------
days = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
map_days = {"Saturday": "السبت", "Sunday": "الأحد", "Monday": "الاثنين", "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء", "Thursday": "الخميس", "Friday": "الجمعة"}
today = map_days.get(datetime.now().strftime("%A"), "غير معروف")

# ---------------- تحميل البيانات ----------------
pharmacies = load_data()

# ---------------- واجهة المستخدم ----------------
st.markdown("<h2 style='text-align:center'>🏥 نظام إدارة صيدليات مدينة الجميل</h2>", unsafe_allow_html=True)

# ---------------- الشريط الجانبي (Sidebar) ----------------
with st.sidebar:
    st.header("➕ إضافة صيدلية جديدة")
    with st.form("add_pharmacy_form", clear_on_submit=True):
        name = st.text_input("اسم الصيدلية")
        loc = st.text_input("العنوان")
        lat = st.number_input("خط العرض (Latitude)", value=32.85, format="%.6f")
        lon = st.number_input("خط الطول (Longitude)", value=12.05, format="%.6f")
        duty = st.selectbox("يوم المناوبة", days)
        open_t = st.time_input("وقت الفتح", time(8, 0))
        close_t = st.time_input("وقت الإغلاق", time(22, 0))
        submitted = st.form_submit_button("حفظ الصيدلية")

        if submitted:
            if name and loc:
                new_pharmacy = {
                    "name": name, "location": loc, "lat": lat, "lon": lon,
                    "duty": duty, "open": open_t.strftime("%H:%M"), "close": close_t.strftime("%H:%M")
                }
                pharmacies.append(new_pharmacy)
                save_data(pharmacies)
                st.success(f"تم حفظ صيدلية '{name}' بنجاح!")
                st.rerun()
            else:
                st.error("الرجاء إدخال اسم الصيدلية وعنوانها.")

    st.divider()

    # --- قسم الحذف (تمت إعادة تنظيمه) ---
    if pharmacies:
        st.header("🗑 حذف صيدلية")
        # إنشاء قائمة أسماء الصيدليات
        pharmacy_names = [p['name'] for p in pharmacies]
        # إنشاء selectbox لاختيار الصيدلية
        pharmacy_to_delete = st.selectbox("اختر الصيدلية لحذفها", pharmacy_names)
        
        # زر الحذف
        if st.button(f"حذف صيدلية '{pharmacy_to_delete}'"):
            # إعادة بناء قائمة الصيدليات مع استثناء الصيدلية المحذوفة
            pharmacies = [p for p in pharmacies if p['name'] != pharmacy_to_delete]
            save_data(pharmacies)
            st.success(f"تم حذف صيدلية '{pharmacy_to_delete}' بنجاح.")
            st.rerun()

    st.divider()
    
    st.header("📍 موقعي الحالي")
    my_lat = st.number_input("خط العرض لموقعي", value=32.852, format="%.6f", key="my_lat")
    my_lon = st.number_input("خط الطول لموقعي", value=12.058, format="%.6f", key="my_lon")

# ---------------- معالجة البيانات ----------------
nearest, min_d = None, float('inf')
# التأكد من أن my_lat و my_lon ليسا None قبل الحساب
my_lat = st.session_state.get('my_lat', 32.852)
my_lon = st.session_state.get('my_lon', 12.058)

if pharmacies:
    for p in pharmacies:
        # التأكد من وجود الإحداثيات في بيانات الصيدلية
        p_lat = p.get("lat")
        p_lon = p.get("lon")
        if p_lat is not None and p_lon is not None:
            dist = calc_dist(my_lat, my_lon, p_lat, p_lon)
            p["dist"] = dist
            if dist < min_d:
                nearest, min_d = p, dist

# ---------------- تقسيم الواجهة إلى أعمدة ----------------
col1, col2 = st.columns([1, 2])

# ---------------- عرض قائمة الصيدليات ----------------
with col1:
    st.subheader("📋 قائمة الصيدليات")
    if not pharmacies:
        st.info("لا توجد صيدليات محفوظة حتى الآن.")
    else:
        # الفرز والعرض
        # التأكد من وجود 'dist' قبل الفرز
        sorted_pharmacies = sorted([p for p in pharmacies if 'dist' in p], key=lambda x: x['dist'])
        for p in sorted_pharmacies:
            open_now = is_open(p.get("open"), p.get("close"))
            status = "🟢 مفتوحة الآن" if open_now else "🔴 مغلقة الآن"
            color = "green" if open_now else "red"
            st.markdown(f"""
            <div style="border:1px solid #ddd; padding:10px; border-radius:8px; margin-bottom:10px; border-left: 5px solid {color};">
                <b>{p.get('name', 'N/A')}</b><br>
                <small>📍 {p.get('location', 'N/A')}</small><br>
                <small>⏰ {p.get('open', 'N/A')} - {p.get('close', 'N/A')}</small><br>
                <span style="color:{color}; font-weight:bold;">{status}</span><br>
                <small>📏 {p.get('dist', 0):.2f} كم تقريبًا</small>
            </div>
            """, unsafe_allow_html=True)

# ---------------- عرض الخريطة ----------------
with col2:
    st.subheader("🗺 الخريطة")
    m = folium.Map(location=[my_lat, my_lon], zoom_start=13)

    folium.Marker([my_lat, my_lon], tooltip="موقعي", icon=folium.Icon(color="black", icon="user")).add_to(m)

    for p in pharmacies:
        p_lat = p.get("lat")
        p_lon = p.get("lon")
        if p_lat is None or p_lon is None:
            continue # تخطي الصيدليات التي لا تحتوي على إحداثيات

        open_now = is_open(p.get("open"), p.get("close"))
        
        marker_color = "blue" # اللون الافتراضي
        if not open_now:
            marker_color = "gray"
        elif p.get("duty") == today:
            marker_color = "red"
        
        # الأقرب يجب أن يتجاوز الألوان الأخرى
        if nearest and p["name"] == nearest["name"] and open_now:
            marker_color = "green"

        popup_html = f"""<b>{p.get('name', 'N/A')}</b><br>{p.get('location', 'N/A')}"""
        folium.Marker(
            location=[p_lat, p_lon],
            tooltip=p.get("name"),
            popup=folium.Popup(popup_html, max_width=200),
            icon=folium.Icon(color=marker_color, icon="plus-sign", prefix='glyphicon')
        ).add_to(m)

    st_folium(m, width="100%", height=500, returned_objects=[])

st.divider()
st.caption(f"اليوم: {today} | 🟢 الأقرب | 🔴 مناوبة | 🔵 مفتوحة | ⚫️ موقعك | ⚪️ مغلقة")