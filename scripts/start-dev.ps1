param(
  [string]$TaskLabel = 'dev:start-all',
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName Microsoft.VisualBasic
Add-Type -AssemblyName System.Windows.Forms

function Write-Step {
  param([string]$Message)
  Write-Host "[start-dev] $Message" -ForegroundColor Cyan
}

function Find-CodeWindow {
  param([string]$WorkspaceName)

  $windows = Get-Process Code -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle } |
    Sort-Object StartTime -Descending

  $matched = $windows | Where-Object { $_.MainWindowTitle -like "*$WorkspaceName*" } | Select-Object -First 1
  if ($matched) {
    return $matched
  }

  return $windows | Select-Object -First 1
}

function Send-TextSlowly {
  param([string]$Text)

  foreach ($char in $Text.ToCharArray()) {
    [System.Windows.Forms.SendKeys]::SendWait($char)
    Start-Sleep -Milliseconds 25
  }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$workspaceName = Split-Path $repoRoot -Leaf
$codeWindow = Find-CodeWindow -WorkspaceName $workspaceName

if (-not $codeWindow) {
  throw '未找到可用的 VS Code 窗口。请先在 VS Code 中打开当前仓库，再运行此脚本。'
}

Write-Step "定位到 VS Code 窗口: $($codeWindow.MainWindowTitle)"

if ($DryRun) {
  Write-Step "DryRun: 将激活该窗口并触发 Tasks: Run Task -> $TaskLabel"
  exit 0
}

[Microsoft.VisualBasic.Interaction]::AppActivate($codeWindow.Id) | Out-Null
Start-Sleep -Milliseconds 400

Write-Step "触发 Tasks: Run Task -> $TaskLabel"
[System.Windows.Forms.SendKeys]::SendWait('{F1}')
Start-Sleep -Milliseconds 300
Send-TextSlowly -Text 'Tasks: Run Task'
Start-Sleep -Milliseconds 250
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
Start-Sleep -Milliseconds 400
Send-TextSlowly -Text $TaskLabel
Start-Sleep -Milliseconds 250
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')

Write-Step '已请求 VS Code 打开集成终端并启动任务。'
