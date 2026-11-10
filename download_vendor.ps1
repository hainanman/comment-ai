# 下载前端静态资源，供答辩断网时使用
$ErrorActionPreference = "Stop"
$root = Join-Path $PSScriptRoot "app\static\vendor"
New-Item -ItemType Directory -Force -Path $root | Out-Null

$items = @(
  @{ Url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"; Out = Join-Path $root "bootstrap.min.css" },
  @{ Url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"; Out = Join-Path $root "bootstrap.bundle.min.js" },
  @{ Url = "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"; Out = Join-Path $root "echarts.min.js" }
)

foreach ($item in $items) {
  try {
    Write-Host "下载 $($item.Url)"
    Invoke-WebRequest -Uri $item.Url -OutFile $item.Out -UseBasicParsing -TimeoutSec 60
    Write-Host "  -> $($item.Out)"
  } catch {
    Write-Warning "下载失败：$($item.Url) :: $($_.Exception.Message)"
  }
}

Write-Host "完成。若文件不存在，页面会自动回退到 CDN。"
