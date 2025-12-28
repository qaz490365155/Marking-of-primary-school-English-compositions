import streamlit as st
from openai import OpenAI
import json
import base64

# --- 页面基础配置 ---
st.set_page_config(layout="wide", page_title="英语写作智能评价 Agent (图文版)")

# --- 初始化 Session State (关键步骤) ---
# 用于在“识别”和“评分”两个步骤之间保存作文内容
if 'essay_content' not in st.session_state:
    st.session_state.essay_content = ""

# --- 侧边栏：API 配置 ---
st.sidebar.title("⚙️ API 设置")

api_key = st.sidebar.text_input("OpenAI API Key", type="password", value=st.secrets.get("OPENAI_API_KEY", ""))
base_url = st.sidebar.text_input("Base URL", value="https://api.nuwaapi.com/v1", help="代理地址")
model_name = st.sidebar.selectbox("选择模型", ["gpt-4o", "gpt-4o-mini"], index=0) # 建议使用 gpt-4o 识别手写体效果更好

# --- 核心逻辑 1: 图片转文字 (OCR) ---
def encode_image(uploaded_file):
    """将上传的图片文件转换为 Base64 字符串"""
    return base64.b64encode(uploaded_file.read()).decode('utf-8')

def recognize_text(uploaded_file, key, url, model):
    """调用 GPT-4o 视觉能力进行文字识别"""
    if not key:
        return "请先输入 API Key"
    
    client = OpenAI(api_key=key, base_url=url)
    base64_image = encode_image(uploaded_file)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please transcribe the handwritten or printed English text in this image exactly as it appears. Do not correct any errors (spelling or grammar), just transcribe what you see. Output ONLY the text."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"识别出错: {str(e)}"

# --- 核心逻辑 2: 作文评分 (Rubric) ---
SYSTEM_PROMPT = """
You are a strict English Writing Assessor. 
Evaluate the student's essay based on this RUBRIC:

1. **Structure**: Must include 3 parts: beginning, body, and ending.
2. **Content**: Must cover at least 2 kinds of clothes.
3. **Description**: Must describe clothes properly with adjectives.
4. **Spelling**: Spell the clothes words correctly.
5. **Grammar**: Use the single or plural forms correctly.

RETURN JSON ONLY. Format:
{
    "score": (0-100),
    "evaluation": {
        "has_3_parts": boolean,
        "has_2_clothes": boolean,
        "has_adjectives": boolean,
        "spelling_ok": boolean,
        "plural_ok": boolean
    },
    "analysis_comment": "Brief comment in Chinese focusing on the rubric.",
    "errors": [
        {"original": "word", "correction": "correction", "reason": "reason in Chinese"}
    ],
    "polished_version": "Full text polished."
}
"""

def get_assessment(text, key, url, model):
    if not key:
        return None, "请先输入 API Key"
    
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
st.title("📸 英语作文智能评价 (支持图片识别)")
st.markdown("上传手写或打印的作文图片，AI 将自动识别文字并根据标准打分。")

col1, col2 = st.columns([1, 1])

# --- 左侧：输入与识别区 ---
with col1:
    st.subheader("1. 上传图片 或 直接输入")
    
    # 图片上传组件
    uploaded_img = st.file_uploader("拖入或选择图片 (JPG/PNG)", type=["jpg", "jpeg", "png"])
    
    # 如果上传了图片，显示识别按钮
    if uploaded_img:
        st.image(uploaded_img, caption="预览", use_container_width=True)
        if st.button("👁️ 开始识别文字 (OCR)", type="primary"):
            with st.spinner("AI 正在努力辨认字迹..."):
                # 重置文件指针位置，防止读取错误
                uploaded_img.seek(0)
                ocr_result = recognize_text(uploaded_img, api_key, base_url, model_name)
                # 将识别结果存入 session_state
                st.session_state.essay_content = ocr_result
                st.rerun() # 刷新页面以填入下方文本框

    # 文本编辑区 (内容绑定到 session_state)
    st.markdown("⬇️ **确认或编辑作文内容**")
    user_input = st.text_area(
        "作文内容", 
        value=st.session_state.essay_content, 
        height=200, 
        placeholder="可以直接打字，也可以上传图片自动生成...",
        key="text_input_area" 
    )
    
    # 监听文本框变化，手动修改时同步 Session State
    if user_input != st.session_state.essay_content:
        st.session_state.essay_content = user_input

    # 评分按钮
    assess_btn = st.button("📝 开始评分 (Analyze)", type="primary", use_container_width=True)

# --- 右侧：结果展示区 ---
with col2:
    if assess_btn and user_input:
        with st.spinner("AI 正在根据 5 项标准打分..."):
            result, error_msg = get_assessment(user_input, api_key, base_url, model_name)
        
        if error_msg:
            st.error(f"出错啦: {error_msg}")
        elif result:
            # 1. 分数展示
            score = result.get('score', 0)
            color = "#28a745" if score >= 80 else "#ffc107" if score >= 60 else "#dc3545"
            st.markdown(f"""
            <div style="text-align: center; border: 2px solid {color}; padding: 10px; border-radius: 10px; margin-bottom: 20px;">
                <h2 style="color: {color}; margin:0;">得分: {score}</h2>
            </div>
            """, unsafe_allow_html=True)
            
            # 2. 核心指标 Checkbox
            st.markdown("#### 🎯 核心指标检查")
            eval_data = result.get('evaluation', {})
            c1, c2 = st.columns(2)
            c1.checkbox("结构完整 (三段式)", value=eval_data.get('has_3_parts'), disabled=True)
            c1.checkbox("内容达标 (2种衣服)", value=eval_data.get('has_2_clothes'), disabled=True)
            c1.checkbox("描写达标 (有形容词)", value=eval_data.get('has_adjectives'), disabled=True)
            c2.checkbox("拼写正确", value=eval_data.get('spelling_ok'), disabled=True)
            c2.checkbox("单复数正确", value=eval_data.get('plural_ok'), disabled=True)
            
            st.info(f"💡 **评语**: {result.get('analysis_comment')}")

            # 3. 纠错与润色 Tab
            t1, t2 = st.tabs(["❌ 纠错列表", "✨ 润色范文"])
            with t1:
                errors = result.get('errors', [])
                if not errors:
                    st.caption("没有发现明显错误。")
                for e in errors:
                    st.error(f"**{e['original']}** ➔ **{e['correction']}**")
                    st.caption(f"原因: {e['reason']}")
            with t2:
                st.write(result.get('polished_version'))
