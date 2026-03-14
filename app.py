import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# --- 1. الإعدادات الأساسية ---
st.set_page_config(page_title='TAF Evaluator Pro', layout='wide', page_icon='✈️')

# جلب المفتاح من Secrets
api_key = st.secrets.get('GOOGLE_API_KEY', '')

if not api_key:
    st.error('يرجى إضافة GOOGLE_API_KEY في إعدادات Secrets في Streamlit Cloud.')
else:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. معالجة البيانات حسب صيغتك الخاصة ---

def format_weather_data(text, is_taf=False):
    """
    تقوم بدمج الأسطر التي تتبع نفس التقرير (خاصة التاف المكسور الأسطر)
    بناءً على وجود الطابع الزمني المكون من 12 رقماً في البداية.
    """
    if not text:
        return ""
    
    lines = text.split('\n')
    results = []
    temp_block = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # هل يبدأ السطر بـ 12 رقماً (التاريخ والوقت)؟
        starts_with_time = re.match(r'^\d{12}', line)
        
        if is_taf:
            if starts_with_time:
                if temp_block:
                    results.append(temp_block)
                temp_block = line
            else:
                # سطر تابع للتاف السابق (مثل BECMG أو TEMPO)
                temp_block += " " + line
            
            # إنهاء الكتلة عند وجود علامة "="
            if line.endswith('='):
                results.append(temp_block)
                temp_block = ""
        else:
            # الميتار كل سطر مستقل
            results.append(line)
            
    if temp_block:
        results.append(temp_block)
        
    return '\n'.join(results)

# --- 3. واجهة البرنامج ---

st.title('📊 نظام تحليل وتقييم الـ TAF')
st.info('يدعم هذا الإصدار الصيغة الرقمية (YYYYMMDDHHMM) والتاف متعدد الأسطر.')

c1, c2 = st.columns(2)
with c1:
    m_file = st.file_uploader('ارفع ملف METAR (.txt)', type=['txt'])
with c2:
    t_file = st.file_uploader('ارفع ملف TAF (.txt)', type=['txt'])

if st.button('🚀 بدء التحليل العميق'):
    if m_file and t_file:
        try:
            # قراءة ومعالجة البيانات
            metar_raw = m_file.getvalue().decode('utf-8')
            taf_raw = t_file.getvalue().decode('utf-8')
            
            cleaned_metar = format_weather_data(metar_raw, is_taf=False)
            cleaned_taf = format_weather_data(taf_raw, is_taf=True)
            
            with st.spinner('جاري المقارنة بين التوقعات والواقع...'):
                
                # بناء البرومبت (تم تأمين الأقواس بمضاعفتها {{ }} لمنع الخطأ)
                prompt = f"""
                أنت خبير أرصاد جوية. قم بتقييم دقة الـ TAF مقارنة بالـ METAR.
                البيانات تبدأ بطابع زمني 12 رقم (سنة شهر يوم ساعة دقيقة).
                
                المطلوب:
                1. قارن أول 24 ساعة من كل TAF مقابل الميتارات في نفس الفترة.
                2. قيم (الرياح، الرؤية، السحب، والظواهر) من 100.
                3. رد بصيغة JSON List فقط.
                
                [البيانات]:
                METAR:
                {cleaned_metar[:8000]}
                
                TAF:
                {cleaned_taf[:8000]}
                
                Response format example:
                [[
                  {{
                    "taf_id": "رأس التاف هنا",
                    "wind_score": 90,
                    "vis_score": 80,
                    "cloud_score": 70,
                    "total_score": 80,
                    "errors": "شرح الأخطاء بالعربية"
                  }}
                ]]
                """
                
                response = model.generate_content(prompt)
                full_res = response.text
                
                # استخراج الـ JSON وتنظيفه
                if '```json' in full_res:
                    full_res = full_res.split('```json')[1].split('```')[0]
                elif '```' in full_res:
                    full_res = full_res.split('```')[1].split('```')[0]
                
                data = json.loads(full_res.strip())
                df = pd.DataFrame(data)
                
                # عرض النتائج
                st.subheader('✅ نتائج التقييم')
                
                def color_logic(val):
                    if isinstance(val, (int, float)):
                        c = 'red' if val < 60 else 'orange' if val < 85 else 'green'
                        return f'color: {c}; font-weight: bold'
                    return ''

                st.dataframe(df.style.map(color_logic, subset=['total_score']), use_container_width=True)
                
                # قسم التحليل التفصيلي
                st.divider()
                st.subheader('🔍 تحليل الأخطاء')
                for item in data:
                    if item.get('total_score', 0) < 60:
                        with st.expander(f"⚠️ {item.get('taf_id')[:50]}..."):
                            st.error(f"الدقة: {item.get('total_score')}%")
                            st.write(f"الأسباب: {item.get('errors')}")

        except Exception as e:
            st.error(f'حدث خطأ في النظام: {str(e)}')
            st.info('تأكد من أن الملفات تتبع الصيغة التي ذكرتها.')
    else:
        st.warning('يرجى رفع الملفين أولاً.')
