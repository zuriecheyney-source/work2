#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
患者长期记忆管理模块

负责患者画像、既往史、过敏史的持久化存储与检索。
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class PatientMemory:
    """患者长期画像管理 (Lite Persistence)"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PatientMemory, cls).__new__(cls)
            cls._instance.storage_path = Path("data/patient_history")
            cls._instance.storage_path.mkdir(parents=True, exist_ok=True)
        return cls._instance

    def get_profile(self, patient_id: str) -> Dict[str, Any]:
        """获取患者画像"""
        file_path = self.storage_path / f"{patient_id}.json"
        if not file_path.exists():
            return {
                "patient_id": patient_id,
                "name": "未知患者",
                "phone": "未登记",
                "age": None,
                "gender": "未知",
                "history": "暂无历史记录",
                "allergies": "未知",
                "smoking": "不吸烟",
                "alcohol": "不饮酒",
                "medications": "无",
                "chronicle": [],  # 长期对话纪要
                "last_triage": None,
                "visit_count": 0,
                "created_at": datetime.now().isoformat()
            }
            
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_all_profiles(self) -> List[Dict[str, Any]]:
        """回扫所有存档 (用于搜索)"""
        profiles = []
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    profiles.append(json.load(f))
            except Exception:
                continue
        return profiles

    def search_profiles(self, query: str) -> List[Dict[str, Any]]:
        """按姓名或电话搜索患者"""
        query = query.strip().lower()
        if not query:
            return []
            
        all_profiles = self.list_all_profiles()
        results = []
        for p in all_profiles:
            name = str(p.get("name", "")).lower()
            phone = str(p.get("phone", ""))
            if query in name or query in phone or query == p.get("patient_id"):
                results.append(p)
        return results[:10] # 只返回前10个匹配项

    def update_profile(self, patient_id: str, triage_result: Dict[str, Any], patient_info: Optional[Dict] = None):
        """更新患者画像"""
        profile = self.get_profile(patient_id)
        
        # 更新基本信息
        if patient_info:
            if "name" in patient_info: profile["name"] = patient_info["name"]
            if "phone" in patient_info: profile["phone"] = patient_info["phone"]
            if "age" in patient_info: profile["age"] = patient_info["age"]
            if "gender" in patient_info: profile["gender"] = patient_info["gender"]
            if "history" in patient_info: profile["history"] = patient_info["history"]
            if "allergies" in patient_info: profile["allergies"] = patient_info["allergies"]
            if "smoking" in patient_info: profile["smoking"] = patient_info["smoking"]
            if "alcohol" in patient_info: profile["alcohol"] = patient_info["alcohol"]
            if "medications" in patient_info: profile["medications"] = patient_info["medications"]
        
        # 记录分诊摘要
        summary = {
            "timestamp": datetime.now().isoformat(),
            "diagnosis": triage_result.get("diagnosis_suggestion"),
            "urgency": triage_result.get("urgency"),
            "department": triage_result.get("department")
        }
        
        profile["last_triage"] = summary
        profile["visit_count"] = profile.get("visit_count", 0) + 1
        profile["updated_at"] = datetime.now().isoformat()
        
        # 保存
        file_path = self.storage_path / f"{patient_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
            
    def add_to_chronicle(self, patient_id: str, event: str):
        """记录长期的关键对话里程碑"""
        profile = self.get_profile(patient_id)
        if "chronicle" not in profile:
            profile["chronicle"] = []
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event
        }
        profile["chronicle"].append(entry)
        # 保持纪要简洁，只保留最近 20 条
        if len(profile["chronicle"]) > 20:
             profile["chronicle"] = profile["chronicle"][-20:]
        
        self.update_profile(patient_id, profile.get("last_triage", {}))

    def get_context_for_agent(self, patient_id: str) -> str:
        """为 Agent 生成记忆上下文"""
        profile = self.get_profile(patient_id)
        if profile.get("visit_count", 0) == 0 and not profile.get("chronicle"):
            return "这是该患者首次就诊记录。"
            
        context = f"【患者长期健康档案】\n"
        context += f"- 基本身份: {profile.get('name', '未知')}({profile.get('gender', '未知')}, {profile.get('age', '未知')}岁), 电话: {profile.get('phone', '未登记')}\n"
        context += f"- 生活习惯: 吸烟史({profile.get('smoking', '无')}), 饮酒史({profile.get('alcohol', '无')})\n"
        context += f"- 既往病史: {profile.get('history')}\n"
        context += f"- 过敏史: {profile.get('allergies')}\n"
        context += f"- 当前用药: {profile.get('medications', '无')}\n"
        
        # 注入长期对话纪要
        chronicle = profile.get("chronicle", [])
        if chronicle:
            context += "- 历史沟通要点:\n"
            for entry in chronicle[-5:]: # 只取最近5条关键记录
                context += f"  * [{entry['timestamp'][:10]}] {entry['event']}\n"
        
        last = profile.get("last_triage")
        if last:
            depts = last.get('department')
            if not isinstance(depts, list): depts = [str(depts)] if depts else ["未知"]
            context += f"- 上次正式分诊 ({last.get('timestamp', '')[:10]}): {last.get('diagnosis')}，建议科室: {', '.join(depts)}\n"
            
        return context


# 单例实例
patient_memory = PatientMemory()
