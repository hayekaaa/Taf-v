import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# --- 1. إعدادات الصفحة والأمان ---
st.set_page_config(page_title='نظام تقييم TAF المطور', layout='wide', page_icon='✈️')

# جلب مفتاح الـ API من Secrets
api_key = st.secrets.get('GOOGLE_API_KEY', '')

if not api_key:
    st.error('خطأ: لم يتم العثور على مفتاح GOOGLE_API_KEY في إعدادات Secrets.')
else:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. دوال معالجة البيانات (المحرك الرئيسي) ---

def process_meteorological_data(raw_text, is_taf=False):
    """
    تقوم هذه الدالة بتنظيف النص ودمج أسطر الـ TAF المكسورة 
    بناءً على وجود الطابع الزمني (12 رقم) في بداية السطر.
    """
    if not raw_text:
        return ""
    
    lines = raw_text.split('\n')
    processed_blocks = []
    current_block = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # التحقق إذا كان السطر يبدأ بطابع زمني (YYYYMMDDHHMM)
        has_timestamp = re.match(r'^\d{12}', line)
        
        if is_taf:
            if has_timestamp:
                # إذا وجدنا طابع زمني جديد، نحفظ الكتلة السابقة ونبدأ واحدة جديدة
                if current_block:
                    processed_blocks.append(current_block)
                current_block = line
            else:
                # إذا لم يبدأ السطر برقم، فهو تابع للـ TAF السابق (مثل BECMG أو TEMPO)
                current_block += " " + line
            
            # إذا انتهى السطر بعلامة "=" يتم إغلاق الكتلة فوراً
            if line.endswith('='):
                processed_blocks.append(current_block)
                current_block = ""
        else:
            # بالنسبة للميتار، كل سطر هو وحدة مستقلة
            processed_blocks.append(line)
            
    # إضافة آخر كتلة إذا لم تكن فارغة
    if current_block:
        processed_blocks.append(current_block)
        
    return '\n'.join(processed_blocks)

# --- 3. تصميم واجهة المستخدم ---

st.title('📊 نظام تقييم دقة التوقعات الجوية (TAF)')
st.write('قم برفع ملفات الميتار والتاف التي تحتوي على الطابع الزمني (YYYYMMDDHHMM).')

col1, col2 = st.columns(2)

with col1:
    metar_file = st.file_uploader('ملف الميتار (METAR.txt)', type=['txt'])
with col2:
    taf_file = st.file_uploader('ملف التوقعات (TAF.txt)', type=['txt'])

# --- 4. منطق التقييم والتحليل ---

if st.button('🚀 بدء التحليل الذكي والمقارنة'):
    if metar_file and taf_file:
        try:
            # قراءة النصوص من الملفات المرفوعة
            metar_raw = metar_file.getvalue().decode('utf-8')
            taf_raw = taf_file.getvalue().decode('utf-8')
            
            # معالجة ودمج الأسطر بناءً على الصيغة المطلوبة
            metar_final = process_meteorological_data(metar_raw, is_taf=False)
            taf_final = process_meteorological_data(taf_raw, is_taf=True)
            
            with st.spinner('جاري مقارنة البيانات وتحليل الدقة...'):
                
                # بناء البرومبت مع حماية الأقواس المتعرجة بمضاعفتها {{ }}
                prompt = f"""
                بصفتك خبير أرصاد جوية، قم بتقييم دقة الـ TAF مقابل الـ METAR.
                
                ملاحظة التنسيق: كل سطر يبدأ بطابع زمني رقمي YYYYMMDDHHMM.
                قواعد التحليل:
                1. حلل أول 24 ساعة فقط من فترة صلاحية كل TAF.
                2. قارن العناصر: (سرعة/اتجاة الرياح، الرؤية، السحب، والظواهر الجوية).
                3. احسب نسبة الدقة (0-100) لكل عنصر.
                4. قدم النتيجة النهائية كقائمة JSON حصراً.
                
                [البيانات المستلمة - METAR]:
                {metar_final[:8000]}
                
                [البيانات المستلمة - TAF]:
                {taf_final[:8000]}
                
                Response Format: STRICT JSON LIST ONLY.
                Example Structure:
                [[
                  {{
                    "taf_header": "202603010440 TAF...",
                    "wind_score": 90,
                    "vis_score": 85,
                    "cloud_score": 70,
                    "total_score": 82,
                    "errors": "اكتب هنا الأسباب التقنية باللغة العربية"
                  }}
                ]]
                """
                
                # استدعاء نموذج Gemini
                response = model.generate_content(prompt)
                res_text = response.text
                
                # تنظيف النص المستخرج من علامات التنسيق الخاصة بـ JSON
                if '```json' in res_text:
                    res_text = res_text.split('```json')[1].split('```')[0]
                elif '```' in res_text:
                    res_text = res_text.split('```')[1].split('```')[0]
                
                # تحويل النص إلى كائن JSON ثم إلى DataFrame
                results = json.loads(res_text.strip())
                df = pd.DataFrame(results)
                
                # عرض النتائج في جدول
                st.subheader('📈 تقرير الدقة التفصيلي')
                
                def apply_color(val):
                    if isinstance(val, (int, float)):
                        color = 'red' if val < 60 else 'orange' if val < 85 else 'green'
                        return f'color: {color}; font-weight: bold'
                    return ''

                st.dataframe(df.style.map(apply_color, subset=['total_score']), use_container_width=True)
                
                # تحليل الأخطاء للتقييمات الضعيفة
                st.divider()
                st.subheader('🔍 تحليل الإخفاقات (أقل من 60%)')
                
                low_performance = [item for item in results if item.get('total_score', 0) < 60]
                if low_performance:
                    for item in low_performance:
                        with st.expander(f"⚠️ {item.get('taf_header', 'TAF')[:50]}..."):
                            st.error(f"الدقة الكلية: {item.get('total_score')}%")
                            st.info(f"التحليل التقني: {item.get('errors')}")
                else:
                    st.success('جميع التوقعات في هذا الملف ذات دقة جيدة جداً!')
                    
        except Exception as e:
            st.error(f'حدث خطأ غير متوقع: {str(e)}')
            st.info('تأكد من أن الملفات المرفوعة تتبع الصيغة الرقمية المطلوبة.')
    else:
        st.warning('يرجى رفع ملف الميتار وملف التاف أولاً.')

st.sidebar.markdown('---')
st.sidebar.caption('إصدار v2.0 - معالج البيانات الرقمية')
