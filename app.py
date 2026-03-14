import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# --- 1. إعدادات النظام ---
st.set_page_config(page_title='TAF Analysis Pro', layout='wide')

# جلب المفتاح من Secrets
API_KEY = st.secrets.get('GOOGLE_API_KEY', '')

if not API_KEY:
    st.error('يرجى ضبط GOOGLE_API_KEY في Streamlit Secrets.')
else:
    try:
        genai.configure(api_key=API_KEY)
        # تم تغيير مسمى الموديل لضمان التوافق وحل مشكلة 404
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f'خطأ في تهيئة الموديل: {e}')

# --- 2. معالجة البيانات (تاريخ 12 رقم + دمج أسطر TAF) ---

def process_data_content(text, is_taf=False):
    if not text:
        return ""
    
    lines = text.split('\n')
    processed = []
    current_block = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # هل السطر يبدأ بـ 12 رقم؟ (مثل 202603010000)
        is_new_entry = re.match(r'^\d{12}', line)
        
        if is_taf:
            if is_new_entry:
                if current_block:
                    processed.append(current_block)
                current_block = line
            else:
                # سطر تكميلي (BECMG/TEMPO) يتم دمجه مع التاف الحالي
                current_block += " " + line
            
            # إنهاء الكتلة إذا وجدنا علامة "="
            if line.endswith('='):
                processed.append(current_block)
                current_block = ""
        else:
            # للميتار كل سطر يعتبر مدخلاً مستقلاً
            processed.append(line)
            
    if current_block:
        processed.append(current_block)
        
    return '\n'.join(processed)

# --- 3. واجهة المستخدم ---

st.title('📊 نظام تقييم دقة التوقعات (Digital Timestamp Version)')
st.write('ارفع ملفات الميتار والتاف التي تبدأ بـ YYYYMMDDHHMM')

col1, col2 = st.columns(2)
with col1:
    metar_input = st.file_uploader('ملف METAR (.txt)', type=['txt'])
with col2:
    taf_input = st.file_uploader('ملف TAF (.txt)', type=['txt'])

if st.button('🚀 تشغيل التحليل العميق'):
    if metar_input and taf_input:
        try:
            # قراءة ومعالجة البيانات
            m_raw = metar_input.getvalue().decode('utf-8')
            t_raw = taf_input.getvalue().decode('utf-8')
            
            final_metar = process_data_content(m_raw, is_taf=False)
            final_taf = process_data_content(t_raw, is_taf=True)
            
            with st.spinner('جاري التحليل...'):
                # بناء البرومبت مع حماية الأقواس (استخدام {{ }} بدلاً من { })
                # هذا يحل مشكلة Invalid format specifier نهائياً
                prompt_text = f"""
                بصفتك خبير أرصاد، قارن دقة الـ TAF مع الـ METAR الفعلي.
                ملاحظة: كل سطر يبدأ بطابع زمني (12 رقم).
                المطلوب: تقييم أول 24 ساعة من كل TAF (رياح، رؤية، سحب، ظواهر).
                الرد يجب أن يكون JSON List فقط.
                
                [البيانات]:
                METAR:
                {final_metar[:7000]}
                
                TAF:
                {final_taf[:7000]}
                
                مثال للرد المطلوب:
                [[
                  {{
                    "taf_id": "رأس التاف مع التاريخ",
                    "wind_score": 90,
                    "vis_score": 80,
                    "cloud_score": 70,
                    "total_score": 80,
                    "errors": "شرح الأخطاء بالعربية"
                  }}
                ]]
                """
                
                # إرسال الطلب (بدون f-string للأجزاء التي تحتوي على أقواس لتجنب الخطأ)
                response = model.generate_content(prompt_text)
                raw_res = response.text
                
                # تنظيف استجابة JSON
                if '```json' in raw_res:
                    raw_res = raw_res.split('```json')[1].split('```')[0]
                elif '```' in raw_res:
                    raw_res = raw_res.split('```')[1].split('```')[0]
                
                analysis_data = json.loads(raw_res.strip())
                df = pd.DataFrame(analysis_data)
                
                # عرض النتائج
                st.subheader('✅ نتائج تقييم الدقة')
                
                def color_cells(val):
                    if isinstance(val, (int, float)):
                        color = 'red' if val < 60 else 'orange' if val < 85 else 'green'
                        return f'color: {color}; font-weight: bold'
                    return ''

                st.dataframe(df.style.map(color_cells, subset=['total_score']), use_container_width=True)
                
                # عرض تفاصيل الأخطاء
                for item in analysis_data:
                    if item.get('total_score', 0) < 60:
                        with st.expander(f"⚠️ تفاصيل: {item.get('taf_id')[:50]}..."):
                            st.write(f"الأخطاء: {item.get('errors')}")

        except Exception as err:
            st.error(f'حدث خطأ أثناء المعالجة: {err}')
    else:
        st.warning('يرجى رفع الملفات أولاً.')
