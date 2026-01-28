#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医疗分诊训练数据生成器

基于医学知识库生成高质量的指令微调数据集
数据格式: LlamaFactory Alpaca Format (instruction/input/output)

运行方式:
    python scripts/generate_data.py           # 生成数据
    python scripts/generate_data.py --validate # 验证数据格式
"""

import json
import random
import argparse
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime


class MedicalDataGenerator:
    """医疗分诊数据生成器"""
    
    def __init__(self, knowledge_path: str = "data/medical_knowledge.json"):
        """
        初始化生成器
        
        Args:
            knowledge_path: 医学知识库路径
        """
        self.knowledge_path = Path(knowledge_path)
        self.knowledge = self._load_knowledge()
        self.generated_inputs = set()  # 用于去重
        
    def _load_knowledge(self) -> Dict:
        """加载医学知识库"""
        if not self.knowledge_path.exists():
            raise FileNotFoundError(f"知识库文件不存在: {self.knowledge_path}")
        
        with open(self.knowledge_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_random_instruction(self) -> str:
        """获取随机的指令模板"""
        templates = self.knowledge.get("instruction_templates", [])
        return random.choice(templates) if templates else self._default_instruction()
    
    def _default_instruction(self) -> str:
        """默认指令"""
        return (
            "你是一名专业的医疗分诊助手。请根据患者描述的症状，"
            "给出初步诊断建议、推荐就诊科室、紧急程度评估和就医建议。"
            "请以JSON格式输出，包含以下字段：diagnosis_suggestion（初步诊断建议）、"
            "department（推荐科室，数组）、urgency（紧急程度）、advice（就医建议）。"
        )
    
    def _generate_symptom_description(
        self, 
        disease: Dict, 
        department: str,
        include_profile: bool = True
    ) -> str:
        """
        生成症状描述 (增强多样性版本)
        """
        templates = self.knowledge.get("symptom_templates", {})
        
        # 随机选择一种语气/人格 (Persona)
        # 1: 专业描述型, 2: 焦虑大白话型, 3: 简洁干练型, 4: 模糊口语型
        persona = random.randint(1, 4)
        
        # 选择症状（2-5个）
        symptoms = disease.get("symptoms", [])
        num_symptoms = min(random.randint(2, 5), len(symptoms))
        selected_symptoms = random.sample(symptoms, num_symptoms)
        
        symptom_phrases = []
        for symptom in selected_symptoms:
            time_desc = random.choice(templates.get("time_duration", ["最近", "刚才", "好几天"]))
            severity = random.choice(templates.get("severity", [""]) + ["", "非常", "有点", "特别"])
            
            if persona == 1: # 专业
                symptom_phrases.append(f"{time_desc}出现{severity}{symptom}")
            elif persona == 2: # 焦虑
                symptom_phrases.append(f"{severity}{symptom}了，已经{time_desc}了，很难受")
            elif persona == 3: # 简洁
                symptom_phrases.append(f"{symptom}{time_desc}")
            else: # 模糊
                symptom_phrases.append(f"感觉{symptom}")
        
        # 组合逻辑
        if persona == 2:
            description = "，".join(symptom_phrases) + "，医生快看看"
        else:
            description = "，".join(symptom_phrases)
            
        # 添加加重因素
        if random.random() > 0.4:
            agg = random.choice(templates.get("aggravating_factors", ["活动后加重"]))
            description += f"，{agg}"
            
        # 添加患者背景
        if include_profile and random.random() > 0.2:
            profiles = templates.get("patient_profiles", [])
            if profiles:
                p = random.choice(profiles)
                prefix = f"年龄{p['age']}，{p['gender']}，既往{p['history']}"
                description = f"{prefix}。{description}"
        
        endings = ["", "，怎么办？", "。请问去哪个科室？", "？急！", "。"]
        return description + random.choice(endings)
    
    def _determine_urgency(self, disease: Dict, symptoms_mentioned: List[str]) -> str:
        """
        根据症状确定紧急程度
        
        Args:
            disease: 疾病信息
            symptoms_mentioned: 提到的症状列表
        """
        urgency_levels = self.knowledge.get("urgency_levels", {})
        urgency_signs = disease.get("urgency_signs", [])
        
        # 检查是否有紧急征兆
        has_urgent_sign = any(
            sign.lower() in " ".join(symptoms_mentioned).lower() 
            for sign in urgency_signs
        )
        
        # 急诊科疾病通常需要立即就医
        if disease.get("name") in ["急性心肌梗死", "急性脑卒中", "过敏性休克"]:
            return urgency_levels.get("immediate", {}).get("label", "立即就医/拨打120")
        
        if has_urgent_sign:
            return urgency_levels.get("urgent", {}).get("label", "建议24小时内就医")
        
        # 根据疾病类型确定
        severity_map = {
            "肺炎": "urgent",
            "胆囊炎": "urgent",
            "骨折": "urgent",
            "异位妊娠": "immediate",
            "脑梗死": "immediate",
            "带状疱疹": "urgent",
            "高血压": "soon",
            "糖尿病": "soon",
        }
        
        disease_name = disease.get("name", "")
        level_key = severity_map.get(disease_name, "routine")
        
        return urgency_levels.get(level_key, {}).get("label", "择期就医")
    
    def _generate_advice(self, disease: Dict, urgency: str) -> str:
        """
        生成就医建议
        
        Args:
            disease: 疾病信息
            urgency: 紧急程度
        """
        advice_points = disease.get("advice", [])
        
        # 根据紧急程度添加前缀
        if "立即" in urgency or "120" in urgency:
            prefix = "这是紧急情况！请立即拨打120或前往最近医院急诊。"
        elif "24小时" in urgency:
            prefix = "建议尽快就医，不要拖延。"
        elif "3天" in urgency:
            prefix = "建议近期安排就诊。"
        else:
            prefix = ""
        
        # 添加检查建议
        examinations = disease.get("examinations", [])
        if examinations and random.random() > 0.5:
            exam_advice = f"建议完善{random.choice(examinations)}等检查"
            advice_points = advice_points + [exam_advice]
        
        # 组合建议
        if advice_points:
            numbered_advice = "; ".join([f"{i+1}. {a}" for i, a in enumerate(advice_points[:4])])
            return f"{prefix}{numbered_advice}" if prefix else numbered_advice
        
        return prefix if prefix else "请到医院就诊，由医生进行详细检查和诊断。"
    
    def _generate_output(
        self, 
        disease: Dict, 
        department: str,
        symptoms_mentioned: List[str]
    ) -> Dict:
        """
        生成标准化输出
        
        Args:
            disease: 疾病信息
            department: 所属科室
            symptoms_mentioned: 提到的症状
        """
        urgency = self._determine_urgency(disease, symptoms_mentioned)
        advice = self._generate_advice(disease, urgency)
        
        # 生成诊断建议
        disease_name = disease.get("name", "")
        risk_factors = disease.get("risk_factors", [])
        
        diagnosis_templates = [
            f"考虑{disease_name}可能，建议进一步检查确诊",
            f"症状提示{disease_name}可能性大，需排除其他相关疾病",
            f"根据症状描述，初步考虑{disease_name}",
            f"可能为{disease_name}，需结合检查结果明确诊断",
        ]
        diagnosis = random.choice(diagnosis_templates)
        
        # 确定推荐科室
        departments = [department]
        # 某些情况需要多科室会诊
        if "急诊" in urgency or "120" in urgency:
            if "急诊科" not in departments:
                departments.insert(0, "急诊科")
        
        return {
            "diagnosis_suggestion": diagnosis,
            "department": departments,
            "urgency": urgency,
            "advice": advice
        }
    
    def generate_sample(self, department: str, disease: Dict) -> Dict[str, str]:
        """
        生成单条训练样本
        
        Args:
            department: 科室名称
            disease: 疾病信息
        """
        # 生成输入
        input_text = self._generate_symptom_description(disease, department)
        
        # 检查去重
        if input_text in self.generated_inputs:
            return None
        self.generated_inputs.add(input_text)
        
        # 获取提到的症状
        symptoms = disease.get("symptoms", [])
        symptoms_mentioned = [s for s in symptoms if s in input_text]
        
        # 生成输出
        output = self._generate_output(disease, department, symptoms_mentioned)
        
        return {
            "instruction": self._get_random_instruction(),
            "input": input_text,
            "output": json.dumps(output, ensure_ascii=False)
        }
    
    def generate_dataset(
        self, 
        train_count: int = 2000, 
        test_count: int = 200,
        output_dir: str = "data"
    ) -> Dict[str, int]:
        """
        生成完整数据集
        
        Args:
            train_count: 训练集数量
            test_count: 测试集数量
            output_dir: 输出目录
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        all_samples = []
        departments = self.knowledge.get("departments", {})
        
        # 计算每个科室应生成的样本数
        total_count = train_count + test_count
        samples_per_dept = total_count // len(departments) + 1
        
        print(f"正在生成数据集...")
        print(f"目标: 训练集 {train_count} 条, 测试集 {test_count} 条")
        print(f"科室数量: {len(departments)}")
        
        for dept_name, dept_info in departments.items():
            diseases = dept_info.get("diseases", [])
            samples_per_disease = samples_per_dept // len(diseases) + 1
            
            for disease in diseases:
                for _ in range(samples_per_disease):
                    sample = self.generate_sample(dept_name, disease)
                    if sample:
                        all_samples.append(sample)
        
        # 打乱数据
        random.shuffle(all_samples)
        
        # 确保有足够的数据
        if len(all_samples) < total_count:
            print(f"警告: 生成数据 {len(all_samples)} 条，少于目标 {total_count} 条")
            # 复制数据直到达到目标
            while len(all_samples) < total_count:
                all_samples.extend(all_samples[:total_count - len(all_samples)])
        
        # 分割数据集
        train_samples = all_samples[:train_count]
        test_samples = all_samples[train_count:train_count + test_count]
        
        # 保存训练集
        train_path = output_path / "train.jsonl"
        with open(train_path, 'w', encoding='utf-8') as f:
            for sample in train_samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        
        # 保存测试集
        test_path = output_path / "test.jsonl"
        with open(test_path, 'w', encoding='utf-8') as f:
            for sample in test_samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        
        print(f"\n[OK] 数据生成完成!")
        print(f"   训练集: {train_path} ({len(train_samples)} 条)")
        print(f"   测试集: {test_path} ({len(test_samples)} 条)")
        
        return {
            "train_count": len(train_samples),
            "test_count": len(test_samples)
        }


def validate_dataset(data_dir: str = "data") -> bool:
    """
    验证数据集格式
    
    Args:
        data_dir: 数据目录
    """
    data_path = Path(data_dir)
    files = ["train.jsonl", "test.jsonl"]
    
    all_valid = True
    
    for filename in files:
        filepath = data_path / filename
        if not filepath.exists():
            print(f"[ERROR] 文件不存在: {filepath}")
            all_valid = False
            continue
        
        print(f"\n验证 {filename}...")
        
        line_count = 0
        error_count = 0
        format_errors = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line_count += 1
                try:
                    data = json.loads(line.strip())
                    
                    # 检查必需字段
                    required_fields = ["instruction", "input", "output"]
                    for field in required_fields:
                        if field not in data:
                            format_errors.append(f"行 {line_num}: 缺少字段 '{field}'")
                            error_count += 1
                    
                    # 检查 output 是否为有效 JSON
                    if "output" in data:
                        try:
                            output_data = json.loads(data["output"])
                            output_fields = ["diagnosis_suggestion", "department", "urgency", "advice"]
                            for field in output_fields:
                                if field not in output_data:
                                    format_errors.append(f"行 {line_num}: output 缺少字段 '{field}'")
                        except json.JSONDecodeError:
                            format_errors.append(f"行 {line_num}: output 不是有效的 JSON")
                            error_count += 1
                    
                except json.JSONDecodeError as e:
                    format_errors.append(f"行 {line_num}: JSON 解析错误 - {e}")
                    error_count += 1
        
        if error_count == 0:
            print(f"   [OK] {filename}: {line_count} 条数据，格式正确")
        else:
            print(f"   [ERROR] {filename}: {line_count} 条数据，{error_count} 条格式错误")
            for err in format_errors[:5]:  # 只显示前5个错误
                print(f"      {err}")
            all_valid = False
    
    return all_valid


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="医疗分诊训练数据生成器")
    parser.add_argument("--validate", action="store_true", help="验证数据格式")
    parser.add_argument("--train-count", type=int, default=2000, help="训练集数量")
    parser.add_argument("--test-count", type=int, default=200, help="测试集数量")
    parser.add_argument("--output-dir", type=str, default="data", help="输出目录")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    
    args = parser.parse_args()
    
    # 设置随机种子
    random.seed(args.seed)
    
    if args.validate:
        # 验证模式
        print("=" * 50)
        print("数据格式验证")
        print("=" * 50)
        success = validate_dataset(args.output_dir)
        if success:
            print("\n[OK] 所有数据格式正确!")
        else:
            print("\n[ERROR] 数据存在格式问题，请检查")
            exit(1)
    else:
        # 生成模式
        print("=" * 50)
        print("医疗分诊训练数据生成")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        generator = MedicalDataGenerator()
        stats = generator.generate_dataset(
            train_count=args.train_count,
            test_count=args.test_count,
            output_dir=args.output_dir
        )
        
        print("\n" + "=" * 50)
        print("统计信息:")
        print(f"   训练集: {stats['train_count']} 条")
        print(f"   测试集: {stats['test_count']} 条")
        print("=" * 50)


if __name__ == "__main__":
    main()
