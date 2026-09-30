# GoldMind - 清理脚本
#
# ⚠️ 本文件必须保存为 **UTF-8 with BOM**。
#    含中文的 .ps1 若存成 UTF-8 无 BOM，Windows PowerShell 会按 GBK 解析，
#    中文字节里可能出现被当成引号/花括号的字节，直接报语法错误。
#
# 删除可重新生成的产物，减小项目体积。
#
# 安全设计（原实现有严重问题）：
#   - 原实现用 `Get-ChildItem -Recurse -Filter "*.csv"` 递归删除**全盘** CSV，
#     会把 node_modules 里的文件和用户自己的数据一起删掉；`test_*.json` 同理。
#     这两条已**移除**：清理脚本不该猜哪些用户文件是垃圾。
#   - 所有操作现在都限制在项目根目录内，并跳过 node_modules / .venv / .git 等目录。
#   - 支持 PowerShell 标准的 -WhatIf，可先预览再执行。
#
# 用法：
#   .\cleanup.ps1                        # 执行清理
#   .\cleanup.ps1 -WhatIf                # 只预览会删什么
#   .\cleanup.ps1 -IncludeDependencies   # 额外删除 node_modules（恢复需 npm ci）
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$Root = $PSScriptRoot,
    [switch]$IncludeDependencies
)

$ErrorActionPreference = 'Stop'

# 这些目录名出现在路径的任意一段就跳过
$SkipDirs = @(
    'node_modules', '.venv', 'venv', 'env', '.git',
    'dist', 'build', '__pycache__', 'test-results', 'playwright-report'
)

function Test-Skipped {
    param([System.IO.FileSystemInfo]$Item)
    $rel = $Item.FullName.Substring($Root.Length).TrimStart('\', '/')
    foreach ($part in ($rel -split '[\\/]')) {
        if ($SkipDirs -contains $part) { return $true }
    }
    return $false
}

function Remove-ProjectPath {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Host "  $Label 不存在"
        return
    }
    # 只有真的删了才说「已删除」；-WhatIf 下 ShouldProcess 返回 false
    if ($PSCmdlet.ShouldProcess($Path, 'Remove')) {
        Remove-Item -LiteralPath $Path -Recurse -Force
        Write-Host "  已删除 $Label"
    }
}

Write-Host "GoldMind 清理（项目根目录: $Root）" -ForegroundColor Green
if ($WhatIfPreference) { Write-Host "  —— 预览模式（-WhatIf），不会真正删除 ——" -ForegroundColor Magenta }

Write-Host "`n[1/4] Python 缓存" -ForegroundColor Yellow
$pycDirs = Get-ChildItem -LiteralPath $Root -Recurse -Force -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
    Where-Object { -not (Test-Skipped $_) }
foreach ($d in $pycDirs) {
    if ($PSCmdlet.ShouldProcess($d.FullName, 'Remove')) {
        Remove-Item -LiteralPath $d.FullName -Recurse -Force
    }
}
Write-Host ("  __pycache__: {0} 个" -f $pycDirs.Count)

$pycFiles = Get-ChildItem -LiteralPath $Root -Recurse -Force -File -Filter '*.pyc' -ErrorAction SilentlyContinue |
    Where-Object { -not (Test-Skipped $_) }
foreach ($f in $pycFiles) {
    if ($PSCmdlet.ShouldProcess($f.FullName, 'Remove')) {
        Remove-Item -LiteralPath $f.FullName -Force
    }
}
Write-Host ("  *.pyc: {0} 个" -f $pycFiles.Count)

Write-Host "`n[2/4] 构建产物" -ForegroundColor Yellow
Remove-ProjectPath -Path (Join-Path $Root 'app\dist') -Label 'app/dist'

Write-Host "`n[3/4] 端到端测试产物" -ForegroundColor Yellow
foreach ($rel in @('backend\e2e.db', 'backend\e2e-cache', 'app\test-results', 'app\playwright-report')) {
    Remove-ProjectPath -Path (Join-Path $Root $rel) -Label $rel
}

if ($IncludeDependencies) {
    Write-Host "`n[附加] 前端依赖（恢复：cd app && npm ci）" -ForegroundColor Yellow
    Remove-ProjectPath -Path (Join-Path $Root 'app\node_modules') -Label 'app/node_modules'
}

Write-Host "`n[4/4] 项目体积" -ForegroundColor Cyan
Get-ChildItem -LiteralPath $Root -Directory -Force |
    Where-Object { $_.Name -ne '.git' } |
    ForEach-Object {
        $size = (Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum / 1MB
        [PSCustomObject]@{ Folder = $_.Name; SizeMB = [math]::Round($size, 2) }
    } | Sort-Object SizeMB -Descending | Format-Table -AutoSize

Write-Host "完成。恢复依赖：" -ForegroundColor Green
Write-Host "  cd app && npm ci"
Write-Host "  cd backend && pip install -r requirements.txt -r requirements-dev.txt"
