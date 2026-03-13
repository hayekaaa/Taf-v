import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# --- 1. إعدادات الأمان والاتصال بـ AI Studio ---
# تأكد من إضافة GOOGLE_API_KEY في قسم Secrets على Streamlit Cloud
API_KEY = st.secrets.get("GOOGLE_API_KEY", "")

if not API_KEY:
    st.error("⚠️ لم يتم العثور على مفتاح الـ API. يرجى إضافته في إعدادات Secrets.")
else:
    genai.configure(api_key=API_KEY)

model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. وظائف المساعدة (Helper Functions) ---

def extract_date_context(filename):
    """استخراج الشهر والسنة من اسم الملف لتقديم سياق دقيق للذكاء الاصطناعي"""
    months = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    
    found_month = next((m for m in months if m.lower() in filename.lower()), "الشهر الحالي")
    year_match = re.search(r'20\d{2}', filename)
    found_year = year_match.group(0) if year_match else "2026"
    
    return f"{found_month} {found_year}"

def process_txt_file(uploaded_file):
    """قراءة ملفات TXT وتنظيفها من أي نوس زائدة أو علامات مصدر"""
    if uploaded_file is not None:
        try:
            # قراءة محتوى الملف
            stringio = uploaded_file.getvalue().decode("utf-8")
            clean_lines = []
            
            for line in stringio.split('\n'):
                # تنظيف علامات المصدر مثل وأي مسافات زائدة
                line = re.sub(r'\', '', line).strip()
                if line:
                    clean_lines.append(line)
            
            date_ctx = extract_date_context(uploaded_file.name)
            return "\n".join(clean_lines), date_ctx
        except Exception as e:
            st.error(f"خطأ في قراءة الملف: {e}")
            return None, None
    return None, None

# --- 3. تصميم واجهة المستخدم ---

st.set_page_config(page_title="TAF Quality Evaluator", layout="wide", page_icon="✈️")

st.markdown("""
    <style>
    .main { text-align: right; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 نظام تقييم جودة الـ TAF (نسخة الويب)")
st.info("قم برفع ملفات الميتار والتاف بصيغة .txt ليقوم النظام بتحليلها ومقارنتها.")

# أعمدة رفع الملفات
col1, col2 = st.columns(2)

with col1:
    metar_file = st.file_uploader("📂 ارفع ملف ميتار شهر كامل (METAR.txt)", type=['txt'])
with col2:
    taf_file = st.file_uploader("📂 ارفع ملف التوقعات المقابل (TAF.txt)", type=['txt'])

# --- 4. منطق التحليل ---

if st.button("🚀 بدء التحليل والمقارنة"):
    if metar_file and taf_file:
        with st.spinner("جاري تحليل البيانات... قد يستغرق ذلك ثواني بناءً على حجم الملف."):
            
            # معالجة الملفات
            metar_text, m_date = process_txt_file(metar_file)
            taf_text, t_date = process_txt_file(taf_file)
            
            # البرومبت الموجه لـ Gemini
            prompt = f"""
            أنت خبير أرصاد جوية متخصص. قم بتحليل جودة الـ TAF بمقارنتها ببيانات الـ METAR الفعلية لشهري {m_date}.
            
            القواعد:
            1. حلل أول 24 ساعة فقط من كل TAF.
            2. قارن العناصر: (Wind, Visibility, Clouds, Phenomena).
            3. خذ في الاعتبار تقارير SPECI و COR الموجودة في البيانات.
            4. احسب درجة الدقة لكل عنصر (0-100) والدرجة الكلية.
            
            البيانات المرفقة:
            [METAR Data]:
            {metar_text}
            
            [TAF Data]:
            {taf_text}
            
            المطلوب: رد بصيغة JSON فقط كقائمة من الكائنات (List of Objects) تحتوي على:
            (taf_text, wind_acc, vis_acc, cloud_acc, phenom_acc, total_score, errors)
            """
            
            try:
                # استدعاء النموذج
                response = model.generate_content(prompt)
                
                # تنظيف مخرجات JSON
                json_str = response.text.replace("```json", "").replace("```", "").strip()
                results_data = json.loads(json_str)
                
                # تحويل النتائج إلى جدول DataFrame
                df = pd.DataFrame(results_data)
                
                # عرض النتائج
                st.subheader(f"✅ تقرير الجودة - {m_date}")
                
                # تنسيق الجدول (ألوان للدرجات)
                st.dataframe(
                    df.style.background_gradient(cmap='RdYlGn', subset=['total_score']),
                    use_container_width=True
                )
                
                # عرض أسباب الأخطاء للتقييم المنخفض
                st.divider()
                st.subheader("🔍 تفاصيل التقييمات الضعيفة (< 60%)")
                
                low_scores = [item for item in results_data if item['total_score'] < 60]
                
                if low_scores:
                    for item in low_scores:
                        with st.expander(f"⚠️ {item['taf_text'][:50]}... (الدرجة: {item['total_score']}%)"):
                            st.write(f"**الأخطاء المرصودة:** {item['errors']}")
                else:
                    st.success("جميع التوقعات كانت دقيقة بنسبة جيدة جداً!")
                    
            except Exception as e:
                st.error(f"عذراً، حدث خطأ أثناء التحليل الذكي: {e}")
    else:
        st.warning("يرجى التأكد من رفع كلا الملفين (METAR و TAF) للبدء.")

st.sidebar.markdown("---")
st.sidebar.caption("تطوير نظام تقييم الأرصاد الجوية الذكي v1.0")
