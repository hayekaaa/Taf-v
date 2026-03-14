import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# 1. الإعدادات
st.set_page_config(page_title='TAF Evaluator', layout='wide')

# جلب الـ API
api_key = st.secrets.get('GOOGLE_API_KEY', '')

if not api_key:
    st.error('يرجى إضافة المفتاح في Secrets باسم GOOGLE_API_KEY')
else:
    genai.configure(api_key=api_key)
    # جربنا هنا استخدام الموديل مباشرة
    model = genai.GenerativeModel('gemini-1.5-flash')

# 2. وظيفة معالجة النصوص (دمج الأسطر)
def clean_data(text, is_taf=False):
    if not text: return ""
    lines = text.split('\n')
    output = []
    current = ""
    for line in lines:
        line = line.strip()
        if not line: continue
        if is_taf:
            if re.match(r'^\d{12}', line):
                if current: output.append(current)
                current = line
            else:
                current += " " + line
            if line.endswith('='):
                output.append(current)
                current = ""
        else:
            output.append(line)
    if current: output.append(current)
    return '\n'.join(output)

# 3. الواجهة
st.title('📊 محلل جودة التوقعات الجوية')

up_m = st.file_uploader('ارفع ملف METAR', type=['txt'])
up_t = st.file_uploader('ارفع ملف TAF', type=['txt'])

if st.button('🚀 تحليل البيانات'):
    if up_m and up_t:
        try:
            m_txt = clean_data(up_m.getvalue().decode('utf-8'), False)
            t_txt = clean_data(up_t.getvalue().decode('utf-8'), True)
            
            with st.spinner('يتم الآن التحليل...'):
                # بناء البرومبت بدون f-string للأجزاء الحساسة
                main_prompt = "Compare TAF vs METAR. Evaluate first 24h. Wind, Vis, Cloud, Phenom. Output JSON list only."
                data_content = f"\n\nMETAR DATA:\n{m_txt[:7000]}\n\nTAF DATA:\n{t_txt[:7000]}"
                
                # إرسال الطلب كقائمة من النصوص (أكثر أماناً من الـ f-string)
                response = model.generate_content([main_prompt, data_content])
                
                res_text = response.text
                if '```json' in res_text:
                    res_text = res_text.split('```json')[1].split('```')[0]
                elif '```' in res_text:
                    res_text = res_text.split('```')[1].split('```')[0]
                
                results = json.loads(res_text.strip())
                st.write('### النتائج:')
                st.table(pd.DataFrame(results))
                
        except Exception as e:
            st.error(f"حدث خطأ: {e}")
            st.info("إذا ظهر خطأ 404، تأكد من تحديث مكتبة google-generativeai في ملف requirements.txt")
