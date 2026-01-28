# LlamaFactory 模型微调指南

## 概述

本模块使用 LlamaFactory 对基础大模型进行指令微调（SFT），使其具备专业的医疗分诊能力。

## 微调配置

### 基础模型选择

| 模型 | 参数量 | 显存需求 | 推荐场景 |
|------|--------|----------|----------|
| Qwen2-1.5B-Instruct | 1.5B | ~8GB | 演示/测试 |
| Qwen2-7B-Instruct | 7B | ~24GB | 生产环境 |
| Qwen2.5-7B-Instruct | 7B | ~24GB | 最佳效果 |

### 微调方法

- **方法**: LoRA (Low-Rank Adaptation)
- **优势**: 显存占用低，训练速度快，适合消费级 GPU
- **参数**: 
  - r = 8 (秩)
  - alpha = 16 (缩放因子)
  - dropout = 0.05

---

## 环境准备

### 1. 安装 LlamaFactory

```bash
# 克隆 LlamaFactory
git clone --depth 1 https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory

# 安装依赖
pip install -e ".[torch,metrics]"
```

### 2. GPU 环境检查

```bash
# 检查 CUDA 版本
nvidia-smi

# 检查 PyTorch CUDA 支持
python -c "import torch; print(torch.cuda.is_available())"
```

---

## 数据集配置

### 注册数据集

将以下内容添加到 LlamaFactory 的 `data/dataset_info.json`:

```json
{
  "medical_triage": {
    "file_name": "path/to/work2/data/train.jsonl",
    "formatting": "alpaca",
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "response": "output"
    }
  }
}
```

或者复制本项目的 `dataset_info.json` 到 LlamaFactory 的 data 目录。

---

## 训练配置说明

### sft_config.yaml 参数解释

```yaml
### 模型配置
model_name_or_path: Qwen/Qwen2-1.5B-Instruct  # 基础模型路径

### 微调方法
stage: sft                    # 监督微调阶段
do_train: true               # 执行训练
finetuning_type: lora        # 使用 LoRA 微调

### LoRA 参数
lora_target: all             # 对所有线性层应用 LoRA
lora_rank: 8                 # 低秩分解的秩
lora_alpha: 16               # LoRA 缩放因子
lora_dropout: 0.05           # Dropout 防止过拟合

### 数据集
dataset: medical_triage      # 数据集名称
template: qwen                # 对话模板

### 训练参数
output_dir: ./saves/medical-triage-lora  # 输出目录
per_device_train_batch_size: 4           # 批大小
gradient_accumulation_steps: 4           # 梯度累积
learning_rate: 2.0e-4                    # 学习率
num_train_epochs: 3                      # 训练轮数

### 优化设置
lr_scheduler_type: cosine    # 学习率调度器
warmup_ratio: 0.1            # 预热比例
bf16: true                   # 使用 BF16 混合精度

### 日志
logging_steps: 10             # 每 10 步记录日志
save_steps: 100               # 每 100 步保存检查点
```

---

## 运行训练

### 方式一：使用配置文件

```bash
cd LLaMA-Factory
llamafactory-cli train /path/to/work2/finetune/sft_config.yaml
```

### 方式二：使用脚本

```bash
cd /path/to/work2
bash finetune/train.sh
```

---

## 微调目标

通过微调，模型将学习以下能力：

### 1. 格式遵循能力
- 严格输出 JSON 格式
- 包含所有必需字段
- 字段内容结构化

### 2. 医学知识能力
- 症状-疾病关联
- 科室-疾病对应
- 紧急程度判断

### 3. 安全边界意识
- 不给出具体药物剂量
- 强调就医必要性
- 急症识别与警示

---

## 训练监控

### 查看训练日志

```bash
# 查看实时日志
tail -f saves/medical-triage-lora/trainer_log.jsonl
```

### 关键指标

| 指标 | 期望值 | 说明 |
|------|--------|------|
| train_loss | <0.5 | 训练损失应稳定下降 |
| eval_loss | <0.6 | 验证损失不应远高于训练损失 |
| learning_rate | 递减 | 应按 cosine 调度递减 |

---

## 模型导出

### 合并 LoRA 权重

```bash
llamafactory-cli export \
    --model_name_or_path Qwen/Qwen2-1.5B-Instruct \
    --adapter_name_or_path saves/medical-triage-lora \
    --export_dir models/medical-triage-merged \
    --template qwen
```

### 模型推理测试

```bash
llamafactory-cli chat \
    --model_name_or_path saves/medical-triage-lora \
    --adapter_name_or_path saves/medical-triage-lora \
    --template qwen
```

---

## 常见问题

### Q1: 显存不足 (OOM)

降低 batch_size 或使用梯度检查点:
```yaml
per_device_train_batch_size: 2
gradient_checkpointing: true
```

### Q2: 训练 loss 不下降

1. 检查数据格式是否正确
2. 尝试降低学习率
3. 检查模板是否匹配

### Q3: 没有 GPU

可以使用云 GPU 服务：
- AutoDL
- 阿里云 PAI
- Google Colab Pro
