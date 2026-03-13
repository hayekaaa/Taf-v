import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# --- 1. Configuration & Security ---
st.set_page_config(page_title='TAF Quality Evaluator', layout='wide', page_icon='✈️')

# Get API Key from Secrets
api_key = st.secrets.get('GOOGLE_API_KEY', '')

if not api_key:
    st.error('Missing GOOGLE_API_KEY in Streamlit Secrets!')
else:
    genai.configure(api_key=api_key)
    # Using gemini-1.5-flash for faster analysis
    model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. Data Processing Functions ---

def clean_and_format_data(raw_text, is_taf=False):
    """
    Cleans the raw text and handles the multi-line TAF format ending with '='.
    """
    if not raw_text:
        return ""
    
    lines = raw_text.split('\n')
    processed_lines = []
    current_block = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if is_taf:
            # Check if line starts with a timestamp (12 digits)
            if re.match(r'^\d{12}', line):
                if current_block:
                    processed_lines.append(current_block)
                current_block = line
            else:
                # Append subsequent lines of the same TAF
                current_block += " " + line
            
            # If line ends with '=', finish the block
            if line.endswith('='):
                processed_lines.append(current_block)
                current_block = ""
        else:
            # For METAR, just take the line as is
            processed_lines.append(line)
            
    if current_block:
        processed_lines.append(current_block)
        
    return '\n'.join(processed_lines)

# --- 3. User Interface ---

st.title('📊 نظام تقييم جودة الـ TAF')
st.markdown("""
هذا النظام مصمم لتحليل بيانات **METAR** و **TAF** بالصيغة الزمنية الرقمية. 
سيتم تحليل أول 24 ساعة من كل TAF ومقارنتها بالواقع المرصود.
""")

col1, col2 = st.columns(2)

with col1:
    metar_file = st.file_uploader('Upload METAR File (.txt)', type=['txt'], key='metar')
with col2:
    taf_file = st.file_uploader('Upload TAF File (.txt)', type=['txt'], key='taf')

if st.button('🚀 بدء عملية التقييم الذكي'):
    if metar_file and taf_file:
        try:
            # Read and decode files
            metar_raw = metar_file.getvalue().decode('utf-8')
            taf_raw = taf_file.getvalue().decode('utf-8')
            
            # Process and Clean
            metar_clean = clean_and_format_data(metar_raw, is_taf=False)
            taf_clean = clean_and_format_data(taf_raw, is_taf=True)
            
            with st.spinner('جاري تحليل البيانات ومقارنة الجداول الزمنية...'):
                # Prepare AI Prompt
                prompt = f"""
                As a meteorological expert, evaluate the TAF accuracy against METAR observations.
                
                Data Format Note: Each line starts with a YYYYMMDDHHMM timestamp.
                Rules:
                1. Evaluate only the first 24 hours of each TAF validity period.
                2. Compare: Wind speed/direction, Visibility, Cloud cover/height, and Weather phenomena.
                3. Calculate accuracy (0-100%) for each category.
                4. Provide a total score average.
                
                Input Data:
                [METAR DATA]:
                {metar_clean[:10000]}
                
                [TAF DATA]:
                {taf_clean[:10000]}
                
                Response Format: STRICT JSON LIST ONLY.
                Example: [{"taf_header": "202603010440 TAF...", "wind_score": 90, "vis_score": 80, "cloud_score": 70, "total_score": 80, "errors": "Reasoning here"}]
                """
                
                response = model.generate_content(prompt)
                res_text = response.text
                
                # Extract JSON from potential markdown code blocks
                if '```json' in res_text:
                    res_text = res_text.split('```json')[1].split('```')[0]
                elif '```' in res_text:
                    res_text = res_text.split('```')[1].split('```')[0]
                
                results_json = json.loads(res_text.strip())
                df = pd.DataFrame(results_json)
                
                # Show Table
                st.subheader('📈 جدول دقة التوقعات')
                
                # Styling the dataframe
                def color_scores(val):
                    if isinstance(val, (int, float)):
                        color = 'red' if val < 60 else 'orange' if val < 85 else 'green'
                        return f'color: {color}; font-weight: bold'
                    return ''

                st.dataframe(df.style.applymap(color_scores, subset=['total_score']), use_container_width=True)
                
                # Error Analysis Section
                st.divider()
                st.subheader('🔍 تحليل الإخفاقات (التقييم أقل من 60%)')
                
                low_perf = [r for r in results_json if r.get('total_score', 0) < 60]
                if low_perf:
                    for item in low_perf:
                        with st.expander(f"⚠️ {item.get('taf_header', 'TAF')[:60]}..."):
                            st.error(f"**الدرجة الكلية:** {item.get('total_score')}%")
                            st.write(f"**الأخطاء المرصودة:** {item.get('errors')}")
                else:
                    st.success('ممتاز! جميع التوقعات في هذا الملف تجاوزت نسبة دقة 60%.')
                    
        except Exception as e:
            st.error(f'حدث خطأ أثناء المعالجة: {str(e)}')
            st.info('تأكد من أن ملفات النص تحتوي على الصيغة المطلوبة.')
    else:
        st.warning('يرجى رفع ملفات METAR و TAF أولاً.')

st.sidebar.markdown('---')
st.sidebar.info('ملاحظة: تأكد من أن أسماء الملفات لا تحتوي على مسافات أو رموز خاصة.')
