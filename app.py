import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# --- 1. الإعدادات والاتصال ---
st.set_page_config(page_title='TAF Quality Pro', layout='wide')

# جلب المفتاح من Secrets
api_key = st.secrets.get('GOOGLE_API_KEY', '')

if not api_key:
    st.error('خطأ: لم يتم العثور على GOOGLE_API_KEY في إعدادات Secrets.')
else:
    try:
        genai.configure(api_key=api_key)
        # مسمى الموديل القياسي
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f'فشل في تهيئة الموديل: {e}')

# --- 2. دالة معالجة النصوص (تنظيف RTF ودمج التاف) ---

def process_meteorological_data(raw_content, is_taf=False):
    if not raw_content:
        return ""
    
    # تحويل النص وتقسيمه لأسطر
    lines = raw_content.split('\n')
    cleaned_lines = []
    current_block = ""
    
    for line in lines:
        line = line.strip()
        # تجاهل أسطر تنسيق الـ RTF والأسطر الفارغة
        if not line or line.startswith(('{', '}', '\\', 'rtf1', 'fonttbl', 'colortbl')):
            continue
            
        # التحقق من وجود 12 رقم في بداية السطر (الطابع الزمني)
        is_new_entry = re.match(r'^\d{12}', line)
        
        if is_taf:
            if is_new_entry:
                if current_block:
                    cleaned_lines.append(current_block)
                current_block = line
            else:
                # دمج الأسطر التكميلية (مثل BECMG)
                current_block += " " + line
            
            # إنهاء التقرير عند علامة "="
            if line.endswith('='):
                cleaned_lines.append(current_block)
                current_block = ""
        else:
            # الميتار سطر مستقل
            if is_new_entry:
                cleaned_lines.append(line)
            
    if current_block:
        cleaned_lines.append(current_block)
        
    return '\n'.join(cleaned_lines)

# --- 3. واجهة المستخدم ---
st.title('📊 نظام تقييم جودة الـ TAF المطور')
st.markdown('يدعم هذا الإصدار ملفات الميتار والتاف ذات الطابع الزمني الرقمي (12 رقم).')

c1, c2 = st.columns(2)
with c1:
    m_file = st.file_uploader('ارفع ملف METAR', type=['txt'])
with c2:
    t_file = st.file_uploader('ارفع ملف TAF', type=['txt'])

if st.button('🚀 بدء التحليل العميق'):
    if m_file and t_file:
        try:
            # قراءة ومعالجة البيانات
            m_text = process_meteorological_data(m_file.getvalue().decode('utf-8'), is_taf=False)
            t_text = process_meteorological_data(t_file.getvalue().decode('utf-8'), is_taf=True)
            
            if not m_text or not t_text:
                st.warning("لم يتم العثور على بيانات صالحة. تأكد أن الملفات تحتوي على الطابع الزمني الرقمي.")
                st.stop()

            with st.spinner('جاري مقارنة التوقعات بالواقع...'):
                # بناء الأوامر كقائمة لتجنب مشاكل الأقواس (Format Specifier)
                prompt_parts = [
                    "أنت خبير أرصاد جوية. قارن دقة الـ TAF مع الـ METAR.",
                    "البيانات تبدأ بطابع زمني 12 رقم. قيم أول 24 ساعة من كل TAF.",
                    "المخرجات المطلوبة هي JSON list فقط تحتوي على: taf_id, wind_score, vis_score, cloud_score, total_score, errors (بالعربي).",
                    f"METAR DATA:\n{m_text[:8000]}",
                    f"TAF DATA:\n{t_text[:8000]}"
                ]
                
                # إرسال الطلب
                response = model.generate_content(prompt_parts)
                res_raw = response.text
                
                # تنظيف الـ JSON المستخرج
                if '```json' in res_raw:
                    res_raw = res_raw.split('```json')[1].split('```')[0]
                elif '```' in res_raw:
                    res_raw = res_raw.split('```')[1].split('```')[0]
                
                results = json.loads(res_raw.strip())
                df = pd.DataFrame(results)
                
                st.subheader('📈 نتائج تقييم الدقة')
                
                # تنسيق الجدول
                def highlight_score(val):
                    if isinstance(val, (int, float)):
                        color = 'red' if val < 60 else 'orange' if val < 85 else 'green'
                        return f'color: {color}; font-weight: bold'
                    return ''

                st.dataframe(df.style.map(highlight_score, subset=['total_score']), use_container_width=True)
                
                # عرض تفاصيل الأخطاء
                for item in results:
                    if item.get('total_score', 0) < 60:
                        with st.expander(f"⚠️ تفاصيل: {item.get('taf_id')[:50]}..."):
                            st.error(f"الأسباب: {item.get('errors')}")

        except Exception as e:
            st.error(f'حدث خطأ أثناء المعالجة: {e}')
    else:
        st.warning('يرجى رفع الملفات المطلوبة.')
