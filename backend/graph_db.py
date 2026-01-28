#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医疗知识图谱模块 (Lite KG)

使用 NetworkX 构建轻量级图数据库，用于增强 Agent 的事实推理能力。
"""

import json
import networkx as nx
from pathlib import Path
from typing import List, Dict, Any, Optional


class MedicalGraph:
    """基于 NetworkX 的医疗知识图谱"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MedicalGraph, cls).__new__(cls)
            cls._instance.graph = nx.DiGraph()
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.knowledge_path = Path("data/medical_knowledge.json")
        self._build_graph()
        self._initialized = True
        
    def _build_graph(self):
        """从 JSON 知识库构建图"""
        if not self.knowledge_path.exists():
            return
            
        try:
            with open(self.knowledge_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            departments = data.get("departments", {})
            self._all_symptoms = set() # 存储所有已知症状

            for dept_name, dept_info in departments.items():
                # 添加科室节点
                self.graph.add_node(dept_name, type="department")
                
                diseases = dept_info.get("diseases", [])
                for disease in diseases:
                    disease_name = disease.get("name")
                    # 添加疾病节点
                    self.graph.add_node(disease_name, type="disease", 
                                      urgency=disease.get("urgency", "unknown"),
                                      advice=disease.get("advice", []))
                    
                    # 建立 疾病 -> 属于 -> 科室 关系
                    self.graph.add_edge(disease_name, dept_name, relation="belongs_to")
                    
                    # 添加症状并建立 症状 -> 提示 -> 疾病 关系
                    for symptom in disease.get("symptoms", []):
                        self.graph.add_node(symptom, type="symptom")
                        self._all_symptoms.add(symptom)
                        self.graph.add_edge(symptom, disease_name, relation="suggests")
                        
                    # 添加风险因素
                    for risk in disease.get("risk_factors", []):
                        self.graph.add_node(risk, type="risk_factor")
                        self.graph.add_edge(risk, disease_name, relation="increases_risk_of")
                        
            print(f"[KG] 知识图谱构建完成: {self.graph.number_of_nodes()} 节点, {self.graph.number_of_edges()} 关系, 已知症状: {len(self._all_symptoms)}")
            
        except Exception as e:
            print(f"[KG] 构建失败: {e}")

    def extract_symptoms(self, text: str) -> List[str]:
        """从文本中动态提取已知症状"""
        if not hasattr(self, '_all_symptoms'):
            return []
        # 简单匹配：检查已知症状词是否在文本中
        return [s for s in self._all_symptoms if s in text]

    def query_relation(self, entity_name: str) -> Dict[str, Any]:
        """查询实体的关联信息"""
        if entity_name not in self.graph:
            return {}
            
        neighbors = list(self.graph.neighbors(entity_name))
        predecessors = list(self.graph.predecessors(entity_name))
        
        node_data = self.graph.nodes[entity_name]
        
        result = {
            "entity": entity_name,
            "type": node_data.get("type"),
            "related_to": neighbors,
            "suggested_by": predecessors if node_data.get("type") == "disease" else []
        }
        
        # 如果是疾病，附带紧急度和建议
        if node_data.get("type") == "disease":
            result["urgency"] = node_data.get("urgency")
            result["advice"] = node_data.get("advice")
            
        return result

    def get_context_for_symptoms(self, symptoms: List[str]) -> str:
        """为一组症状生成图谱背景知识"""
        relevant_diseases = {}
        
        for symptom in symptoms:
            if symptom in self.graph:
                # 寻找该症状提示的所有疾病
                for disease in self.graph.neighbors(symptom):
                    if self.graph.nodes[disease].get("type") == "disease":
                        if disease not in relevant_diseases:
                            relevant_diseases[disease] = {
                                "symptoms": [symptom],
                                "departments": list(self.graph.neighbors(disease))
                            }
                        else:
                            if symptom not in relevant_diseases[disease]["symptoms"]:
                                relevant_diseases[disease]["symptoms"].append(symptom)
                            
        if not relevant_diseases:
            return "知识图谱中未找到直接匹配的逻辑链条。"
            
        context = "【基于知识图谱的逻辑关联】\n"
        for d, info in relevant_diseases.items():
            depts = "、".join([n for n in info["departments"] if self.graph.nodes[n].get("type") == "department"])
            context += f"- 症状 [{', '.join(info['symptoms'])}] -> 可能疾病: {d} (推荐科室: {depts})\n"
            
        return context


# 单例实例
medical_kg = MedicalGraph()

if __name__ == "__main__":
    # 简单测试
    kg = MedicalGraph()
    print(kg.get_context_for_symptoms(["胸痛", "气短"]))
