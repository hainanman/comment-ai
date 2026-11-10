# 基于 AI 的评论管理系统（框架版）

低频、单机、答辩优先的 Flask 评论管理系统。当前仓库是**可运行骨架**，已包含：

- 登录/注册/三角色权限
- 商品列表（真实商品图 + 评论数/评分/好评率/RI）、商品详情（整体情感倾向 + RI + 趋势 + 关键词语义筛选）、商品页内联写评论
- 评论广场、我的评论、结果页
- 规则初筛（DFA + 正则）+ qwen-plus 终审 + JSON 校验 + 规则兜底
- 情感判别：qwen-plus 主判 + 规则否定/程度/反讽/表情兜底
- 关键词提取（jieba，缺失时正则兜底）
- 审核员待复核 + 极简申诉复审
- 管理员用户管理（仅此一项）
- 登录可见只读数据概览（ECharts，缺失时 HTML 兜底）
- 情感倾向：趋势、商品负向率、负面关键词、负向预警
- 三张表：`users` / `comments` / `analysis_traces`
- 演示数据脚本、评测脚本、基础测试

> 详细设计见 `../PRD_基于AI的评论管理系统.md` 和 `../技术文档_基于AI的评论管理系统.md`。

## 1. 快速启动

### 1.1 安装依赖

```powershell
cd "M:\work\Vibe Coding\deep\comment-ai"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

如果 PowerShell 禁止激活脚本：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

### 1.2 配置

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少填：

- `FLASK_SECRET_KEY`：随机字符串
- `DATABASE_URL`：MySQL 连接串
- `DASHSCOPE_API_KEY`：阿里云百炼 Key（没有也能跑纯规则模式）

### 1.3 初始化 MySQL

用 root 执行项目自带脚本：

```powershell
mysql -u root -p < sql/init_mysql.sql
```

脚本会创建 `comment_ai` 库和 `comment_ai@127.0.0.1` 本地账号（密码 `change-me`，仅本地开发用）。执行后把 `.env` 里的数据库密码改成一致。

### 1.4 建表 + 演示数据

```powershell
python seed.py
```

重建演示数据：

```powershell
python seed.py --reset
```

### 1.5 启动

开发模式：

```powershell
flask --app wsgi run --debug
```

演示/低频运行：

```powershell
waitress-serve --listen=127.0.0.1:8000 --threads=8 wsgi:app
```

打开 `http://127.0.0.1:8000`。

### 1.6 演示账号

| 角色 | 用户名 | 密码 | 能做什么 |
|---|---|---|---|
| 管理员 | `admin` | `admin123` | 只做用户管理 |
| 审核员 | `reviewer` | `reviewer123` | 待复核、申诉复审 |
| 普通用户 | `user` | `user123` | 发评论、看状态、申诉 |

> 仅用于答辩，上线前必须改强密码。

## 2. 没有 MySQL / 没有网络时

### 2.1 用 SQLite 冒烟

```powershell
$env:DATABASE_URL="sqlite:///comment_ai.db"
$env:AI_ENABLED="false"
python seed.py --reset
flask --app wsgi run --debug
```

SQLite 只用于本地冒烟；论文/答辩按 MySQL 写。

### 2.2 没有 API Key

`AI_ENABLED=false` 或留空 Key，系统会走纯规则：

- DFA 敏感词 + 正则
- 情感词典
- jieba 关键词
- 规则阈值分流

不会因为模型不可用而 500。

## 3. 目录

```text
comment-ai/
  app/
    __init__.py          # 应用工厂、错误处理、日志、健康检查
    extensions.py        # db / csrf（Flask-WTF 或内置兜底）
    csrf.py              # 未安装 Flask-WTF 时的 session CSRF
    models.py            # 三张表
    auth/                # 注册登录 + 角色装饰器
    comment/             # 发布/广场/我的评论/申诉
    product/             # 商品列表/商品详情
    review/              # 待复核/申诉复审/详情
    admin/               # 用户管理
    stats/               # 只读数据概览 + 情感倾向 + JSON
    stats/sentiment.py   # 情感倾向聚合（趋势/商品/关键词/预警）
    catalog.py           # 8 件演示商品 + 评论模板/关键词
    ai/                  # rules / sentiment / llm / keywords / pipeline
    templates/           # Jinja2 页面（含 products/、dashboard/sentiment.html）
    static/               # CSS / JS / 商品图 / vendor（含 sentiment.js、product-reviews.js）
  data/                  # 敏感词、情感词典、停用词、验收/评测数据
  sql/                   # MySQL 首次初始化脚本
  tests/                 # pytest 基础测试
  seed.py
  evaluate.py
  acceptance.py          # 10 条真实 AI 验收
  AI验收报告.md          # 真实 qwen-plus 验收结果
  config.py
  wsgi.py
```

## 4. 关键路由

| 路由 | 权限 | 说明 |
|---|---|---|
| `/` | 公开 | 评论广场 |
| `/products` | 公开 | 商品列表 |
| `/products/<slug>` | 公开 | 商品详情 + 商品情感倾向 + 已发布评论 |
| `/login` `/register` | 公开 | 登录/注册 |
| `POST /products/<slug>/comments` | 普通用户 | 商品详情页内联表单提交评论 |
| `/my/comments` | 普通用户 | 我的评论/申诉 |
| `/comments/<id>/appeal` | 普通用户 | 一键申诉 |
| `/dashboard` | 登录 | 只读数据概览 |
| `/dashboard?tab=sentiment` | 登录 | 情感倾向：趋势/商品/关键词/预警 |
| `/api/dashboard/summary` | 登录 | 概览 JSON |
| `/api/dashboard/sentiment` | 登录 | 情感倾向 JSON |
| `/review` | 审核员 | 待复核 |
| `/review/appeals` | 审核员 | 申诉复审 |
| `/review/<id>` | 审核员 | 复核详情 |
| `/admin/users` | 管理员 | 用户管理 |
| `/healthz` | 本地公开 | 健康检查 |

> 商品目录是 `app/catalog.py` 里的静态演示数据，不建第四张表；评论通过 `target_name` 关联商品，提交时只能从目录下拉框选择，避免商品名、评论内容和关键词对不上。

## 5. 测试与评测

```powershell
pytest -q
python acceptance.py
python evaluate.py --csv data/eval_set_sample.csv --mode rule
python evaluate.py --csv data/eval_set_sample.csv --mode dual --limit 10
```

`acceptance.py` 会真实调用 qwen-plus，跑 10 条验收用例并输出 `data/acceptance_results.json`。  
`dual` 模式会真实调用 qwen-plus；没有 Key 会自动走规则兜底，结果会标注。

单独查看一条文本的规则情感结果：

```powershell
python -m flask --app wsgi sentiment "非常满意，物流也很快"
```

AI 验收详情见 [AI验收报告.md](<AI验收报告.md>)。

## 6. 已验证

当前骨架已做以下本地检查：

- Python 语法编译通过
- `dashboard.js` 语法检查通过
- SQLite 冒烟：登录、发评论、申诉、审核员复审、管理员权限、数据概览
- `seed.py` 生成 3 个账号 / **970 条评论 / 970 条 AI 轨迹**（每商品 120 条，评论内容去重）
- `pytest`：28 个规则、情感、JSON 解析、决策边界测试通过
- 情感倾向页/API：全部/一年内/半年内、按月趋势、8 个商品、差评关键词、商品筛选均通过
- 商品详情：每商品 120+ 条已发布评论；好评/中评/差评筛选、关键词模糊筛选和 AJAX 局部刷新均通过
- **真实 qwen-plus 验收**：10/10 状态、10/10 类型、10/10 情感；模型平均 2.21 秒
- **MySQL 8.0.42 联调**：建表、seed 970 条、真实评论写入、申诉复审、管理员/看板均通过
- **真实 CSRF 校验**：无 token 的 POST 返回 400，带 token 正常提交
- Web 路由联调：评论写入 `comments` + `analysis_traces`，无 500
- 商品页内联评论表单：登录用户提交后进入结果页；短正文返回 400 并回填；旧 `/comments/new` 返回 404

> 环境未安装 Flask-WTF 时，项目自动使用 `app/csrf.py` 的 session CSRF 兜底；安装 Flask-WTF 后自动切换，表单行为一致。

## 7. 前端资源

模板默认引用 `app/static/vendor/` 下的 Bootstrap/ECharts；如果你的环境没有这些文件：

- 模板会自动回退到 CDN；
- 数据概览会回退到 HTML 条形图；
- 答辩前建议执行 `.\download_vendor.ps1` 把资源下载到本地，避免现场断网。

商品主图已下载到 `app/static/images/products/*.jpg`，本地优先、完全离线可用；加载失败时再回退到远程 Unsplash 图和本地 SVG。  
`catalog.py` 中 `photo_local` 是本地实拍图，`photo` 是远程兜底地址。

## 8. 当前边界

- 管理员只做用户管理，没有词库/策略/日志后台。
- 人工复核只改当前状态，不记录审核人/时间/理由，没有审核历史。
- 申诉只做“按钮 → 审核员可见 → 复审”，每条评论一次。
- 不引入 Redis/Celery/Docker；低频单机同步链路。
- 生产上线前需要补：HTTPS、限流、审计、隐私政策、完整申诉、备份自动化。
