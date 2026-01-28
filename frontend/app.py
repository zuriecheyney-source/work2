#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit 前端应用

提供医疗分诊系统的用户界面:
1. 任务提交 → 获取 Task ID
2. 状态轮询 → 实时展示进度
3. Agent 中间步骤可视化
4. 人工审批交互
5. 最终结果展示

运行方式:
    streamlit run frontend/app.py
"""

import time
import requests
import streamlit as st
from datetime import datetime
import json
import os
import uuid

# ===== 配置 =====

# 后端 API 地址
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

import streamlit.components.v1 as components

# 页面配置
st.set_page_config(
    page_title="智能医疗分诊助手",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== 样式 =====

# ===== 样式 (Pure CSS Purple Garden) =====

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Nunito', sans-serif;
        color: #5b4a7a;
    }

    .stApp {
        background: linear-gradient(180deg, #fdfaff 0%, #f3ebff 100%);
        background-attachment: fixed;
    }

    /* --- 枫叶飘落 (Pure CSS) --- */
    .leaf-container {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 1;
        overflow: hidden;
    }

    .leaf {
        position: absolute;
        top: -10%;
        font-size: 2rem;
        opacity: 0.6;
        animation: leaf-fall 12s linear infinite;
        color: #d8b4fe;
    }

    @keyframes leaf-fall {
        0% { top: -10%; transform: translateX(0) rotate(0); }
        100% { top: 110%; transform: translateX(100px) rotate(360deg); }
    }

    /* --- 底部追逐动效 (Pure CSS) --- */
    .garden-bottom {
        position: fixed;
        bottom: 20px;
        left: 20px;
        width: 250px;
        height: 120px;
        pointer-events: none;
        z-index: 9999;
    }

    .chase-butterfly {
        position: absolute;
        font-size: 2.22rem;
        animation: bfly-flight 8s infinite ease-in-out;
    }

    .chase-dog {
        position: absolute;
        font-size: 4.22rem;
        animation: dog-follow 8s infinite ease-in-out;
    }

    @keyframes bfly-flight {
        0%, 100% { transform: translate(0, 0) rotate(0); }
        25% { transform: translate(120px, -40px) rotate(30deg); }
        50% { transform: translate(180px, 10px) rotate(-10deg); }
        75% { transform: translate(40px, -60px) rotate(45deg); }
    }

    @keyframes dog-follow {
        0%, 12%, 100% { transform: translate(0, 40px) rotate(0); }
        35% { transform: translate(100px, 0px) rotate(15deg); }
        60% { transform: translate(150px, 50px) rotate(-5deg); }
        85% { transform: translate(30px, -10px) rotate(20deg); }
    }

    /* --- UI 框架 --- */
    .main-header {
        background: linear-gradient(90deg, #9333ea, #a855f7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3.2rem;
        font-weight: 800;
        text-align: center;
        padding-top: 1.5rem;
        margin-bottom: 0.5rem;
    }

    .glass-card {
        background: rgba(255, 255, 255, 0.85);
        border: 2px solid #e9d5ff;
        border-radius: 2rem;
        padding: 2.5rem;
        box-shadow: 0 15px 40px rgba(168, 85, 247, 0.08);
        margin-bottom: 2.5rem;
    }

    /* 侧边栏品牌卡片 (紫色回归) */
    .sidebar-brand-card {
        background: linear-gradient(135deg, rgba(147, 51, 234, 0.1) 0%, rgba(168, 85, 247, 0.05) 100%);
        border-radius: 1.5rem;
        padding: 1.5rem 1rem;
        margin-bottom: 1.2rem;
        border: 1px solid rgba(147, 51, 234, 0.2);
        text-align: center;
        backdrop-filter: blur(10px);
    }
    
    .sidebar-brand-title {
        color: #9333ea;
        font-size: 1.5rem;
        font-weight: 800;
        margin: 0.5rem 0 0 0;
        line-height: 1.2;
    }
    
    .sidebar-brand-subtitle {
        color: #a855f7;
        font-size: 0.9rem;
        font-weight: 600;
        opacity: 0.7;
        margin: 0;
    }

    .glass-card {
        background: rgba(255, 255, 255, 0.85);
        border: 2px solid #e9d5ff;
        border-radius: 2rem;
        padding: 2.5rem;
        box-shadow: 0 15px 40px rgba(168, 85, 247, 0.08);
        margin-bottom: 2.5rem;
    }

    /* 状态徽章 */
    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.5rem 1.5rem;
        border-radius: 2rem;
        font-size: 0.95rem;
        font-weight: 700;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    
    .status-pending { background-color: #f3e8ff; color: #7e22ce; border: 2.5px solid #ddd6fe; }
    .status-running { background-color: #ede9fe; color: #6d28d9; border: 2.5px solid #c4b5fd; animation: pulse-light 2s infinite; }
    .status-completed { background-color: #f0fdf4; color: #166534; border: 2.5px solid #bbf7d0; }

    @keyframes pulse-light {
        0% { opacity: 1; }
        50% { opacity: 0.6; }
        100% { opacity: 1; }
    }

    /* --- V7.2 侧边栏“去箭头”极致版 --- */
    
    [data-testid="stVerticalBlock"] > div:has(.sidebar-marker) {
        position: relative !important;
        margin-bottom: 4px !important; /* 修正：保持紧凑但绝对不重叠 */
        z-index: 5;
    }

    /* 主按钮：恢复紫色渐变，高频操作用色更深沉专业 */
    [data-testid="stVerticalBlock"] > div:has(.sidebar-marker) .stButton button {
        width: 100% !important;
        background: rgba(255, 255, 255, 0.5) !important;
        border: 1px solid rgba(147, 51, 234, 0.1) !important;
        border-radius: 12px !important;
        color: #5b4a7a !important;
        font-weight: 600 !important;
        height: 42px !important;
        padding-left: 16px !important;
        padding-right: 32px !important;
        text-align: left !important;
        justify-content: flex-start !important;
        box-shadow: none !important;
        transition: all 0.2s ease !important;
        backdrop-filter: blur(5px);
    }

    /* 激活态：紫色发光效果 */
    [data-testid="stVerticalBlock"] > div:has(.sidebar-marker.active) .stButton button {
        background: linear-gradient(135deg, #9333ea, #a855f7) !important;
        color: white !important;
        font-weight: 800 !important;
        box-shadow: 0 4px 15px rgba(147, 51, 234, 0.4) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }

    [data-testid="stVerticalBlock"] > div:has(.sidebar-marker) .stButton button:hover {
        background: rgba(147, 51, 234, 0.08) !important;
        transform: translateX(2px) !important;
    }

    /* --- 入户引导卡片 (Onboarding) --- */
    .onboarding-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 3rem 1rem;
        animation: fadeInScale 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    }

    @keyframes fadeInScale {
        from { opacity: 0; transform: scale(0.95); }
        to { opacity: 1; transform: scale(1); }
    }

    /* --- 单一无缝玻璃卡片 (Unified Glass Card) --- */
    div[data-testid="stVerticalBlock"]:has(> div > .onboarding-marker) {
        background: rgba(255, 255, 255, 0.7) !important;
        backdrop-filter: blur(25px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(25px) saturate(180%) !important;
        border: 1px solid rgba(255, 255, 255, 0.5) !important;
        border-radius: 2.5rem !important;
        padding: 3rem !important;
        width: 100% !important;
        max-width: 650px !important;
        margin: 4rem auto !important;
        box-shadow: 0 25px 50px -12px rgba(147, 51, 234, 0.1) !important;
        text-align: center;
        transition: all 0.3s ease;
    }

    /* 确保内部容器不产生额外间距 */
    div[data-testid="stVerticalBlock"]:has(> div > .onboarding-marker) > div {
        width: 100% !important;
        background: transparent !important;
    }

    .onboarding-marker { display: none; }

    /* 三点菜单：绝对定位并抹除箭头 */
    [data-testid="stVerticalBlock"] > div:has(.sidebar-marker) .stPopover {
        position: absolute !important;
        right: 12px !important;
        top: 50% !important;
        transform: translateY(-50%) !important;
        z-index: 10 !important;
        opacity: 0 !important;
        transition: opacity 0.2s !important;
    }

    [data-testid="stVerticalBlock"] > div:has(.sidebar-marker):hover .stPopover {
        opacity: 0.6 !important;
    }
    
    [data-testid="stVerticalBlock"] > div:has(.sidebar-marker):hover .stPopover:hover {
        opacity: 1 !important;
    }

    [data-testid="stVerticalBlock"] > div:has(.sidebar-marker) .stPopover button {
        background: transparent !important;
        border: none !important;
        color: #9ca3af !important; /* 浅灰 */
        font-size: 1.2rem !important;
        font-weight: 900 !important;
        padding: 0 !important;
        min-height: unset !important;
        width: 24px !important;
        height: 24px !important;
        box-shadow: none !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        line-height: 0 !important;
    }

    [data-testid="stVerticalBlock"] > div:has(.sidebar-marker) .stPopover button p {
        margin: 0 !important;
        padding-bottom: 8px !important; /* 让 ... 在视觉上居中 */
    }

    [data-testid="stVerticalBlock"] > div:has(.sidebar-marker) .stPopover button:hover {
        color: white !important;
        transform: scale(1.1);
    }

    /* --- V7.3 新建对话按钮: 强调主操作 --- */
    [data-testid="stVerticalBlock"] > div:has(.new-chat-marker) .stButton button {
        background: linear-gradient(135deg, #7e22ce, #9333ea) !important;
        border: none !important;
        color: white !important;
        border-radius: 14px !important;
        height: 48px !important;
        font-weight: 800 !important;
        font-size: 1.05rem !important;
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
        margin-bottom: 8px !important;
        box-shadow: 0 10px 20px rgba(126, 34, 206, 0.2) !important;
    }

    [data-testid="stVerticalBlock"] > div:has(.new-chat-marker) .stButton button:hover {
        transform: scale(1.03) !important;
        box-shadow: 0 12px 25px rgba(147, 51, 234, 0.35) !important;
        filter: brightness(1.1);
    }

    /* 强制压缩侧边栏所有垂直块的间隙 */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.6rem !important; /* 恢复呼吸感，配合 4px margin 实现“不松散” */
    }

    /* --- 气泡对话框增强 (基于 Marker 的左右对齐) --- */
    /* 用户气泡靠右 (通过查找 .msg-marker-user) */
    [data-testid="stChatMessage"]:has(.msg-marker-user) {
        flex-direction: row-reverse !important;
        justify-content: flex-start !important;
    }
    
    /* 极致兼容的选择器：锁定所有可能的聊天内容容器 */
    [data-testid="stChatMessage"]:has(.msg-marker-user) > div:nth-child(2),
    [data-testid="stChatMessage"]:has(.msg-marker-user) [data-testid="stchatMessageContentProxy"] {
        background-color: #f3e8ff !important;
        border-radius: 1.5rem 0.2rem 1.5rem 1.5rem !important;
        border: 1px solid #e9d5ff !important;
        margin: 0 0.5rem 0 4rem !important;
        padding: 0.8rem 1.5rem !important;
        width: fit-content !important;
        flex: 0 1 auto !important;
        max-width: 80% !important;
        box-shadow: 0 4px 12px rgba(168, 85, 247, 0.08) !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important; /* 核心修改：文字居中 */
        min-width: 0 !important;
    }

    /* AI 气泡靠左 (通过查找 .msg-marker-ai) */
    [data-testid="stChatMessage"]:has(.msg-marker-ai) {
        justify-content: flex-start !important;
    }
    
    [data-testid="stChatMessage"]:has(.msg-marker-ai) > div:nth-child(2),
    [data-testid="stChatMessage"]:has(.msg-marker-ai) [data-testid="stchatMessageContentProxy"] {
        background-color: white !important;
        border-radius: 0.2rem 1.5rem 1.5rem 1.5rem !important;
        border: 1px solid #e9d5ff !important;
        margin: 0 4rem 0 0.5rem !important;
        padding: 0.8rem 1.5rem !important;
        width: fit-content !important;
        flex: 0 1 auto !important;
        max-width: 80% !important;
        box-shadow: 0 4px 12px rgba(168, 85, 247, 0.08) !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important; /* 核心修改：文字居中 */
        min-width: 0 !important;
    }

    /* 隐藏标记位 */
    .msg-marker-user, .msg-marker-ai {
        display: none;
        height: 0;
        width: 0;
    }

    [data-testid="stChatMessage"] {
        background-color: transparent !important;
    }
</style>

</style>



<!-- 枫叶飘落层 -->
<div class="leaf-container">
    <div class="leaf" style="left: 10%; animation-delay: 0s;">🍁</div>
    <div class="leaf" style="left: 25%; animation-delay: 2s;">🍂</div>
    <div class="leaf" style="left: 45%; animation-delay: 5s;">🌸</div>
    <div class="leaf" style="left: 65%; animation-delay: 1s;">🧊</div>
    <div class="leaf" style="left: 85%; animation-delay: 3s;">⭐</div>
</div>

<!-- 底部追逐区 -->
<div class="garden-bottom">
    <div class="chase-butterfly">🦋</div>
    <div class="chase-dog">🐶</div>
</div>

<!-- 统一页头 (已移动到侧边栏) -->
""", unsafe_allow_html=True)


# ===== 辅助函数 =====

def call_api(method: str, endpoint: str, data: dict = None) -> dict:
    """调用后端 API"""
    url = f"{BACKEND_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=30)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, timeout=30)
        elif method == "PATCH":
            response = requests.patch(url, json=data, timeout=30)
        else:
            raise ValueError(f"不支持的方法: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.ConnectionError:
        st.error(f"无法连接到后端服务: {BACKEND_URL}")
        st.info("请确保后端服务已启动: `cd backend && uvicorn server:app --reload`")
        return None
    except requests.exceptions.Timeout:
        st.error("请求超时，请稍后重试")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"API 错误: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        st.error(f"请求失败: {e}")
        return None


def get_status_badge(status: str) -> str:
    """获取状态徽章 HTML"""
    status_classes = {
        "pending": "status-pending",
        "coordinator": "status-running",
        "expert": "status-running",
        "analyst": "status-running",
        "waiting_approval": "status-waiting",
        "approved": "status-completed",
        "completed": "status-completed",
        "rejected": "status-failed",
        "failed": "status-failed"
    }
    
    status_labels = {
        "pending": "⏳ 待处理",
        "coordinator": "🔄 规划中",
        "expert": "👨‍⚕️ 分诊中",
        "analyst": "📊 分析中",
        "waiting_approval": "⏸️ 等待审批",
        "approved": "✅ 已批准",
        "completed": "✅ 已完成",
        "rejected": "❌ 已拒绝",
        "failed": "❌ 失败"
    }
    
    css_class = status_classes.get(status, "status-pending")
    label = status_labels.get(status, status)
    
    return f'<span class="status-badge {css_class}">{label}</span>'


def get_urgency_class(urgency: str) -> str:
    """获取紧急程度样式类"""
    if "立即" in urgency or "120" in urgency:
        return "urgency-immediate"
    elif "24小时" in urgency or "尽快" in urgency:
        return "urgency-urgent"
    elif "3天" in urgency:
        return "urgency-soon"
    else:
        return "urgency-routine"


# ===== 初始化 Session State =====

if "sessions" not in st.session_state:
    # 初始默认会话
    default_id = str(uuid.uuid4())[:8]
    st.session_state.sessions = {
        default_id: {
            "name": "新对话 1",
            "messages": [{"role": "assistant", "content": "您好呀~ 我是您的健康管家小星球。💜", "intent": "general_chat"}],
            "current_task_id": None
        }
    }
    st.session_state.current_session_id = default_id

if "patient_id" not in st.session_state:
    # 隐私修复：新用户自动随机生成唯一 ID，不再默认 user_001
    st.session_state.patient_id = f"user_{str(uuid.uuid4())[:8]}"

if "onboarding_completed" not in st.session_state:
    st.session_state.onboarding_completed = False

if "force_profile_form" not in st.session_state:
    st.session_state.force_profile_form = False

# --- 自动恢复历史会话与个人档案 (Persistence Layer) ---
p_id = st.session_state.get("patient_id")
if "last_restored_pid" not in st.session_state or st.session_state.last_restored_pid != p_id:
    # 切换患者时，强制清空旧会话并重置引导状态
    st.session_state.sessions = {}
    
    # 1. 恢复对话列表
    history_data = call_api("GET", f"/patient/tasks/{p_id}")
    if history_data and history_data.get("tasks"):
        for task in history_data["tasks"]:
            t_id = task["task_id"]
            # 强化标题：包含日期减少混淆
            created_at = task.get("created_at", "")[:10] if task.get("created_at") else ""
            display_name = f"📅 {created_at} {task.get('patient_input', '历史对话')[:8]}" if created_at else task.get('patient_input', '历史对话')
            
            st.session_state.sessions[t_id] = {
                "name": display_name,
                "messages": [], # 初始空，后续通过 current_session 获取完整数据
                "current_task_id": t_id,
                "status": task.get("status")
            }
        
        # 自动选中并加载最新会话
        session_list = list(st.session_state.sessions.keys())
        st.session_state.current_session_id = session_list[0]
        st.spinner("正在加载完整对话记录...")
        history = call_api("GET", f"/tasks/{st.session_state.current_session_id}/messages")
        if history:
            st.session_state.sessions[st.session_state.current_session_id]["messages"] = history["messages"]
    else:
        # 如果没历史，创建一个空的
        default_id = str(uuid.uuid4())[:8]
        st.session_state.sessions[default_id] = {
            "name": "新对话 1",
            "messages": [{"role": "assistant", "content": "您好呀~ 我是您的健康管家小星球。💜", "intent": "general_chat"}],
            "current_task_id": None
        }
        st.session_state.current_session_id = default_id
    
    # 2. 恢复个人档案
    profile = call_api("GET", f"/patient/profile/{p_id}")
    if profile:
        st.session_state.p_name = profile.get("name", "未知患者")
        st.session_state.p_phone = profile.get("phone", "未登记")
        st.session_state.age = profile.get("age", "")
        st.session_state.gender = profile.get("gender", "不填")
        st.session_state.history = profile.get("history", "")
        st.session_state.p_smoking = profile.get("smoking", "不吸烟")
        st.session_state.p_alcohol = profile.get("alcohol", "不饮酒")
        st.session_state.p_medications = profile.get("medications", "无")

    st.session_state.last_restored_pid = p_id

if "polling_active" not in st.session_state:
    st.session_state.polling_active = False
if "require_approval" not in st.session_state:
    st.session_state.require_approval = False

# 获取当前会话引用
curr_id = st.session_state.current_session_id
curr_session = st.session_state.sessions[curr_id]

# ===== 侧边栏 (简洁版) =====

with st.sidebar:
    # --- 1. 品牌展示 (Header) ---
    st.markdown(f"""
    <div class="sidebar-brand-card">
        <img src="https://img.icons8.com/fluency/96/hospital.png" width="55" style="margin-bottom: 0.5rem;">
        <h2 class="sidebar-brand-title">智能医疗分诊助手</h2>
        <p class="sidebar-brand-subtitle">小星球健康空间</p>
    </div>
    """, unsafe_allow_html=True)

    # --- 0. 模式切换 ---
    st.session_state.require_approval = st.toggle(
        "🧠 开启专家复核模式", 
        value=st.session_state.require_approval,
        help="开启后，报告需经人工确认后发布"
    )
    st.markdown("---")

    # --- 2. 身份配置 (高频操作层) ---
    with st.expander("👤 患者画像设定", expanded=True):
        p_id_input = st.text_input("患者 ID", value=st.session_state.get("patient_id", "user_001"))
        if p_id_input != st.session_state.get("patient_id"):
            st.session_state.patient_id = p_id_input
            st.session_state.last_restored_pid = None 
            st.rerun() 
            
        st.session_state.p_name = st.text_input("姓名", value=st.session_state.get("p_name", ""), key="sb_name")
        st.session_state.p_phone = st.text_input("手机号", value=st.session_state.get("p_phone", ""), key="sb_phone")
        st.session_state.age = st.text_input("年龄", value=st.session_state.get("age", ""), key="sb_age")
        gender_options = ["不填", "男性", "女性"]
        current_gender = st.session_state.get("gender", "不填")
        gender_idx = gender_options.index(current_gender) if current_gender in gender_options else 0
        st.session_state.gender = st.selectbox("性别", gender_options, index=gender_idx, key="sb_gender")
        st.session_state.history = st.text_area("既往病史", value=st.session_state.get("history", ""), height=80, key="sb_history")
        
        with st.expander("🩺 更多背景"):
            smoke_options = ["不吸烟", "已戒烟", "偶尔吸烟", "经常吸烟"]
            current_smoke = st.session_state.get("p_smoking", "不吸烟")
            smoke_idx = smoke_options.index(current_smoke) if current_smoke in smoke_options else 0
            st.session_state.p_smoking = st.selectbox("吸烟史", smoke_options, index=smoke_idx, key="sb_smoke")

            alc_options = ["不饮酒", "已戒酒", "社交饮酒", "经常饮酒"]
            current_alc = st.session_state.get("p_alcohol", "不饮酒")
            alc_idx = alc_options.index(current_alc) if current_alc in alc_options else 0
            st.session_state.p_alcohol = st.selectbox("饮酒史", alc_options, index=alc_idx, key="sb_alc")
            st.session_state.p_medications = st.text_input("当前用药", value=st.session_state.get("p_medications", "无"), key="sb_med")

        if st.button("☁️ 同步到云端记忆", key="sync_sidebar_v2", use_container_width=True):
            call_api("POST", "/patient/profile", {
                "patient_id": st.session_state.patient_id,
                "name": st.session_state.p_name,
                "phone": st.session_state.p_phone,
                "age": st.session_state.age,
                "gender": st.session_state.gender,
                "history": st.session_state.history,
                "smoking": st.session_state.p_smoking,
                "alcohol": st.session_state.p_alcohol,
                "medications": st.session_state.p_medications
            })
            st.toast("✅ 档案已同步至云端", icon="💜")

    # --- 3. 核心功能: 开启咨询 (置于画像下方) ---
    st.markdown('<p style="color: #9ca3af; font-size: 0.85rem; font-weight: 600; margin-top: 1.2rem; margin-bottom: 0.4rem; padding-left: 10px;">快速操作</p>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="new-chat-marker"></div>', unsafe_allow_html=True)
        if st.button("➕ 开启全新对话", key="new_chat_v8", use_container_width=True):
            new_id = str(uuid.uuid4())[:8]
            st.session_state.sessions[new_id] = {
                "name": f"新对话 {len(st.session_state.sessions) + 1}",
                "messages": [{"role": "assistant", "content": "您好呀~ 我是您的健康小管家小星球。💜", "intent": "general_chat"}],
                "current_task_id": None
            }
            st.session_state.current_session_id = new_id
            st.rerun()

    # --- 4. 咨询足迹 (历史记录) ---
    st.markdown('<p style="color: #9ca3af; font-size: 0.85rem; font-weight: 600; margin-top: 1rem; margin-bottom: 0.4rem; padding-left: 10px;">历史会话</p>', unsafe_allow_html=True)
    
    # 渲染当前会话列表 (展示最近 10 个，倒序)
    s_items = list(st.session_state.sessions.items())
    for s_id, s_data in reversed(s_items):
        is_active = (s_id == st.session_state.current_session_id)
        with st.container():
            st.markdown(f'<div class="sidebar-marker {"active" if is_active else ""}" data-sid="{s_id}"></div>', unsafe_allow_html=True)
            if st.button(f" {s_data['name']}", key=f"btn_v9_{s_id}", use_container_width=True):
                st.session_state.current_session_id = s_id
                if not st.session_state.sessions[s_id].get("messages"):
                    with st.spinner("唤起记忆..."):
                        history = call_api("GET", f"/tasks/{s_id}/messages")
                        if history: st.session_state.sessions[s_id]["messages"] = history["messages"]
                st.rerun()
            
            with st.popover("", help="管理"):
                st.markdown("##### ⚙️ 会话管理")
                new_n = st.text_input("重命名", value=s_data['name'], key=f"ren_v9_{s_id}")
                if st.button("💾 保存", key=f"ok_v9_{s_id}", use_container_width=True):
                    if s_data.get("current_task_id"):
                        call_api("PATCH", f"/tasks/{s_id}/name", {"task_id": s_id, "name": new_n})
                    s_data['name'] = new_n
                    st.rerun()
                if st.button("🗑️ 删除", key=f"del_v9_{s_id}", type="primary", use_container_width=True):
                    if s_data.get("current_task_id"):
                        call_api("DELETE", f"/tasks/{s_id}")
                    del st.session_state.sessions[s_id]
                    if s_id == st.session_state.current_session_id:
                        st.session_state.current_session_id = list(st.session_state.sessions.keys())[0] if st.session_state.sessions else None
                        if not st.session_state.current_session_id:
                            d_id = str(uuid.uuid4())[:8]
                            st.session_state.sessions[d_id] = {"name": "新对话", "messages": [], "current_task_id": None}
                            st.session_state.current_session_id = d_id
                    st.rerun()

    st.caption("⚠️ 系统建议仅供医学参考")

# ===== 核心弹窗逻辑 (Professional Modal) =====

@st.dialog("🏥 智慧医疗建档中心")
def show_registration_dialog():
    st.markdown("""
        <p style="color: #6b7280; margin-top: -1rem;">为了提供专业级诊断，建议您完善或找回已有的医疗档案</p>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["✨ 新建医疗档案", "🔍 找回我的档案"])
    
    with tab1:
        col_id1, col_id2 = st.columns(2)
        with col_id1:
            name = st.text_input("真实姓名*", value=st.session_state.get("p_name", ""), placeholder="如: 张三")
        with col_id2:
            phone = st.text_input("联系电话*", value=st.session_state.get("p_phone", ""), placeholder="11位手机号")
            
        col1, col2 = st.columns(2)
        with col1:
            age = st.text_input("患者年龄", value=st.session_state.get("age", ""), placeholder="如: 55")
        with col2:
            gender = st.selectbox("患者性别", ["不填", "男性", "女性"], index=["不填", "男性", "女性"].index(st.session_state.get("gender", "不填")), key="dlg_gender")
        
        history = st.text_area("既往病史与过敏史", 
                              value=st.session_state.get("history", "") if st.session_state.get("history") != "暂无历史记录" else "",
                              placeholder="如: 高血压5年，对青霉素过敏...", height=100)
        
        with st.expander("🩺 更多背景 (有助于提高诊断准确度)"):
            smoking = st.selectbox("吸烟史", ["不吸烟", "已戒烟", "偶尔吸烟", "经常吸烟"], index=["不吸烟", "已戒烟", "偶尔吸烟", "经常吸烟"].index(st.session_state.get("p_smoking", "不吸烟")), key="p_smoke_dlg")
            alcohol = st.selectbox("饮酒史", ["不饮酒", "已戒酒", "社交饮酒", "经常饮酒"], index=["不饮酒", "已戒酒", "社交饮酒", "经常饮酒"].index(st.session_state.get("p_alcohol", "不饮酒")), key="p_alc_dlg")
            medications = st.text_input("正在使用的药物", value=st.session_state.get("p_medications", ""), placeholder="如: 降压药、感冒药等", key="p_med_dlg")

        if st.button("🚀 保存并立即开启对话", type="primary", use_container_width=True):
            if not name or not phone:
                st.error("请至少填写姓名和电话，以便下次找回。")
                return
            
            # 生成临时 ID (如果还没有)
            p_id = st.session_state.get("patient_id", "user_" + str(phone)[7:])
            
            call_api("POST", "/patient/profile", {
                "patient_id": p_id,
                "name": name,
                "phone": phone,
                "age": age,
                "gender": gender,
                "history": history,
                "smoking": smoking,
                "alcohol": alcohol,
                "medications": medications
            })
            
            # 更新本地状态与 Sidebar 组件状态同步
            st.session_state.patient_id = p_id
            st.session_state.p_name = name
            st.session_state.p_phone = phone
            st.session_state.age = age
            st.session_state.gender = gender
            st.session_state.history = history
            st.session_state.p_smoking = smoking
            st.session_state.p_alcohol = alcohol
            st.session_state.p_medications = medications
            
            # 强制同步到 Sidebar 组件绑定的 Key
            st.session_state.sb_name = name
            st.session_state.sb_phone = phone
            st.session_state.sb_age = age
            st.session_state.sb_gender = gender
            st.session_state.sb_history = history
            st.session_state.sb_smoke = smoking
            st.session_state.sb_alc = alcohol
            st.session_state.sb_med = medications
            
            st.session_state.onboarding_completed = True
            st.session_state.force_profile_form = False
            st.session_state.last_restored_pid = p_id
            st.rerun()

    with tab2:
        search_query = st.text_input("输入您的姓名或手机号", placeholder="快速搜索我的健康档案...")
        if search_query:
            results = call_api("GET", f"/patient/search?query={search_query}")
            if results and results.get("results"):
                st.markdown("---")
                for p in results["results"]:
                    res_col1, res_col2 = st.columns([3, 1])
                    with res_col1:
                        st.markdown(f"**{p['name']}** ({p['gender']}, {p['age']}岁)")
                        st.caption(f"📞 {p['phone']} | ID: {p['patient_id']}")
                    with res_col2:
                        if st.button("✅ 选定", key=f"sel_{p['patient_id']}", use_container_width=True):
                            st.session_state.patient_id = p['patient_id']
                            st.session_state.onboarding_completed = True
                            st.session_state.force_profile_form = False
                            st.session_state.last_restored_pid = None # 强制触发数据同步
                            st.rerun()
            else:
                st.warning("并未找到匹配档案，您可以尝试新建。")


# ===== 主界面渲染逻辑 =====

st.title("🏥 智能医疗分诊助手")
st.markdown("---")

if not st.session_state.onboarding_completed and len(curr_session["messages"]) < 2:
    # 检查是否为老用户 (除非强制显示表单)
    is_old_user = (st.session_state.get("age") or (st.session_state.get("history") and st.session_state.history != "暂无历史记录")) \
                  and not st.session_state.get("force_profile_form", False)
    
    if not is_old_user or st.session_state.get("force_profile_form"):
        # 触发弹窗
        show_registration_dialog()
        # 并在页面留一个优雅的占位背景
        st.markdown("""
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 60vh; opacity: 0.5;">
                <img src="https://img.icons8.com/fluency/96/medical-history.png" width="100">
                <h2 style="color: #9333ea; font-weight: 700;">医疗引擎已就绪</h2>
                <p>正在等待档案创建...</p>
            </div>
        """, unsafe_allow_html=True)
        st.stop() # 停止后续渲染，直到弹窗操作完成
    else:
        # 老用户回归欢迎 (现在通过 st.container 配合 CSS 实现整体包裹)
        with st.container():
            st.markdown('<div class="onboarding-marker"></div>', unsafe_allow_html=True)
            st.markdown(f"""
                <div style="text-align: center; margin-bottom: 2rem;">
                    <img src="https://img.icons8.com/fluency/96/handshake.png" width="80">
                    <h1 style="font-size: 2.22rem; font-weight: 800; background: linear-gradient(135deg, #7e22ce, #9333ea); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.2rem;">
                        欢迎回来，{st.session_state.get('p_name', '主公')}
                    </h1>
                    <p style="color: #6b7280; font-size: 1rem; opacity: 0.8;">我已备好您的健康档案，随时为您效劳</p>
                </div>
                <div style="background: rgba(147, 51, 234, 0.03); border-radius: 1.2rem; padding: 1.2rem; text-align: left; border: 1px solid rgba(147, 51, 234, 0.1); margin-bottom: 2rem;">
                    <p style="margin: 0; color: #7e22ce; font-weight: 700; font-size: 0.9rem; letter-spacing: 0.05em;">📋 档案摘要</p>
                    <div style="margin-top: 0.5rem; color: #4b5563; font-size: 0.95rem; line-height: 1.6;">
                        <span style="opacity: 0.7;">姓名:</span> <b>{st.session_state.get('p_name')}</b> | <span style="opacity: 0.7;">电话:</span> <b>{st.session_state.get('p_phone')}</b><br>
                        <span style="opacity: 0.7;">生活习惯:</span> {st.session_state.get('p_smoking')}、{st.session_state.get('p_alcohol')}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # 这里是真正的 Streamlit 按钮
            bc1, bc2 = st.columns([2, 1])
            with bc1:
                if st.button("🚀 即刻开始问诊", type="primary", use_container_width=True, key="start_now_v8"):
                    st.session_state.onboarding_completed = True
                    st.rerun()
            with bc2:
                if st.button("📝 修正档案", use_container_width=True, key="fix_profile_v8"):
                    st.session_state.force_profile_form = True
                    st.rerun()
        st.stop()

# 渲染对话历史
for idx, msg in enumerate(curr_session["messages"]):
    avatar = "🪐" if msg["role"] == "assistant" else "⭐"
    # 注入隐藏 Marker 辅助 CSS 对齐
    marker_class = "msg-marker-ai" if msg["role"] == "assistant" else "msg-marker-user"
    with st.chat_message(msg["role"], avatar=avatar):
        # 合并渲染，确保 marker 和内容在同一个 div 内，增强选择器稳定性
        st.markdown(f'<div class="{marker_class}"></div>' + msg["content"], unsafe_allow_html=True)
        
        # 处理中间步骤 (仅在医疗模式下显示，保持一般对话的清爽感)
        if "steps" in msg and msg.get("intent") != "general_chat":
            with st.expander("🧩 查看 AI 思考路径 (Map-Reduce)"):
                for step in msg["steps"]:
                    st.caption(f"📍 {step.get('agent_name')}: {step.get('action')} ({step.get('duration_ms')}ms)")
        
        # 处理人工审批 (Inline)
        if "task_data" in msg and msg["task_data"].get("status") == "waiting_approval":
            task = msg["task_data"]
            res = task.get("triage_result", {})
            
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.warning("🕵️ 主公，这是我初步整理的建议，您看看是否合适？")
            st.info(f"**初步判断**: {res.get('diagnosis_suggestion')}\n\n**建议科室**: {', '.join(res.get('department', []))}")
            
            # 审批按钮层
            rev_comment = st.text_input("您可以输入补充意见 (可选)", key=f"rev_{idx}")
            btn_col1, btn_col2 = st.columns(2)
            
            with btn_col1:
                if st.button("✅ 批准方案", key=f"app_{idx}", type="primary", use_container_width=True):
                    with st.spinner("同步中..."):
                        call_api("POST", "/human-approval", {
                            "task_id": task["task_id"],
                            "approved": True,
                            "reviewer_comment": rev_comment
                        })
                    # 更新本地显示状态
                    msg["task_data"]["status"] = "approved"
                    st.rerun()
            
            with btn_col2:
                if st.button("❌ 重新调整", key=f"rej_{idx}", use_container_width=True):
                    with st.spinner("同步中..."):
                        call_api("POST", "/human-approval", {
                            "task_id": task["task_id"],
                            "approved": False,
                            "reviewer_comment": rev_comment
                        })
                    msg["task_data"]["status"] = "rejected"
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# 聊天输入
if prompt := st.chat_input("在这里可以跟我聊聊，我就在这里听着呢..."):
    # 展示用户消息并更新会话标题 (带时间戳)
    if len(curr_session["messages"]) < 2:
        now_str = datetime.now().strftime("%m-%d")
        curr_session["name"] = f"📅 {now_str} {prompt[:8]}"
        
    curr_session["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="⭐"):
        st.markdown('<div class="msg-marker-user"></div>' + prompt, unsafe_allow_html=True)
    
    # 准备数据并调用后端
    patient_info = {
        "name": st.session_state.get("p_name"),
        "phone": st.session_state.get("p_phone"),
        "age": st.session_state.get("age"),
        "gender": st.session_state.get("gender"),
        "history": st.session_state.get("history"),
        "smoking": st.session_state.get("p_smoking"),
        "alcohol": st.session_state.get("p_alcohol"),
        "medications": st.session_state.get("p_medications")
    }
    
    result = call_api("POST", "/start", {
        "patient_description": prompt,
        "patient_id": st.session_state.get("patient_id", "default_user"),
        "patient_info": patient_info,
        "require_approval": st.session_state.require_approval,
        "chat_history": curr_session["messages"],
        "task_id": curr_session.get("current_task_id")
    })
    
    if result:
        intent = result.get("intent", "medical_triage")
        # 统一保存 Task ID，确保后续对话在同一个 Thread
        if result.get("task_id"):
            curr_session["current_task_id"] = result["task_id"]
            
        if intent == "general_chat":
            # 直接添加回复，结束生命周期
            curr_session["messages"].append({
                "role": "assistant", 
                "content": result.get("reply", "你好呀~"),
                "intent": "general_chat"
            })
            st.rerun()
        else:
            # 开启寻医问诊模式
            status_placeholder = st.empty()
            status_placeholder.markdown("✨ 智慧引擎正在启动 (检索医学知识图谱 & 历史记忆)...")
            
            task_id = result.get("task_id")
            curr_session["current_task_id"] = task_id
            st.session_state.polling_active = True
            st.rerun()

# ===== 后台任务轮询逻辑 (全局) =====

if st.session_state.polling_active and curr_session["current_task_id"]:
    task_id = curr_session["current_task_id"]
    
    with st.chat_message("assistant", avatar="🪐"):
        st.markdown('<div class="msg-marker-ai"></div>', unsafe_allow_html=True)
        status_placeholder = st.empty()
        
        # 轮询状态
        task = call_api("GET", f"/status/{task_id}")
        if task:
            status = task.get("status")
            steps = task.get("steps", [])
            
            # 显示进度
            if status not in ["completed", "approved", "waiting_approval", "failed", "rejected"]:
                current_agent = steps[-1].get("agent_name", "AI") if steps else "智慧引擎"
                status_placeholder.markdown(f"🧬 **{current_agent}** 正在深度分析中... (累计完成 {len(steps)} 个任务节点)")
                time.sleep(1.5)
                st.rerun()
            else:
                # 任务终结
                st.session_state.polling_active = False
                
                if status == "waiting_approval":
                    curr_session["messages"].append({
                        "role": "assistant", 
                        "content": "✨ **我已经为您整理好了初步方案，请您过目并批准：**",
                        "task_data": task,
                        "steps": steps
                    })
                elif status in ["completed", "approved"]:
                    res = task.get("triage_result", {})
                    intent = task.get("intent", "medical_triage")
                    
                    if intent == "general_chat":
                        final_content = task.get("analysis_report", "分析完成。")
                    else:
                        # 彻底对话化：不再罗列标签，只展示有温度的建议正文
                        # 如果有科室建议，以非常微弱的方式附带在最后
                        advice = res.get('advice', '')
                        dept_str = f"建议挂号: {', '.join(res.get('department', []))}" if res.get('department') else ""
                        urg_str = f"紧急程度: {res.get('urgency')}" if res.get('urgency') else ""
                        
                        final_content = f"{advice}\n\n"
                        if dept_str or urg_str:
                             final_content += f"---\n"
                             final_content += f"*{dept_str} | {urg_str}*"
                    
                    curr_session["messages"].append({
                        "role": "assistant", 
                        "content": final_content,
                        "steps": steps,
                        "intent": intent
                    })
                elif status == "failed":
                    curr_session["messages"].append({
                        "role": "assistant", 
                        "content": f"❌ 抱歉，分诊任务遇到异常: {task.get('error')}"
                    })
                
                st.rerun()


# 对话引导
if len(curr_session["messages"]) < 2:
    st.info("👋 别紧张，您可以先跟我打个招呼，或者直接说说哪里不舒服。我就在这里陪着您呢~")


# ===== 页脚 =====

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.875rem;">
    <p>⚠️ 重要提示：本系统提供的分诊建议仅供参考，不能替代专业医生的诊断和治疗。如有紧急情况，请立即拨打 120 或前往最近的医院急诊。</p>
    <p>智能医疗分诊助手 v1.0.0 | 基于 LangGraph + FastAPI + Streamlit</p>
</div>
""", unsafe_allow_html=True)
