# vendor 静态资源

把以下文件放在本目录，页面优先使用本地文件，避免答辩现场断网：

- `bootstrap.min.css`
- `bootstrap.bundle.min.js`
- `echarts.min.js`

可以运行项目根目录的：

```powershell
.\download_vendor.ps1
```

如果文件不存在，模板会自动回退到 CDN；数据概览会回退为 HTML 条形图。
