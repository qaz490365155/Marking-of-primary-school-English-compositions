import streamlit as st
from openai import OpenAI
import json
import base64

# --- 页面基础配置 ---
st.set_page_config(layout="wide", page_title="英语写作智能评价 Agent (图文版)")

# --- 安全与身份验证逻辑 ---
# 1. 优先从 Streamlit Secrets 读取 Key 和密码，如果没有则留空
# 这样做即便源码公开在 GitHub，别人也看不到你的 Key
HIDDEN_KEY = st.secrets.get("OPENAI_API_KEY", "")
HIDDEN_BASE_URL = st.secrets.get("BASE_URL", "https://api.openai.com/v1")
# 你可以在 Secrets 里设置一个 APP_PASSWORD，如果不设置，默认密码为 "English666"
VALID_PASSWORD = st.secrets.get("APP_PASSWORD", "English666")

# 2. 侧边栏验证界面
st.sidebar.title("🔐 访问验证")
input_password = st.sidebar.text_input("请输入老师提供的访问码", type="password")

# 如果密码不匹配，阻断后续逻辑执行
if input_password != VALID_PASSWORD:
    st.title("👋 欢迎使用英语写作助手")
    st.warning("🔒 这是一个受保护的资源，请输入正确的访问码开始使用。")
    st.info("💡 提示：访问码由你的指导老师提供。")
    st.stop()  # 停止运行后续代码

# --- 验证通过后显示功能界面 ---
st.sidebar.success("验证成功，欢迎使用！")
st.sidebar.divider()
st.sidebar.title("⚙️ 模型设置")
# 默认使用 Secrets 中的配置，同时也允许在界面临时修改
api_key = st.sidebar.text_input("OpenAI API Key", type="password", value=HIDDEN_KEY)
base_url = st.sidebar.text_input("Base URL", value=HIDDEN_BASE_URL)
model_name = st.sidebar.selectbox("选择模型", ["gpt-4o", "gpt-4o-mini"], index=1) # 默认选 mini 更省钱

# --- 初始化 Session State ---
if 'essay_content' not in st.session_state:
    st.session_state.essay_content = ""

# --- 核心逻辑 1: 图片转文字 (OCR) ---
def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.read()).decode('utf-8')

def recognize_text(uploaded_file, key, url, model):
    if not key: return "未配置 API Key"
    client = OpenAI(api_key=key, base_url=url)
    base64_image = encode_image(uploaded_file)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Please transcribe the handwritten or printed English text in this image exactly as it appears. Output ONLY the text."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }],
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"识别出错: {str(e)}"

# --- 核心逻辑 2: 作文评分 (Rubric) ---
SYSTEM_PROMPT = """
You are a strict English Writing Assessor. 
Evaluate the student's essay based on this RUBRIC:
1. **Structure**: Must include 3 parts (beginning, body, ending).
2. **Content**: Must cover at least 2 kinds of clothes.
3. **Description**: Must use adjectives properly.
4. **Spelling**: Correct spelling of clothes.
5. **Grammar**: Correct single/plural forms.

RETURN JSON ONLY.
"""

def get_assessment(text, key, url, model):
    if not key: return None, "未配置 API Key"
    client = OpenAI(api_key=key, base_url=url)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content), None
    except Exception as e:
        return None, str(e)

# --- 主界面 UI ---
st.title("📝 英语作文智能评价系统")
st.markdown("请上传手写作文照片，AI 会自动识别并根据 5 项标准给出反馈。")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 提交作文")
    uploaded_img = st.file_uploader("拖入图片 (JPG/PNG)", type=["jpg", "jpeg", "png"])
    
    if uploaded_img:
        st.image(uploaded_img, caption="预览", use_container_width=True)
        if st.button("👁️ 自动识别文字", type="primary"):
            with st.spinner("正在辨认字迹..."):
                uploaded_img.seek(0)
                ocr_result = recognize_text(uploaded_img, api_key, base_url, model_name)
                st.session_state.essay_content = ocr_result
                st.rerun()

    user_input = st.text_area("作文内容确认", value=st.session_state.essay_content, height=200)
    if user_input != st.session_state.essay_content:
        st.session_state.essay_content = user_input

    assess_btn = st.button("🚀 开始智能批改", type="primary", use_container_width=True)

with col2:
    if assess_btn and user_input:
        with st.spinner("AI 批改中..."):
            result, error_msg = get_assessment(user_input, api_key, base_url, model_name)
        
        if error_msg:
            st.error(f"评分失败: {error_msg}")
        elif result:
            score = result.get('score', 0)
            st.markdown(f"<h2 style='text-align:center; color:#28a745;'>得分: {score}</h2>", unsafe_allow_html=True)
            
            st.markdown("#### 🎯 核心标准检查")
            eval_data = result.get('evaluation', {})
            c1, c2 = st.columns(2)
            c1.checkbox("三段式结构", value=eval_data.get('has_3_parts'), disabled=True)
            c1.checkbox("包含2种衣服", value=eval_data.get('has_2_clothes'), disabled=True)
            c2.checkbox("形容词描写", value=eval_data.get('has_adjectives'), disabled=True)
            c2.checkbox("拼写与单复数", value=eval_data.get('spelling_ok') and eval_data.get('plural_ok'), disabled=True)
            
            st.info(f"💡 **总评**: {result.get('analysis_comment')}")
            
            tab1, tab2 = st.tabs(["❌ 纠错", "✨ 润色"])
            with tab1:
                for e in result.get('errors', []):
                    st.error(f"{e['original']} -> {e['correction']} ({e['reason']})")
            with tab2:
                st.write(result.get('polished_version'))
