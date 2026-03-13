import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# --- إعدادات AI Studio ---
API_KEY = "ضع_مفتاح_الـ_API_الخاص_بك_هنا"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- واجهة المستخدم ---
st.set_page_config(page_title="TAF Quality Evaluator", layout="wide")
st.title("📊 نظام تقييم TAF المتقدم (رفع ملفات)")

# --- قسم رفع الملفات ---
col_file1, col_file2 = st.columns(2)

with col_file1:
    metar_file = st.file_uploader("📂 ارفع ملف METAR (Excel/CSV)", type=['xlsx', 'csv'])
with col_file2:
    taf_file = st.file_uploader("📂 ارفع ملف TAF (Excel/CSV)", type=['xlsx', 'csv'])

# دالة لقراءة الملفات وتحويلها لنص
def process_file(file):
    if file is not None:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        # تحويل محتوى العمود الأول (أو عمود محدد) إلى نص مجمع
        return "\n".join(df.iloc[:, 0].astype(str).tolist())
    return None

if st.button("🚀 تحليل البيانات المرفوعة", type="primary", use_container_width=True):
    if metar_file and taf_file:
        with st.spinner("جاري قراءة الملفات وتحليلها عبر الذكاء الاصطناعي..."):
            
            metar_text = process_file(metar_file)
            taf_text = process_file(taf_file)
            
            # البرومبت (System Instructions)
            prompt = f"""
            حلل جودة الـ TAF بمقارنتها بـ METAR. 
            الشروط:
            1. التقييم لأول 24 ساعة من كل TAF فقط.
            2. المعايير: (Wind, Vis, Clouds, Phenomena, Change Groups).
            3. المخرجات JSON حصراً.
            4. إذا كان التقييم < 60%، اشرح الأخطاء بالتفصيل (مثل: تأخر في رصد الضباب، خطأ في سرعة الرياح بـ 10 عقد، إلخ).

            البيانات المرفوعة:
            METAR Data: {metar_text[:10000]}  # نأخذ عينة إذا كان الملف ضخماً جداً
            TAF Data: {taf_text[:10000]}
            """
            
            try:
                response = model.generate_content(prompt)
                raw_json = response.text.replace("```json", "").replace("```", "").strip()
                data_list = json.loads(raw_json)
                
                df_results = pd.DataFrame(data_list)
                
                # --- عرض النتائج ---
                st.subheader("✅ التقرير النهائي")
                
                # تلوين التقييم العام (خلفية الجدول)
                def color_total(val):
                    color = 'red' if val < 60 else 'orange' if val < 80 else 'green'
                    return f'color: {color}; font-weight: bold'

                st.dataframe(
                    df_results[["taf_text", "wind", "vis", "clouds", "total"]].style.applymap(color_total, subset=['total']),
                    use_container_width=True
                )

                # --- قسم الأخطاء الذكي ---
                st.divider()
                st.subheader("🔍 لماذا التقييم منخفض؟")
                low_quality = df_results[df_results['total'] < 60]
                
                if not low_quality.empty:
                    for _, row in low_quality.iterrows():
                        with st.expander(f"⚠️ خطأ في TAF: {row['taf_text'][:40]}... (النسبة: {row['total']}%)"):
                            st.error(f"**الأسباب:** {row['errors']}")
                else:
                    st.success("لا توجد أخطاء فادحة في ملفات هذا الشهر!")

            except Exception as e:
                st.error(f"فشل التحليل. تأكد من تنسيق الملف أو الـ API Key. الخطأ: {e}")
    else:
        st.warning("يرجى رفع الملفين معاً للبدء.")
