# Medical Triage Model Verification
# Using absolute paths and no complex arrays to avoid parser issues

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PythonPath = "D:\miniconda3\python.exe"
$AdapterPath = Join-Path $ScriptDir "saves\medical-triage-lora"
$env:PYTHONPATH = "E:\AgentAI\LLaMA-Factory\src" + [IO.Path]::PathSeparator + $env:PYTHONPATH

Write-Host "Starting interactive chat with fine-tuned model..."
Write-Host "Model: Qwen2-1.5B-Instruct + LoRA Adapter"
Write-Host "------------------------------------------------"

# Execute in the most basic way possible
$Cmd = "$PythonPath -m llamafactory.cli chat --model_name_or_path Qwen/Qwen2-1.5B-Instruct --adapter_name_or_path $AdapterPath --template qwen --finetuning_type lora"
Invoke-Expression $Cmd
