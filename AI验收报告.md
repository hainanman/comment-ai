# AI 分析链路验收报告

> 日期：2026-10-28  
> 模型：通义千问 `qwen-plus`（阿里云百炼 OpenAI 兼容接口）  
> 配置：`AI_ENABLED=true`、`LLM_JSON_MODE=true`、超时 4 秒、不重试  
> 验收脚本：`acceptance.py`  
> 用例文件：`data/acceptance_cases.csv`  
> 原始结果：`data/acceptance_results.json`

## 1. 结论

10 条典型评论全部通过：

| 指标 | 结果 |
|---|---|
| 状态正确（发布/复核/驳回） | **10/10** |
| 违规类型正确 | **10/10** |
| 情感判别正确 | **10/10** |
| 模型参与 | 8 条；规则直接拦截 2 条 |
| 平均模型耗时 | **2212 ms** |
| 总平均耗时 | **1770 ms** |
| 最慢单条 | **2399 ms** |
| 是否超过 5 秒目标 | 否 |

Web 路由联调同时验证：10 条评论均返回 302，均成功写入 `comments` 和 `analysis_traces`，`trace.decision` 与评论最终状态一致。

MySQL + 真实 CSRF 联调也已通过：MySQL 8.0.42、`comment_ai` 库、root 连接；无 token 的 POST 返回 400，带 token 正常提交；真实评论写入 `comments` + `analysis_traces`；申诉 #10 后审核员通过，状态变为 `published` 且 `appeal_status=handled`；管理员 `/admin/users` 正常，访问 `/review/` 返回 403。

## 2. 逐条结果

| # | 用例 | 期望（状态 / 类型 / 情感） | 实际（状态 / 类型 / 情感） | 引擎 | 耗时 |
|---|---|---|---|---|---|
| 1 | 正常好评 | published / none / positive | published / none / positive | llm | 2298ms |
| 2 | 普通差评 | published / none / negative | published / none / negative | llm | 1949ms |
| 3 | 中性评价 | published / none / neutral | published / none / neutral | llm | 2184ms |
| 4 | 广告引流 | rejected / ad / neutral | rejected / ad / neutral | rule | 1ms |
| 5 | 刷单返利 | rejected / fraud / neutral | rejected / fraud / neutral | llm | 2257ms |
| 6 | 辱骂攻击 | rejected / abuse / negative | rejected / abuse / negative | llm | 2227ms |
| 7 | 反讽差评 | published / none / negative | published / none / negative | llm | 2190ms |
| 8 | 无关内容 | reviewing / irrelevant / neutral | reviewing / irrelevant / neutral | llm | 2193ms |
| 9 | 虚假宣传 | reviewing / false_promo / positive | reviewing / false_promo / positive | llm | 2399ms |
| 10 | 直接拦截 | rejected / other / neutral | rejected / other / neutral | rule | 1ms |

## 3. 本轮修正

第一轮状态正确 8/10（刷单返利、无关内容被转人工/放行不一致），修正后 10/10。主要修正两类问题：

1. **刷单/无关内容被低估风险**
   - `好评返现` 模型给 0.60，原逻辑会转人工；`无关内容` 模型给 0.10，原逻辑会直接发布。
   - 现在：`ad/fraud/abuse` 属于硬违规类型，风险 ≥ 0.50 即驳回；其他 `violation_type != none` 至少转人工，不允许直接发布。
2. **规则直接拦截的类型不准确**
   - 原 `加V` / 违法服务类词都归为 `other`，前者应为 `ad`。
   - 现在：规则层按命中词做类型映射（广告、刷单、辱骂、虚假宣传、违法服务），并保持“违法服务优先于联系方式”的判断。
3. **Prompt 增加风险分参考**
   - 明确广告/刷单/辱骂 ≥ 0.85，边界/无关/虚假宣传 0.50—0.84，正常 < 0.50。

对应代码：

- `app/ai/pipeline.py`：`HARD_VIOLATIONS`、`_rule_violation`、`_rule_decision`、`decide`
- `app/ai/llm.py`：Prompt 第 7 条风险分参考
- `tests/test_decision.py`：硬违规、非 none 至少复核的边界测试

## 4. 关键观察

- 反讽识别有效：`戴了一天耳朵就发炎，这耳机真是绝了` 判为 negative，且 `is_sarcasm=true`，未误判违规。
- 普通差评未被误杀：`用了三天就断连...` 判为 negative，但 violation_type=none，正常发布。
- 直接拦截有效：`加V` 和违法服务类词均跳过模型，约 1ms 返回，节省 token。
- 无关内容、虚假宣传进入 `reviewing`，符合“边界内容人工兜底”。
- 所有模型调用均成功解析 JSON，`response_format=json_object` 在当前接口可用。
- 单条 2.1—2.8 秒，低于 5 秒目标；直接拦截几乎无延迟。

## 5. 复现方式

```powershell
cd "M:\work\Vibe Coding\deep\comment-ai"
python acceptance.py
```

只跑前 3 条：

```powershell
python acceptance.py --limit 3
```

输出会写入 `data/acceptance_results.json`；如果有任何状态/类型/情感不一致，脚本以非 0 退出。

## 6. 局限与下一步

- 本轮只有 10 条人工设计用例，不是 120 条评测集；不能据此宣称 85%/90% 的总体指标。
- 只跑了一轮，模型存在随机性；论文中应固定测试集、固定阈值、记录原始结果。
- 当前环境未安装 Flask-WTF，联调使用项目内置的 session CSRF 兜底；安装 Flask-WTF 后会自动切换，建议再用正式依赖跑一次表单提交。
- 下一步：
  1. 扩充到 120 条标注集，覆盖更多反讽、谐音广告、软广、短文本中性。
  2. 统计混淆矩阵、精确率/召回率/F1。
  3. 用 `evaluate.py` 跑“纯规则 vs 双引擎”对比。
  4. 针对误判样本调整 Prompt 或敏感词表，而不是改测试数据。
