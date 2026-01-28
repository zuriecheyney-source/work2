#!/bin/bash
# ============================================================
# 医疗分诊模型微调启动脚本
# 项目: MedicalTriage-Agent
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================================"
echo "医疗分诊模型微调"
echo "============================================================"

# 检查 LlamaFactory 是否安装
if ! command -v llamafactory-cli &> /dev/null; then
    echo -e "${RED}错误: LlamaFactory 未安装${NC}"
    echo "请运行以下命令安装:"
    echo "  git clone https://github.com/hiyouga/LLaMA-Factory.git"
    echo "  cd LLaMA-Factory && pip install -e ."
    exit 1
fi

# 检查 GPU
echo "检查 GPU 状态..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total --format=csv
else
    echo -e "${YELLOW}警告: 未检测到 NVIDIA GPU${NC}"
    echo "建议使用 GPU 进行训练"
fi

# 获取脚本目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 配置文件路径
CONFIG_FILE="${SCRIPT_DIR}/sft_config.yaml"
DATASET_INFO="${SCRIPT_DIR}/dataset_info.json"

# 检查配置文件
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}错误: 配置文件不存在: ${CONFIG_FILE}${NC}"
    exit 1
fi

# 检查数据集
if [ ! -f "${PROJECT_DIR}/data/train.jsonl" ]; then
    echo -e "${YELLOW}数据集不存在，正在生成...${NC}"
    python "${PROJECT_DIR}/scripts/generate_data.py"
fi

# 创建输出目录
mkdir -p "${PROJECT_DIR}/finetune/saves"
mkdir -p "${PROJECT_DIR}/finetune/logs"

echo ""
echo "配置信息:"
echo "  配置文件: ${CONFIG_FILE}"
echo "  数据目录: ${PROJECT_DIR}/data/"
echo "  输出目录: ${PROJECT_DIR}/finetune/saves"
echo ""

# 询问是否继续
read -p "是否开始训练? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "训练已取消"
    exit 0
fi

# 开始训练
echo ""
echo -e "${GREEN}开始训练...${NC}"
echo "============================================================"

# 设置环境变量
export CUDA_VISIBLE_DEVICES=0

# 运行训练
llamafactory-cli train "$CONFIG_FILE"

echo ""
echo "============================================================"
echo -e "${GREEN}训练完成!${NC}"
echo "模型保存在: ${PROJECT_DIR}/finetune/saves/medical-triage-lora"
echo "============================================================"
