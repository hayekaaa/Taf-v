import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# --- 1. الإعدادات ---
API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
if not API_KEY:
    st.error("يرجى إضافة مفتاح الـ API في Secrets")
else:
    genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. الوظائف ---
def extract_date_context(filename):
    months = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    found_month = next((m for m in months if m.lower() in filename.lower()), "الشهر الحالي")
    year_match = re.search(r'20\d{2}', filename)
    found_year = year_match.group(0) if year_match else "2026"
    return f"{found_month} {found_year}"

def process_txt_file(uploaded_file):
    if uploaded_file is None: return None, None
    try:
        content = uploaded_file.getvalue().decode("utf-8")
        clean_lines = []
        for line in content.split('\n'):
            # حذف أي نص بين أقواس مربعة [مثل هذا] بشكل آمن
            line = re.sub(r"\[.*?\]", "", line).strip()
            if line: clean_lines.append(line)
        return "\n".join(clean_lines), extract_date_context(uploaded_file.name)
    except:
        return None, None

# --- 3. الواجهة ---
st.set_page_config(page_title="TAF Quality", layout="wide")
st.title("📊 نظام تقييم TAF")

c1, c2 = st.columns(2)
with c1: metar_file = st.file_uploader("ملف METAR", type=['txt'])
with c2: taf_file = st.file_uploader("ملف TAF", type=['txt'])

if st.button("بدء التحليل"):
    if metar_file and taf_file:
        with st.spinner("جاري العمل..."):
            m_text, m_date = process_txt_file(metar_file)
            t_text, t_date = process_txt_file(taf_file)
            
            prompt = f"قارن TAF و METAR لشهري {m_date}. قيم أول 24 ساعة. دقة الرياح والرؤية والسحب. رد بـ JSON list فقط."
            prompt += f"\n\nMETAR:\n{m_text[:7000]}\n\nTAF:\n{t_text[:7000]}"
            
            try:
                res = model.generate_content(prompt).text
                if "
http://googleusercontent.com/immersive_entry_chip/0
http://googleusercontent.com/immersive_entry_chip/1

### لماذا هذا الإصدار سيعمل؟
1. استخدمت `r"\[.*?\]"` بدلاً من الأنماط السابقة؛ هذا النمط يبحث عن أي شيء يبدأ بـ `[` وينتهي بـ `]` ويحذفه، وهو نمط بسيط جداً لا يحتوي على علامات المائلة المتكررة التي كانت تسبب لك الخطأ.
2. الكود أصبح مختصراً وأقل عرضة لأخطاء "المسافات" (Indentation).

**جرب الآن، وسيعمل البرنامج بإذن الله.**
