import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# إعدادات الصفحة
st.set_page_config(page_title='TAF Evaluator', layout='wide')

# الحصول على المفتاح من Secrets
api_key = st.secrets.get('GOOGLE_API_KEY', '')

if not api_key:
    st.error('Missing API Key in Secrets')
else:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

def get_date_from_name(filename):
    return filename.split('.')[0]

def clean_text(uploaded_file):
    if uploaded_file is None:
        return None
    try:
        raw_content = uploaded_file.getvalue().decode('utf-8')
        lines = raw_content.split('\n')
        final_lines = []
        for line in lines:
            # حذف أي نص بين أقواس مربعة بطريقة بسيطة
            cleaned = re.sub(r'\[.*?\]', '', line).strip()
            if cleaned:
                final_lines.append(cleaned)
        return '\n'.join(final_lines)
    except:
        return None

st.title('📊 نظام تقييم الـ TAF')

c1, c2 = st.columns(2)
with c1:
    m_file = st.file_uploader('Upload METAR (.txt)', type=['txt'])
with c2:
    t_file = st.file_uploader('Upload TAF (.txt)', type=['txt'])

if st.button('Start Analysis'):
    if m_file and t_file:
        with st.spinner('Analyzing...'):
            metar_text = clean_text(m_file)
            taf_text = clean_text(t_file)
            
            # بناء البرومبت
            p = 'Evaluate TAF vs METAR. Rules: 24h only, score Wind/Vis/Clouds/Phenom 0-100.'
            p += ' Provide a JSON list: [{"taf_text": "...", "total_score": 85, "errors": "..."}]'
            p += '\n\nMETAR:\n' + metar_text[:7000]
            p += '\n\nTAF:\n' + taf_text[:7000]
            
            try:
                res = model.generate_content(p).text
                
                # استخراج الـ JSON
                if '```json' in res:
                    res = res.split('```json')[1].split('```')[0]
                elif '```' in res:
                    res = res.split('```')[1].split('```')[0]
                
                data = json.loads(res.strip())
                df = pd.DataFrame(data)
                
                st.subheader('Results')
                st.dataframe(df, use_container_width=True)
                
                for item in data:
                    score = item.get('total_score', 0)
                    if score < 60:
                        with st.expander('Errors for: ' + item.get('taf_text', '')[:50]):
                            st.write(item.get('errors', 'No details'))
            except Exception as e:
                st.error('Error during analysis: ' + str(e))
    else:
        st.warning('Please upload both files')
