import streamlit as st
import uuid
import json
import os
from datetime import datetime
from openai import OpenAI

# ===================== 全局配置 CSS美化 =====================
st.set_page_config(
    page_title="AI人格化交互辅助决策实验",
    layout="wide",
    initial_sidebar_state="collapsed"
)

custom_css = """
<style>
.main {background-color:#f7f9fc;}
.block-container {padding-top:2rem;padding-left:3rem;padding-right:3rem;}
.good-card{background:#fff;border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.08);height:260px;}
.info-box{background:#e8f0fe;padding:12px 16px;border-radius:8px;border-left:4px #2b7bba solid;}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ============ 【三套人格Prompt，核心！】 ============
PROMPT_DICT = {
    "理性分析型": """
你是理性分析型AI助手，说话客观、数据导向、简洁克制，不带情感。
【硬性强制约束】你只能使用下方给定商品数据，**禁止编造任何商品参数、价格**。
商品数据：
无线降噪耳机｜499元｜续航30h、主动降噪｜评分4.6
便携充电宝｜129元｜20000mAh PD快充｜评分4.5
机械键盘｜279元｜青轴 RGB背光｜评分4.3
蓝牙音箱｜199元｜IPX5防水｜评分4.4
平板支架｜69元｜铝合金可折叠｜评分4.7
回答风格：只罗列客观数据、对比参数，不用口语化语气，不使用表情，不做情绪化安慰。
""",
    "谨慎建议型": """
你是谨慎建议型AI助手，给出建议同时强调风险与局限性，带有免责口吻。
【硬性强制约束】你只能使用下方给定商品数据，**禁止编造任何商品参数、价格**。
商品数据：
无线降噪耳机｜499元｜续航30h、主动降噪｜评分4.6
便携充电宝｜129元｜20000mAh PD快充｜评分4.5
机械键盘｜279元｜青轴 RGB背光｜评分4.3
蓝牙音箱｜199元｜IPX5防水｜评分4.4
平板支架｜69元｜铝合金可折叠｜评分4.7
回答风格：给出参考建议，但要加上类似“仅供参考，请你自行权衡”“不能完全保证适配你的需求”这类风险提示。
""",
    "友好陪伴型": """
你是友好陪伴型AI助手，语气亲切口语化，温暖，适当使用表情符号。
【硬性强制约束】你只能使用下方给定商品数据，**禁止编造任何商品参数、价格**。
商品数据：
无线降噪耳机｜499元｜续航30h、主动降噪｜评分4.6
便携充电宝｜129元｜20000mAh PD快充｜评分4.5
机械键盘｜279元｜青轴 RGB背光｜评分4.3
蓝牙音箱｜199元｜IPX5防水｜评分4.4
平板支架｜69元｜铝合金可折叠｜评分4.7
回答风格：语气轻松友好，可以用😊✨这类简单表情，多共情用户感受。
"""
}

# ========= API配置 DeepSeek；换成通义千问只改base_url和model =========
client = OpenAI(
    api_key="sk-156ccd1b5a504068a60cb55f8e07ed9c",
    base_url="https://api.deepseek.com"
)

# ========= SessionState初始化 =========
if "user_unique_id" not in st.session_state:
    st.session_state.user_unique_id = str(uuid.uuid4())
if "start_timestamp" not in st.session_state:
    st.session_state.start_timestamp = None
if "click_record" not in st.session_state:
    st.session_state.click_record = []
if "selected_style" not in st.session_state:
    st.session_state.selected_style = "理性分析型"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

mock_top5_goods = [
    {"id":1,"name":"无线降噪耳机","price":499,"param":"续航30h、主动降噪","score":4.6},
    {"id":2,"name":"便携充电宝","price":129,"param":"20000mAh PD快充","score":4.5},
    {"id":3,"name":"机械键盘","price":279,"param":"青轴 RGB背光","score":4.3},
    {"id":4,"name":"蓝牙音箱","price":199,"param":"IPX5防水","score":4.4},
    {"id":5,"name":"平板支架","price":69,"param":"铝合金可折叠","score":4.7},
]
style_list = ["理性分析型","谨慎建议型","友好陪伴型"]

# ================= 页面UI =================
st.markdown("# 🧪 AI人格化交互辅助决策实验原型")
st.markdown(f'<div class="info-box">🔑 用户唯一实验ID：<code>{st.session_state.user_unique_id}</code></div>', unsafe_allow_html=True)
st.divider()

st.subheader("📌 步骤1：选择AI交互风格")
choose_style = st.radio("切换AI助手人格风格", style_list, horizontal=True)

# 切换风格时：重置聊天记录！不同实验组对话隔离
if choose_style != st.session_state.selected_style:
    st.session_state.selected_style = choose_style
    st.session_state.start_timestamp = datetime.now()
    st.session_state.chat_history = []
    st.success(f"✅已切换：【{choose_style}】，计时已开始，对话已清空！")

st.divider()

st.subheader("💬 步骤2：AI对话窗口")
# 渲染聊天历史（只展示user/assistant，system不展示）
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("在这里输入你的问题，和AI对话")
if user_input:
    st.session_state.chat_history.append({"role":"user","content":user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # ===== 核心调用：把对应风格的System Prompt放在消息列表头部 =====
    messages_api = [{"role":"system","content":PROMPT_DICT[st.session_state.selected_style]}]
    messages_api.extend(st.session_state.chat_history)

    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model="deepseek-flash",
            messages=messages_api,
            stream=True,
            temperature=0.3  # 温度调低，减少模型自由发挥，保证事实稳定
        )
        ai_response = st.write_stream(stream)
    st.session_state.chat_history.append({"role":"assistant","content":ai_response})

st.divider()

# 商品卡片
st.subheader("🛒 步骤3：AI推荐 Top‑5商品（底层事实固定不变）")
col_container = st.columns(5)
for idx, item in enumerate(mock_top5_goods):
    with col_container[idx]:
        st.markdown('<div class="good-card">',unsafe_allow_html=True)
        st.markdown(f"**{item['name']}**")
        st.markdown(f"💰 价格：**{item['price']} 元**")
        st.markdown(f"📋 参数：{item['param']}")
        st.markdown(f"⭐ 评分：{item['score']}")
        st.write("")
        if st.button("✅选择此商品", key=f"goods_btn_{item['id']}"):
            end_time = datetime.now()
            delta_sec = (end_time - st.session_state.start_timestamp).total_seconds()
            record = {
                "user_id": st.session_state.user_unique_id,
                "ai_style": st.session_state.selected_style,
                "selected_goods_id": item["id"],
                "selected_goods_name": item["name"],
                "start_time": str(st.session_state.start_timestamp),
                "end_time": str(end_time),
                "decision_cost_second": round(delta_sec,2)
            }
            st.session_state.click_record.append(record)
            st.toast(f"已选择：{item['name']}，耗时 {delta_sec:.2f} 秒")
        st.markdown("</div>",unsafe_allow_html=True)

st.divider()
st.subheader("📊 后台埋点行为日志（调试）")
st.dataframe(st.session_state.click_record, use_container_width=True)
if st.button("💾【调试】导出埋点JSON"):
    with open("behavior_log.json","w",encoding="utf‑8") as f:
        json.dump(st.session_state.click_record, f, ensure_ascii=False, indent=2)
    st.success("behavior_log.json已保存")

st.divider()
st.subheader("📝 步骤4：完成实验填写问卷")
questionnaire_base_url = "https://v.wjx.cn/vm/YDNnB9I.aspx#"
full_question_url = questionnaire_base_url + st.session_state.user_unique_id
st.markdown(f"> 携带实验ID问卷链接原型：`{full_question_url}`")
st.link_button("👉跳转填写实验问卷", url=full_question_url, type="primary")
