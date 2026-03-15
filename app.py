import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# --- 1. إعدادات الصفحة والاتصال ---
st.set_page_config(page_title="TAF Quality Evaluator", layout="wide", page_icon="✈️")

# جلب المفتاح من Secrets
api_key = st.secrets.get("GOOGLE_API_KEY", "")

if not api_key:
    st.error("⚠️ لم يتم العثور على مفتاح الـ API. تأكد من إضافته في Settings > Secrets.")
else:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

# --- 2. دالة تنظيف البيانات (تنظيف RTF ودمج أسطر التاف) ---

def process_meteorological_data(raw_content, is_taf=False):
    if not raw_content: return ""
    
    # تنظيف أكواد RTF (مثل \rtf1, \ansi, \par ...) لضمان قراءة البيانات فقط
    text = re.sub(r'\\{.*?\\}|[{}]|\\(?! )[^ ]* *', '', raw_content)
    
    lines = text.split('\n')
    processed_blocks = []
    current_block = ""
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith(('rtf1', 'fonttbl', 'colortbl')): continue
            
        # التحقق من وجود الطابع الزمني (12 رقم) في بداية السطر
        is_new_entry = re.match(r'^\d{12}', line)
        
        if is_taf:
            if is_new_entry:
                if current_block: processed_blocks.append(current_block)
                current_block = line
            else:
                current_block += " " + line
            
            if line.endswith('='):
                processed_blocks.append(current_block)
                current_block = ""
        else:
            if is_new_entry: processed_blocks.append(line)
            
    if current_block: processed_blocks.append(current_block)
    return '\n'.join(processed_blocks)

# --- 3. واجهة المستخدم ---
st.title("📊 نظام تقييم جودة الـ TAF المطور")
st.info("قم برفع ملفات الميتار والتاف (بصيغة TXT أو RTF).")

col1, col2 = st.columns(2)
with col1:
    m_file = st.file_uploader("📂 ارفع ملف الميتار (METAR)", type=["txt"])
with col2:
    t_file = st.file_uploader("📂 ارفع ملف التوقعات (TAF)", type=["txt"])

if st.button("🚀 بدء التحليل الذكي"):
    if m_file and t_file:
        try:
            # قراءة ومعالجة البيانات
            m_text = process_meteorological_data(m_file.getvalue().decode("utf-8"), is_taf=False)
            t_text = process_meteorological_data(t_file.getvalue().decode("utf-8"), is_taf=True)
            
            if not m_text or not t_text:
                st.warning("⚠️ لم يتم العثور على بيانات صالحة. تأكد أن الملفات تحتوي على الطابع الزمني الرقمي.")
                st.stop()

            with st.spinner("جاري مقارنة التوقعات بالواقع..."):
                # بناء البرومبت كقائمة لتجنب مشاكل الأقواس
                prompt_parts = [
                    "أنت خبير أرصاد جوية. قارن دقة الـ TAF مع الـ METAR الفعلي.",
                    "البيانات تبدأ بطابع زمني 12 رقم. قيم أول 24 ساعة من كل TAF (الرياح، الرؤية، السحب، الظواهر).",
                    "المخرجات JSON list فقط تحتوي على: taf_id, wind_score, vis_score, cloud_score, total_score, errors (بالعربية).",
                    f"METAR DATA:\n{m_text[:8000]}",
                    f"TAF DATA:\n{t_text[:8000]}"
                ]
                
                response = model.generate_content(prompt_parts)
                res_raw = response.text
                
                if '```json' in res_raw:
                    res_raw = res_raw.split('```json')[1].split('```')[0]
                elif '```' in res_raw:
                    res_raw = res_raw.split('```')[1].split('```')[0]
                
                results = json.loads(res_raw.strip())
                st.subheader("📈 نتائج التقييم")
                st.dataframe(pd.DataFrame(results), use_container_width=True)
                
        except Exception as e:
            st.error(f"حدث خطأ في المعالجة: {e}")
    else:
        st.warning("يرجى رفع الملفات المطلوبة.")
