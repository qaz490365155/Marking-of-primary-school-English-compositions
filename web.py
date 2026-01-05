import streamlit as st
from openai import OpenAI
import json
import base64

# --- 页面基础配置 ---
st.set_page_config(layout="wide", page_title="英语写作智能评价 Agent")

# --- 初始化 Session State ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'essay_content' not in st.session_state:
    st.session_state.essay_content = ""

# --- 安全与身份验证逻辑 ---
HIDDEN_KEY = st.secrets.get("OPENAI_API_KEY", "")
HIDDEN_BASE_URL = st.secrets.get("BASE_URL", "https://api.nuwaapi.com/v1")
VALID_PASSWORD = st.secrets.get("APP_PASSWORD", "123")

if not st.session_state.authenticated:
    st.sidebar.title("🔐 访问验证")
    input_password = st.sidebar.text_input("请输入访问码", type="password")
    login_btn = st.sidebar.button("确认进入", use_container_width=True)
    if login_btn or (input_password == VALID_PASSWORD and input_password != ""):
        if input_password == VALID_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.sidebar.error("密码错误")
    st.title("👋 欢迎使用英语写作助手")
    st.warning("🔒 请输入访问码开始使用。")
    st.stop()

# --- 验证通过界面 ---
st.sidebar.success("✅ 验证成功")
if st.sidebar.button("退出登录"):
    st.session_state.authenticated = False
    st.rerun()

st.sidebar.divider()
st.sidebar.title("⚙️ 模型设置")
api_key = st.sidebar.text_input("API Key", type="password", value=HIDDEN_KEY)
base_url = st.sidebar.text_input("Base URL", value=HIDDEN_BASE_URL)
model_name = st.sidebar.selectbox("选择模型", ["gpt-4o", "gpt-4o-mini"], index=0)

# --- 核心逻辑函数 ---
def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.read()).decode('utf-8')

def recognize_text(uploaded_file, key, url, model):
    client = OpenAI(api_key=key, base_url=url)
    base64_image = encode_image(uploaded_file)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Please transcribe the English text in this image exactly. Do not correct errors. Output ONLY text."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }],
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"识别出错: {str(e)}"

# --- 优化后的 Prompt (5分制) ---
SYSTEM_PROMPT = """
You are a professional primary school English teacher. 
Evaluate the essay based on exactly 5 points. Each point is worth 1 mark. Total score is 5.

RUBRIC:
1. [Structure]: Score 1 if it includes beginning, body, and ending. Otherwise 0.
2. [Content]: Score 1 if it covers at least 2 kinds of clothes. Otherwise 0.
3. [Adjectives]: Score 1 if clothes are described properly with adjectives. Otherwise 0.
4. [Spelling]: Score 1 if all clothes words are spelled correctly. Otherwise 0.
5. [Grammar]: Score 1 if single/plural forms of clothes are used correctly. Otherwise 0.

RETURN JSON ONLY:
{
    "total_score": (int 0-5),
    "evaluation": {
        "has_3_parts": boolean,
        "has_2_clothes": boolean,
        "has_adjectives": boolean,
        "spelling_ok": boolean,
        "plural_ok": boolean
    },
    "analysis_comment": "Chinese comment for the student.",
    "errors": [
        {"original": "...", "correction": "...", "reason": "Chinese reason"}
    ],
    "polished_version": "Full polished text."
}
"""

def get_assessment(text, key, url, model):
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

# --- 主界面 ---
st.title("📝 英语写作智能评价系统 (5分制)")
st.markdown("AI 将根据：结构、内容、形容词、拼写、单复数 5 项标准进行打分。")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 提交作文")
    uploaded_img = st.file_uploader("上传手写图片", type=["jpg", "jpeg", "png"])
    if uploaded_img:
        st.image(uploaded_img, use_container_width=True)
        if st.button("👁️ 自动识别文字", type="primary"):
            with st.spinner("辨认中..."):
                uploaded_img.seek(0)
                ocr_result = recognize_text(uploaded_img, api_key, base_url, model_name)
                st.session_state.essay_content = ocr_result
                st.rerun()

    user_input = st.text_area("作文内容确认/编辑", value=st.session_state.essay_content, height=200)
    if user_input != st.session_state.essay_content:
        st.session_state.essay_content = user_input

    assess_btn = st.button("🚀 开始智能批改", type="primary", use_container_width=True)

with col2:
    if assess_btn and user_input:
        with st.spinner("批改中..."):
            result, error_msg = get_assessment(user_input, api_key, base_url, model_name)
        
        if error_msg:
            st.error(f"失败: {error_msg}")
        elif result:
            # 分数展示：星级显示
            score = result.get('total_score', 0)
            st.markdown(f"""
            <div style="text-align: center; background-color: #f0f2f6; padding: 20px; border-radius: 15px;">
                <h1 style="color: #FF4B4B; margin: 0;">{score} / 5 分</h1>
                <p style="font-size: 24px;">{'⭐' * score}{'☆' * (5-score)}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("#### 🎯 标准检查详情")
            eval_data = result.get('evaluation', {})
            # 使用更直观的标签
            c1, c2 = st.columns(2)
            c1.write(f"{'✅' if eval_data.get('has_3_parts') else '❌'} 三段式结构")
            c1.write(f"{'✅' if eval_data.get('has_2_clothes') else '❌'} 包含2种衣服")
            c1.write(f"{'✅' if eval_data.get('has_adjectives') else '❌'} 形容词描写")
            c2.write(f"{'✅' if eval_data.get('spelling_ok') else '❌'} 单词拼写正确")
            c2.write(f"{'✅' if eval_data.get('plural_ok') else '❌'} 单复数正确")
            
            st.info(f"💡 **老师评语**: {result.get('analysis_comment')}")
            
            tab1, tab2 = st.tabs(["❌ 纠错建议", "✨ 优秀范文"])
            with tab1:
                errors = result.get('errors', [])
                if not errors: st.success("太棒了！没有发现明显的语言错误。")
                for e in errors:
                    st.error(f"**{e['original']}** ➔ **{e['correction']}**")
                    st.caption(f"原因: {e['reason']}")
            with tab2:
                st.write(result.get('polished_version'))

