import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# --- إعدادات AI Studio ---
# يفضل وضع المفتاح في Secrets كما شرحنا سابقاً
API_KEY = st.secrets.get("GOOGLE_API_KEY", "ضع_مفتاحك_هنا")
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="TAF Analysis Tool", layout="wide")
st.title("📊 نظام تحليل ملفات الأرصاد (Text-Based)")

# دالة استخراج التاريخ من اسم الملف
def extract_date_context(filename):
    months = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    found_month = next((m for m in months if m.lower() in filename.lower()), "هذا الشهر")
    year_match = re.search(r'20\d{2}', filename)
    found_year = year_match.group(0) if year_match else "2026"
    return f"{found_month} {found_year}"

# دالة تنظيف وقراءة ملفات الـ TXT
def process_txt_file(uploaded_file):
    if uploaded_file is not None:
        # قراءة الملف كنص
        stringio = uploaded_file.getvalue().decode("utf-8")
        # تنظيف النص: إزالة الأسطر الفارغة وإزالة علامات 
        clean_lines = []
        for line in stringio.split('\n'):
            line = re.sub(r'\', '', line).strip() # حذف علامات المصدر
            if line:
                clean_lines.append(line)
        
        date_ctx = extract_date_context(uploaded_file.name)
        return "\n".join(clean_lines), date_ctx
    return None, None

# واجهة رفع الملفات
col1, col2 = st.columns(2)
with col1:
    metar_file = st.file_uploader("📂 ارفع ملف METAR (.txt)", type=['txt'])
with col2:
    taf_file = st.file_uploader("📂 ارفع ملف TAF (.txt)", type=['txt'])

if st.button("🚀 معالجة وتحليل البيانات", type="primary", use_container_width=True):
    if metar_file and taf_file:
        with st.spinner("جاري قراءة النصوص وتنظيمها للتحليل..."):
            
            metar_text, m_date = process_txt_file(metar_file)
            taf_text, t_date = process_txt_file(taf_file)
            
            prompt = f"""
            بصفتك خبير أرصاد، قم بمقارنة بيانات METAR و TAF لشهري {m_date}.
            
            المهام:
            1. تنظيم البيانات زمنياً ومقارنة كل TAF بالـ METAR الفعلي لنفس الفترة.
            2. تقييم أول 24 ساعة من كل TAF.
            3. حساب الدقة لـ (الرياح، الرؤية، السحب، الظواهر).
            4. إذا كان التقييم العام < 60%، اذكر الأسباب التقنية بدقة.
            
            البيانات المستلمة:
            [METAR DATA]:
            {metar_text}
            
            [TAF DATA]:
            {taf_text}
            
            أعطني النتائج حصراً بصيغة JSON List (Object لكل TAF) يحتوي على:
            (taf_text, wind_acc, vis_acc, cloud_acc, total_score, errors)
            """
            
            try:
                response = model.generate_content(prompt)
                # تنظيف استجابة JSON
                clean_json = response.text.replace("```json", "").replace("```", "").strip()
                results = json.loads(clean_json)
                
                # عرض النتائج في جدول تفاعلي
                df = pd.DataFrame(results)
                st.subheader(f"✅ نتائج التقييم لشهر {m_date}")
                
                # تحسين شكل الجدول
                st.dataframe(
                    df.style.background_gradient(cmap='RdYlGn', subset=['total_score']),
                    use_container_width=True
                )
                
                # قسم تحليل الأخطاء
                st.divider()
                st.subheader("🔍 تحليل الأخطاء (للمستوى الضعيف)")
                for item in results:
                    if item['total_score'] < 60:
                        with st.expander(f"⚠️ {item['taf_text'][:40]}... (دقة: {item['total_score']}%)"):
                            st.write(f"**الأخطاء المرصودة:** {item['errors']}")

            except Exception as e:
                st.error(f"حدث خطأ في التحليل: {e}")
                st.info("تأكد من أن الملفات تحتوي على بيانات ميتار وتاف صحيحة.")
