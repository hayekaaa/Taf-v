import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title='TAF Quality Evaluator', layout='wide')

# جلب المفتاح من Secrets
api_key = st.secrets.get('GOOGLE_API_KEY', '')

if not api_key:
    st.error('خطأ: لم يتم العثور على GOOGLE_API_KEY في إعدادات Secrets.')
else:
    try:
        genai.configure(api_key=api_key)
        # استخدام المسمى القياسي للموديل
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f'فشل في الاتصال بالذكاء الاصطناعي: {e}')

# --- 2. دالة تنظيف البيانات (تتعامل مع الطابع الزمني وتنسيق الملفات) ---

def process_weather_data(raw_content, is_taf=False):
    if not raw_content:
        return ""
    
    # تحويل النص وإزالة أي أكواد تنسيق (RTF) إذا وجدت
    lines = raw_content.split('\n')
    cleaned_lines = []
    current_taf = ""
    
    for line in lines:
        line = line.strip()
        # تخطي أسطر التنسيق أو الأسطر الفارغة
        if not line or line.startswith(('{', '}', '\\')):
            continue
            
        # التحقق من وجود 12 رقم (الطابع الزمني) في بداية السطر
        is_new_entry = re.match(r'^\d{12}', line)
        
        if is_taf:
            if is_new_entry:
                if current_taf:
                    cleaned_lines.append(current_taf)
                current_taf = line
            else:
                # دمج الأسطر التابعة للتاف (BECMG/TEMPO)
                current_taf += " " + line
            
            if line.endswith('='):
                cleaned_lines.append(current_taf)
                current_taf = ""
        else:
            # الميتار يؤخذ كما هو
            cleaned_lines.append(line)
            
    if current_taf:
        cleaned_lines.append(current_taf)
        
    return '\n'.join(cleaned_lines)

# --- 3. واجهة المستخدم ---
st.title('📊 نظام تقييم دقة التوقعات الجوية')
st.write('ارفع ملفات METAR و TAF بالصيغة الرقمية (YYYYMMDDHHMM)')

c1, c2 = st.columns(2)
with c1:
    m_file = st.file_uploader('ارفع ملف METAR (.txt)', type=['txt'])
with c2:
    t_file = st.file_uploader('ارفع ملف TAF (.txt)', type=['txt'])

if st.button('🚀 بدء التحليل العميق'):
    if m_file and t_file:
        try:
            # قراءة الملفات
            m_text = process_weather_data(m_file.getvalue().decode('utf-8'), is_taf=False)
            t_text = process_weather_data(t_file.getvalue().decode('utf-8'), is_taf=True)
            
            with st.spinner('جاري المقارنة والتحليل...'):
                # بناء الأوامر (استخدام المصفوفة يحل مشكلة الأقواس Invalid format specifier)
                instructions = "Evaluate TAF accuracy vs METAR. Compare first 24h only. Wind, Vis, Clouds, Phenom."
                format_guide = "Response MUST be a JSON list of objects with: taf_id, wind_score, vis_score, cloud_score, total_score, errors (in Arabic)."
                data_payload = f"METAR DATA:\n{m_text[:8000]}\n\nTAF DATA:\n{t_text[:8000]}"
                
                # إرسال الطلب
                response = model.generate_content([instructions, format_guide, data_payload])
                res_raw = response.text
                
                # استخراج الـ JSON
                if '```json' in res_raw:
                    res_raw = res_raw.split('```json')[1].split('```')[0]
                elif '```' in res_raw:
                    res_raw = res_raw.split('```')[1].split('```')[0]
                
                results = json.loads(res_raw.strip())
                df = pd.DataFrame(results)
                
                st.subheader('📈 تقرير الدقة')
                
                def color_scores(val):
                    if isinstance(val, (int, float)):
                        color = 'red' if val < 60 else 'orange' if val < 85 else 'green'
                        return f'color: {color}; font-weight: bold'
                    return ''

                st.dataframe(df.style.map(color_scores, subset=['total_score']), use_container_width=True)
                
                # عرض الأخطاء
                for item in results:
                    if item.get('total_score', 0) < 60:
                        with st.expander(f"⚠️ تفاصيل الخطأ: {item.get('taf_id')[:50]}..."):
                            st.error(f"الأسباب: {item.get('errors')}")

        except Exception as e:
            st.error(f'حدث خطأ في المعالجة: {e}')
    else:
        st.warning('يرجى رفع الملفات المطلوبة أولاً.')
