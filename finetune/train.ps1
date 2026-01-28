# ============================================================
# Medical Triage Model Fine-tuning Script (Windows PowerShell)
# Project: MedicalTriage-Agent
# ============================================================

# Fix encoding issues
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Medical Triage Fine-tuning" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Check LlamaFactory installation
if (-not (Get-Command llamafactory-cli -ErrorAction SilentlyContinue)) {
    Write-Host "Error: LlamaFactory not installed" -ForegroundColor Red
    Write-Host "Please run: cd ..\LLaMA-Factory; pip install -e ."
    exit 1
}

# Check GPU
Write-Host "Checking GPU status..."
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    nvidia-smi --query-gpu=name,memory.total --format=csv
} else {
    Write-Host "Warning: NVIDIA GPU not detected" -ForegroundColor Yellow
    Write-Host "GPU is highly recommended for training"
}

# Get directory paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = Split-Path -Parent $ScriptDir

# Config file paths
$ConfigFile = Join-Path $ScriptDir "sft_config.yaml"
$DatasetInfo = Join-Path $ScriptDir "dataset_info.json"

# Check config file
if (-not (Test-Path $ConfigFile)) {
    Write-Host "Error: Config file not found: $ConfigFile" -ForegroundColor Red
    exit 1
}

# Check dataset
$TrainData = Join-Path $ProjectDir "data\train.jsonl"
if (-not (Test-Path $TrainData)) {
    Write-Host "Dataset not found, generating..." -ForegroundColor Yellow
    python (Join-Path $ProjectDir "scripts\generate_data.py")
}

# Create output directories
$SaveDir = Join-Path $ScriptDir "saves"
$LogDir = Join-Path $ScriptDir "logs"
if (-not (Test-Path $SaveDir)) { New-Item -ItemType Directory -Path $SaveDir | Out-Null }
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

Write-Host ""
Write-Host "Configuration:"
Write-Host "  Config: $ConfigFile"
Write-Host "  Data: $(Join-Path $ProjectDir 'data')"
Write-Host "  Output: $SaveDir"
Write-Host ""

# Ask to continue
$Confirmation = Read-Host "Start training? (y/n)"
if ($Confirmation -ne "y") {
    Write-Host "Training cancelled"
    exit 0
}

Write-Host ""
Write-Host "Starting training..." -ForegroundColor Green
Write-Host "============================================================"

# Set env vars
# Explicitly add LLaMA-Factory to PYTHONPATH
$env:PYTHONPATH = "E:\AgentAI\LLaMA-Factory\src" + [IO.Path]::PathSeparator + $env:PYTHONPATH

# Robust Python path detection
$PossiblePythonPaths = @(
    "D:\miniconda3\python.exe",
    (Get-Command python -ErrorAction SilentlyContinue).Source,
    "python"
)

$FinalPython = ""
foreach ($p in $PossiblePythonPaths) {
    if ($p -and (Test-Path $p)) {
        $FinalPython = $p
        break
    }
}

Write-Host "Using Python: $FinalPython" -ForegroundColor Gray

# Print environment diagnostic
Write-Host "--- Environment Diagnostic ---" -ForegroundColor Gray
& $FinalPython -m llamafactory.cli env
Write-Host "-----------------------------" -ForegroundColor Gray

# Run training
if ($FinalPython) {
    & $FinalPython -m llamafactory.cli train "$ConfigFile"
} else {
    Write-Host "Error: Could not find python interpreter." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================================"
Write-Host "Training Completed!" -ForegroundColor Green
Write-Host "Model saved at: $(Join-Path $SaveDir 'medical-triage-lora')"
Write-Host "============================================================"
