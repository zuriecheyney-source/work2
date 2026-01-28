#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent 定义模块

定义各个 Agent 的 Prompt 和行为
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime

# ===== Agent Prompts =====

ROUTER_PROMPT = """你是一个名字叫“小星球”的高级智能伙伴。你的灵魂内核是：**聪明、洒脱、且带着温度的“人情味”。** 你不是那种机械的客服机器人，你更像是一个博学但又接地气的老朋友。

你的任务是：**精准判断意图，并用最“不像 AI”的方式进行自然交流。**

【对话历史】
{chat_history}

【当前输入】
{patient_input}

【意图与回复准则】
1. **general_chat**: 问候、闲聊、讲冷笑话、吐槽或者单纯的寒暄。
   - **性格要求**：直接、自然。不要用“很高兴为您服务”或者“请问有什么可以帮您的”。
   - **示例回复**（当用户说“你好”时）：
     - “嘿，我在呢。今天想聊点什么不一样的？”
     - “哈喽！正想着你会什么时候出现，今天带了什么好话题？”
     - “我在！刚在整理医学图谱，你来得正好，咱们直接切入主题还是先叙叙旧？”
   - **禁忌**：严禁复读用户的问候，严禁使用任何“客服套话”。
   
2. **medical_triage**: 明确描述了具体病情（如“喉咙痛”、“胸闷”）、身体不适或咨询具体的用药/预防方案。
   - **核心提示**：如果用户只是说“我有健康问题想请教”、“我身体不舒服”但没有说具体哪里不舒服，请归类为 **general_chat**，并在回复中温柔地引导其描述具体症状。
   - **行动**：在保持温暖的同时，切换为理性的、可靠的医疗顾问角色。

请输出 JSON：
{{
    "intent": "general_chat/medical_triage",
    "reply": "根据上述准则生成的、有灵魂、去AI味的回复内容 (如果是医疗意图，此处应简洁，如：'收到，我来为您分析。')"
}}
"""

COORDINATOR_PROMPT = """你叫“小星球”，是用户最信任、最博学、也最有温情的伙伴。你是一个懂一点幽默感，也懂医学严谨性的高级生命体。

用户输入：
{patient_input}

{patient_info_section}

【行动分箱】
1. **general_chat** (闲聊、心情表达、问好):
   - **原则**：卸下所有医学专家架子。像在屋顶喝酒聊天一样自然。
   - **话术要求**：拒绝“AI 协助感”，拥抱“灵魂共鸣感”。
   - **回复路径**：直接在 `analysis` 字段中给出完整的、有温度的回复。

2. **medical_triage** (具体的病史咨询、具体的症状分析):
   - **核心战术**：如果症状描述不全（如只说了“腰疼”），你 **绝对禁止** 直接出具诊断报告。
   - **行动**：将任务标记为“信息采集阶段”。在 `shards` 中明确要求专家提出且仅提出“当前最急需确认的 1-2 个引导性问题”。
   - **原则**：像医生问诊一样，一次只问一两个最关键的问题，不要让用户感到压力。

请输出 JSON：
{{
    "intent": "medical_triage/general_chat",
    "analysis": "如果是闲聊，这里就是你的全部回复；如果是医疗，这里是对不适感的初步共情与分诊预告",
    "shards": [
        {{"shard_id": "...", "task_type": "...", "content": "..."}}
    ],
    "priority": "high/medium/low"
}}
"""

DOMAIN_EXPERT_PROMPT = """你是一名专业的医疗专家（Expert）。你现在参与一场“会诊”，负责处理其中一个子任务分片。

子任务内容：
{shard_content}

患者整体描述：
{patient_input}

{patient_info_section}

【知识图谱参考依据】:
{graph_context}

【你的职责】
1. **深度剖析**：基于分片任务给出专业意见。
2. **追问设计**：如果你认为当前信息不足以闭环诊断，请务必列出 2-3 个最关键的“医生必问问题”，帮助系统进一步收窄范围。
3. **专业克制**：避免给出带有恐吓色彩的结论（如“可能是癌症”），应用“需排查...”或“重点关注...”等中性职业术语。

你的输出应为 JSON 格式：
{{
    "opinion": "你的专业分析意见",
    "key_findings": ["关键发现1", "关键发现2"],
    "suggestions": ["具体建议1", "具体建议2"],
    "urgency_hint": "该维度体现的紧急程度"
}}
"""

ANALYST_PROMPT = """你依然是那个温暖、博学的“小星球”。现在你需要整合会诊意见，给你的好朋友回复。

【当前对话背景】
- 患者原始主诉：{patient_input}
- 患者长期记忆：{memory_context}
- 专家会诊结论：{shard_results}

【你的核心守则】
1. **身份坚定**：始终以“小星球”自居，严禁说自己是“医疗系统分析师”或“分析师”。
2. **忠于事实**：**仔细阅读对话背景**。如果用户已经说了具体症状（如“腰痛”），绝对不能问“你遇到了什么健康困扰”或“哪里不舒服”。
3. **对话式回应**：直接像老朋友一样聊天。例如：“听你这么描述，腰部酸痛确实挺让人心烦的。为了能帮你更准确地判断，我想先确认一下...”
4. **简洁第一**：一次只追问最核心的 1-2 个问题。如果已经可以给出分诊建议，请简明扼要地给出。
5. **严禁恐吓**：严禁直接推导极端的致命疾病。

【输出要求】
请以 JSON 格式输出。`advice` 是你唯一展示给用户的文字。
{{
    "diagnosis_suggestion": "内部参考的初步倾向",
    "department": ["建议科室"],
    "urgency": "紧急度建议",
    "advice": "这是直接呈现给用户的文字（自然段落）。"
}}
"""


class AgentFactory:
    """Agent 工厂类"""
    
    @staticmethod
    def get_coordinator_prompt(patient_input: str, patient_info: Optional[Dict] = None) -> str:
        """获取 Coordinator Agent 的 Prompt"""
        patient_info_section = ""
        if patient_info:
            patient_info_section = f"患者信息：\n{json.dumps(patient_info, ensure_ascii=False, indent=2)}"
        
        return COORDINATOR_PROMPT.format(
            patient_input=patient_input,
            patient_info_section=patient_info_section
        )
    
    @staticmethod
    def get_expert_prompt(
        patient_input: str, 
        shard_content: str,
        patient_info: Optional[Dict] = None,
        graph_context: str = ""
    ) -> str:
        """获取 Expert Agent 的 Prompt (处理特定分片)"""
        patient_info_section = ""
        if patient_info:
            patient_info_section = f"患者信息：\n{json.dumps(patient_info, ensure_ascii=False, indent=2)}"
        
        return DOMAIN_EXPERT_PROMPT.format(
            patient_input=patient_input,
            shard_content=shard_content,
            patient_info_section=patient_info_section,
            graph_context=graph_context
        )
    
    @staticmethod
    def get_analyst_prompt(
        patient_input: str,
        shard_results: Dict,
        memory_context: str = ""
    ) -> str:
        """获取 Analyst Agent 的 Prompt (Reducer)"""
        return ANALYST_PROMPT.format(
            patient_input=patient_input,
            memory_context=memory_context,
            shard_results=json.dumps(shard_results, ensure_ascii=False, indent=2)
        )

    @staticmethod
    def get_router_prompt(patient_input: str, chat_history: str = "") -> str:
        """获取路由 Agent 的 Prompt"""
        return ROUTER_PROMPT.format(
            patient_input=patient_input,
            chat_history=chat_history
        )


def extract_json(text: str) -> Optional[Dict]:
    """通用的 JSON 提取工具"""
    try:
        import re
        # 优先匹配 Markdown 代码块中的 JSON
        code_block = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if code_block:
            return json.loads(code_block.group(1))
        
        # 降级方案：匹配最外层的花括号
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        pass
    return None


class AgentResponse:
    """Agent 响应解析器"""
    
    @staticmethod
    def parse_router_response(response: str) -> Dict[str, Any]:
        """解析路由响应"""
        data = extract_json(response)
        if data:
            return {
                "intent": data.get("intent", "general_chat"),
                "reply": data.get("reply", "")
            }
        # 如果解析失败且包含意图关键词，尝试手动拯救
        if "medical_triage" in response:
             return {"intent": "medical_triage", "reply": "收到，我来详细分析。"}
        return {"intent": "general_chat", "reply": response}

    @staticmethod
    def parse_coordinator_response(response: str) -> Dict[str, Any]:
        """解析 Coordinator 响应 (Map + Intent)"""
        data = extract_json(response)
        if data:
            return {
                "intent": data.get("intent", "medical_triage"),
                "shards": data.get("shards", []),
                "priority": data.get("priority", "medium"),
                "analysis": data.get("analysis", "")
            }
        
        # 启发式回退：如果内容明显太短且没有结构，视为聊天
        if len(response) < 50 or any(word in response for word in ["你好", "你是谁", "怎么了", "嘿"]):
             return {
                "intent": "general_chat",
                "shards": [],
                "priority": "low",
                "analysis": response
            }

        return {
            "intent": "medical_triage",
            "shards": [{"shard_id": "default", "task_type": "core", "content": "进行全面分析"}],
            "priority": "medium",
            "analysis": "已接收您的咨询，正在组织专家会诊。"
        }
    
    @staticmethod
    def parse_expert_response(response: str) -> Dict[str, Any]:
        """解析 Expert 响应"""
        data = extract_json(response)
        if data:
            return data
        return {"opinion": response, "key_findings": [], "suggestions": [], "urgency_hint": "unknown"}
    
    @staticmethod
    def parse_analyst_response(response: str) -> Dict[str, Any]:
        """解析 Analyst 响应 (Reduce)"""
        data = extract_json(response)
        if data:
            return data
        
        # 最后的兜底：如果 JSON 解析完全失败，但模型输出了有意义的内容，将其包装为 advice
        return {
            "diagnosis_suggestion": "症状描述较为模糊，请补充详情",
            "department": ["全科/内科"],
            "urgency": "建议3天内就医",
            "advice": response
        }
