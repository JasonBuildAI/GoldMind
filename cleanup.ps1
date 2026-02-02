# GoldMind - Cleanup Script
# 清理不必要的文件，减小项目体积

Write-Host "🧹 Cleaning up project..." -ForegroundColor Green

# 1. 清理前端 node_modules（可以重新安装）
Write-Host "📦 Cleaning node_modules..." -ForegroundColor Yellow
if (Test-Path "app\node_modules") {
    Remove-Item -Recurse -Force "app\node_modules"
    Write-Host "   ✓ Removed app/node_modules" -ForegroundColor Green
}

# 2. 清理Python缓存
Write-Host "🐍 Cleaning Python cache..." -ForegroundColor Yellow
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -File -Filter "*.pyc" | Remove-Item -Force
Write-Host "   ✓ Removed Python cache files" -ForegroundColor Green

# 3. 清理测试数据文件（保留结构）
Write-Host "🗂️  Cleaning test data files..." -ForegroundColor Yellow
$testFiles = @(
    "test_*.json",
    "*_result.json",
    "*.csv"
)
foreach ($pattern in $testFiles) {
    Get-ChildItem -Recurse -File -Filter $pattern | ForEach-Object {
        Remove-Item $_.FullName -Force
        Write-Host "   ✓ Removed $($_.Name)" -ForegroundColor Gray
    }
}

# 4. 清理dist目录（可以重新构建）
Write-Host "🏗️  Cleaning build artifacts..." -ForegroundColor Yellow
if (Test-Path "app\dist") {
    Remove-Item -Recurse -Force "app\dist"
    Write-Host "   ✓ Removed app/dist" -ForegroundColor Green
}

# 5. 显示清理后的体积
Write-Host "`n📊 Project size after cleanup:" -ForegroundColor Cyan
Get-ChildItem -Directory | ForEach-Object { 
    $size = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB
    [PSCustomObject]@{ Folder = $_.Name; SizeMB = [math]::Round($size, 2) } 
} | Format-Table -AutoSize

Write-Host "`n✅ Cleanup complete!" -ForegroundColor Green
Write-Host "`nTo restore dependencies:" -ForegroundColor Cyan
Write-Host "  cd app && npm install" -ForegroundColor White
Write-Host "  cd backend && pip install -r requirements.txt" -ForegroundColor White
