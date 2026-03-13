import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# --- 1. إعدادات الاتصال بـ AI Studio ---
# تأكد من وضع المفتاح في Secrets باسم GOOGLE_API_KEY
API_KEY = st.secrets.get("GOOGLE_API_KEY", "")

if not API_KEY:
    st.error("⚠️ لم يتم العثور على مفتاح الـ API. يرجى إضافته في إعدادات Secrets باسم GOOGLE_API_KEY")
else:
    genai.configure(api_key=API_KEY)

model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. وظائف المساعدة ---

def extract_date_context(filename):
    """استخراج الشهر والسنة من اسم الملف"""
    months = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    found_month = next((m for m in months if m.lower() in filename.lower()), "الشهر الحالي")
    year_match = re.search(r'20\d{2}', filename)
    found_year = year_match.group(0) if year_match else "2026"
    return f"{found_month} {found_year}"

def process_txt_file(uploaded_file):
    """قراءة وتنظيف ملفات TXT"""
    if uploaded_file is not None:
        try:
            # قراءة محتوى الملف وتحويله لنص
            content = uploaded_file.getvalue().decode("utf-8")
            lines = content.split('\n')
            clean_lines = []
            
            # نمط البحث عن بشكل آمن
            source_pattern = r'\'
            
            for line in lines:
                # تنظيف علامات المصدر والمسافات الزائدة
                line = re.sub(source_pattern, '', line)
                line = line.strip()
                if line:
                    clean_lines.append(line)
            
            date_ctx = extract_date_context(uploaded_file.name)
            return "\n".join(clean_lines), date_ctx
        except Exception as e:
            st.error(f"خطأ في قراءة الملف: {e}")
            return None, None
    return None, None

# --- 3. واجهة المستخدم ---

st.set_page_config(page_title="TAF Quality Evaluator", layout="wide")

st.title("📊 نظام تقييم جودة الـ TAF")
st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    metar_file = st.file_uploader("📂 ملف ميتار (METAR.txt)", type=['txt'])
with col2:
    taf_file = st.file_uploader("📂 ملف توقعات (TAF.txt)", type=['txt'])

# --- 4. التحليل ---

if st.button("🚀 بدء التحليل الذكي"):
    if metar_file and taf_file:
        with st.spinner("جاري تحليل البيانات..."):
            
            metar_text, m_date = process_txt_file(metar_file)
            taf_text, t_date = process_txt_file(taf_file)
            
            prompt = f"""
            أنت خبير أرصاد. قارن بيانات METAR و TAF لشهري {m_date}.
            الشروط: تقييم أول 24 ساعة، مراعاة SPECI و COR، وحساب دقة (Wind, Vis, Clouds, Phenom).
            النتائج بصيغة JSON List فقط (Object لكل TAF) يحتوي على:
            (taf_text, wind_acc, vis_acc, cloud_acc, phenom_acc, total_score, errors)

            البيانات:
            METAR: {metar_text[:7000]}
            TAF: {taf_text[:7000]}
            """
            
            try:
                response = model.generate_content(prompt)
                # تنظيف الـ JSON المستخرج
                json_clean = response.text.strip()
                if "```json" in json_clean:
                    json_clean = json_clean.split("```json")[1].split("```")[0].strip()
                elif "```" in json_clean:
                    json_clean = json_clean.split("```")[1].split("```")[0].strip()
                
                results = json.loads(json_clean)
                df = pd.DataFrame(results)
                
                st.subheader(f"✅ النتائج المستخلصة - {m_date}")
                st.dataframe(df.style.background_gradient(cmap='RdYlGn', subset=['total_score']), use_container_width=True)
                
                # تفاصيل الأخطاء
                st.divider()
                st.subheader("🔍 تفاصيل الأخطاء (أقل من 60%)")
                for item in results:
                    if item['total_score'] < 60:
                        with st.expander(f"⚠️ {item['taf_text'][:40]}... ({item['total_score']}%)"):
                            st.error(f"الأخطاء: {item.get('errors', 'لا توجد تفاصيل')}")
                            
            except Exception as e:
                st.error(f"حدث خطأ أثناء معالجة البيانات: {e}")
    else:
        st.warning("يرجى رفع الملفات المطلوبة.")
