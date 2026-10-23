import streamlit as st
import json
import time
import uuid
import random
from datetime import datetime
from openai import OpenAI
import urllib.request          # 新增：用于把埋点上报到云端数据库

# ===================== API配置区 =====================
API_KEY = "sk-05a5a11ed9da4e3ea16c17b0ed6bfc01"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-flash"

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

# ===================== 埋点数据库配置（Supabase）=====================
# 说明：publishable key 是公开性质的低权限密钥，只允许【插入】、不允许【读取】，
#      因此写进代码是安全的。切勿把 sb_secret_ 开头的 secret key 放在这里。
SUPABASE_URL = "https://aiznqqcispcntgouzhct.supabase.co"
SUPABASE_KEY = "sb_publishable_xfm0TvH5W5-Qq5ZvvmkDVA_8lTfgWO9"

# 表 click_log 必须具备这些列，缺任何一列都会导致写入失败：
# id, user_id, ai_style, question_count, product_id, product_name,
# price_usd, cbf_score, decision_cost_sec, select_time, created_at


def log_to_supabase(rec: dict) -> bool:
    """把一条点击记录追加到云端表 click_log。

    设计要点：任何失败都静默吞掉，绝不让被试看到报错、也绝不中断实验流程。
    返回 True/False 仅供调试。
    """
    try:
        req = urllib.request.Request(
            SUPABASE_URL + "/rest/v1/click_log",
            data=json.dumps(rec, ensure_ascii=False).encode("utf-8"),
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": "Bearer " + SUPABASE_KEY,
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


# ===================== 实验任务情境（三组完全一致）=====================
# 说明：这段情境文本是「前置条件」而非自变量，三种风格下必须一字不差，
#      不得因为风格不同而改动措辞，否则会引入第四个混淆变量。
SCENARIO_TITLE = "🎯 请您完成的任务"

SCENARIO_TEXT = """
**请您先代入下面的情境：**

> 您是一位小学一年级孩子的家长，孩子的生日快到了，您想送他一份
> **既有意义、又能真正用得上**的礼物，预算大约在 **60 美元以内**。
>
> 您平时工作比较忙，没有太多时间对比各种商品，于是打开了这个
> AI 购物助手，希望它帮您从推荐的商品里挑出最合适的一件。

**接下来请您：**

1. 浏览下方推荐的五件商品，想一想您最关心的是哪些方面；
2. 向右侧的 AI 助手咨询您在意的问题（可以问价格、适用年龄、
   耐用程度、是否适合一年级孩子等）；
3. 在您认为最合适的一件商品上点击 **「✅选择此商品」**；
4. 完成选择后，点击页面底部的按钮进入问卷填写。
"""

SCENARIO_TIPS = (
    "💡 如果您不知道问什么，可以试试："
    "「这五件里哪件适合一年级孩子？」　"
    "「60 美元以内哪件更划算？」　"
    "「买之前我需要注意什么？」"
)

# ===================== 页面基础配置 =====================
st.set_page_config(
    page_title="AI人格化商品推荐实验",
    layout="wide",
    initial_sidebar_state="collapsed"
)

custom_css = """
<style>
.main {background-color:#f7f9fc;}
.block-container {
    padding-top: 1rem;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
}
.good-card{
    background:#ffffff;
    border-radius:12px;
    padding:14px;
    box-shadow:0 2px 10px rgba(0,0,0,0.08);
    min-height:auto !important;
}
.info-box{background:#e8f0fe;padding:12px 16px;border-radius:8px;border-left:4px #2b7bba solid;}
.consent-box{background:#ffffff;padding:2rem;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.07);max-width:720px;margin:0 auto;}
/* 卡片内expander去除边框，适配卡片样式 */
[data-testid="stExpander"]{
    border:none !important;
    box-shadow:none !important;
}
[data-testid="stExpander"] details summary p{
    font-size:14px;
    color:#2b7bba;
}
/* 任务情境：美化 Markdown 引用块（Streamlit 原生解析，不能用 div 包 Markdown） */
[data-testid="stMarkdownContainer"] blockquote{
    background:#f5f9ff;
    border-left:4px solid #2b7bba;
    border-radius:8px;
    padding:14px 20px;
    margin:10px 0 16px 0;
    line-height:1.95;
    font-size:15px;
    color:#33465c;
}
[data-testid="stMarkdownContainer"] blockquote p{
    margin:4px 0;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ===================== 会话状态初始化 =====================
if "user_unique_id" not in st.session_state:
    st.session_state.user_unique_id = str(uuid.uuid4())
if "agreed" not in st.session_state:
    st.session_state.agreed = False
if "selected_style" not in st.session_state:
    st.session_state.selected_style = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "click_record" not in st.session_state:
    st.session_state.click_record = []
if "start_timestamp" not in st.session_state:
    st.session_state.start_timestamp = None
if "question_count" not in st.session_state:
    st.session_state.question_count = 0   # 记录用户提问条数

style_pool = ["理性分析型", "谨慎建议型", "友好陪伴型"]

# ===================== 知情同意页面 =====================
if not st.session_state.agreed:
    st.markdown('<div class="consent-box">', unsafe_allow_html=True)
    st.header("您好！欢迎参与本次AI商品推荐助手交互体验学术实验")
    st.markdown("""
本实验包含原型交互与问卷填写两个部分，全程约2‑3分钟。
您将体验一种人格风格的AI商品推荐助手，完成交互后填写评价量表。

**所有数据匿名、仅用于课题研究，您可以随时退出。**

# 知情同意书
您好！诚邀您参与本次人机交互课题实验。
1. **实验内容**：您将体验AI商品推荐原型系统，完成交互评价，全程约2‑3分钟。
2. **风险说明**：本实验仅为线上原型演示，无任何金钱交易，不会带来生理、心理伤害。
3. **数据保密**：收集的全部信息匿名处理，仅用于课程课题分析，不会对外泄露。
4. **自愿原则**：参与完全自愿，您可以随时退出实验，无需理由。
""")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅同意，继续实验", use_container_width=True):
            # 只分配风格，不启动计时；计时等到第一条AI提问才触发
            st.session_state.selected_style = random.choice(style_pool)
            st.session_state.chat_history = []
            st.session_state.click_record = []
            st.session_state.start_timestamp = None
            st.session_state.question_count = 0
            st.session_state.agreed = True
            st.rerun()
    with col2:
        st.button("❌不同意，退出实验", use_container_width=True, disabled=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ===================== 读取JSON商品数据集 =====================
@st.cache_data
def load_product_json():
    """读取top5_recommendations_zh.json，提取products数组"""
    with open("top5_recommendations_zh.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, str):
        data = json.loads(data)
    if isinstance(data, dict) and "products" in data:
        return data["products"]
    return data

product_list = load_product_json()

# 商品图片映射（按product_id绑定，放在循环外部）
image_map = {
    "P001-B01DTIFMSO": "P001-B01DTIFMSO.jpg",
    "P002-B005Q16MDW": "P002-B005Q16MDW.jpg",
    "P003-B01FLNRQYS": "P003-B01FLNRQYS.jpg",
    "P004-B0792T5T77": "P004-B0792T5T77.jpg",
    "P005-B01ECLZC1O": "P005-B01ECLZC1O.jpg",
}

# ===================== 拼接商品文本，供给AI Prompt =====================
def get_products_text():
    lines = []
    for p in product_list:
        if not isinstance(p, dict):
            continue
        line = (f"【{p['product_id']}】{p['name_zh']} | 价格${p['price_usd']} | "
                f"类目:{p['category_family_zh']} | 匹配分数cbf_score:{p['cbf_score']} | "
                f"卖点：{p['features_text_zh']}")
        lines.append(line)
    return "\n".join(lines)

product_full_text = get_products_text()

# ===================== AI三种人格Prompt =====================
style_prompt_dict = {
    "理性分析型": """
你是理性分析型AI助手，客观数据导向，不带情感。
只能使用下面提供的5件商品，**禁止编造任何商品信息**。
输出侧重：价格、类目、cbf匹配分数、商品卖点对比，简洁客观。
""",
    "谨慎建议型": """
你是谨慎建议型AI助手，给出建议同时附带风险提示。
只能使用下面提供的5件商品，禁止编造商品。
输出风格：给出参考，补充“仅供参考，请自行权衡需求”之类提示。
""",
    "友好陪伴型": """
你是友好陪伴型AI助手，语气亲切口语化，适当简单表情。
只能使用下面提供的5件商品，禁止编造商品。站在用户角度共情。
"""
}

# ===================== UI页面 =====================
st.markdown("# 🧪 AI人格化商品推荐实验")
st.markdown(f'<div class="info-box">🔑 用户实验ID：<code>{st.session_state.user_unique_id}</code></div>', unsafe_allow_html=True)
st.divider()

# 展示当前随机分配到的AI风格
st.subheader("📌 当前AI助手交互风格")
st.info(f"本次为您随机分配：**{st.session_state.selected_style}**，本实验不可切换风格。")
st.divider()

# ========== 任务情境【三种风格完全一致】 ==========
st.subheader(SCENARIO_TITLE)
st.markdown(SCENARIO_TEXT)
st.caption(SCENARIO_TIPS)
st.divider()

# ========== 商品区域【页面上方】 ==========
st.subheader("🛒 推荐Top‑5商品")
for i in range(0, len(product_list),5):
    cols = st.columns(5)
    for j in range(5):
        idx = i + j
        if idx >= len(product_list):
            break
        item = product_list[idx]
        with cols[j]:
            st.markdown('<div class="good-card">',unsafe_allow_html=True)
            pid = item.get("product_id")
            # 卡片顶部加载商品图片
            if pid in image_map:
                st.image(image_map[pid], use_container_width=True)

            st.markdown(f"**{item['name_zh']}**")
            st.markdown(f"💰 价格：**${item['price_usd']}** ｜档位：{item['price_band_zh']}")
            st.markdown(f"📂类目：{item['category_family_zh']}")
            st.markdown(f"⭐匹配分数(cbf_score)：{item['cbf_score']}")
            # 卖点折叠展开
            with st.expander("📝 查看完整卖点"):
                st.write(item["features_text_zh"])
            st.markdown(f"🔗[亚马逊商品链接]({item['product_url']})")

            if st.button("✅选择此商品", key=f"sel_{item['product_id']}"):
                # 只有点击选择商品，才生成埋点记录；不选商品不会产生埋点
                end_time = datetime.now()
                # 保护：防止用户还没对话直接点选商品
                if st.session_state.start_timestamp is not None:
                    delta = (end_time - st.session_state.start_timestamp).total_seconds()
                else:
                    delta = None
                rec = {
                    "user_id": st.session_state.user_unique_id,
                    "ai_style": st.session_state.selected_style,
                    "question_count": st.session_state.question_count, # 记录当前已经提问的总条数
                    "product_id": item["product_id"],
                    "product_name": item["name_zh"],
                    "price_usd": item["price_usd"],
                    "cbf_score": item["cbf_score"],
                    "decision_cost_sec": round(delta,2) if delta is not None else None,
                    "select_time": end_time.strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.click_record.append(rec)
                log_to_supabase(rec)      # 新增：同步写入云端总表（失败也不影响流程）
                st.toast(f"已选择商品，决策耗时 {delta:.2f} 秒" if delta is not None else "已选择商品，尚未开始AI对话")
            st.markdown("</div>",unsafe_allow_html=True)


st.divider()

# ========== AI对话窗口【移动到页面下端】 ==========
st.subheader("💬 AI对话窗口")
# 渲染历史聊天记录
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("输入你的选购问题，和AI对话")
if user_input:
    # 用户发出第一条问题，才开启计时
    if st.session_state.start_timestamp is None:
        st.session_state.start_timestamp = datetime.now()

    # 用户提问计数+1
    st.session_state.question_count += 1

    st.session_state.chat_history.append({"role":"user","content":user_input})
    with st.chat_message("user"):
        st.write(user_input)

    sys_prompt = style_prompt_dict[st.session_state.selected_style]

    # 真实API调用
    messages_api = [
        {"role":"system", "content": sys_prompt + "\n商品库:\n" + product_full_text[:1400]}
    ]
    messages_api.extend(st.session_state.chat_history)

    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages_api,
            stream=True,
            temperature=0.3
        )
        ai_response = st.write_stream(stream)
    st.session_state.chat_history.append({"role":"assistant","content":ai_response})


st.divider()

# 埋点已改为实时写入云端数据库（Supabase click_log 表），被试端不再展示也不提供导出：
# 1) 展示埋点会让被试意识到自己被观察，属于实验设计泄露，会污染行为数据；
# 2) 原来的本地导出写到服务器容器里，多用户相互覆盖且重启即丢失。
# 数据请在 Supabase 后台 Table Editor → click_log → Export 导出。

st.divider()

# 问卷跳转，问卷星自定义参数 userid、aistyle
st.subheader("📝 步骤4：完成实验填写问卷")
uid = st.session_state.user_unique_id
style = st.session_state.selected_style
questionnaire_base_url = "https://v.wjx.cn/vm/eWrccpZ.aspx#"
full_url = f"{questionnaire_base_url}?userid={uid}&aistyle={style}"
st.markdown(f"> 携带ID问卷链接：`{full_url}`")
st.link_button("👉跳转填写实验问卷", url=full_url, type="primary")
