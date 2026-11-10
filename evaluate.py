"""小型评测脚本：纯规则 vs 双引擎。

用法：
    python evaluate.py --csv data/eval_set_sample.csv --mode rule
    python evaluate.py --csv data/eval_set_sample.csv --mode dual --limit 10
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app import create_app
from app.ai.pipeline import analyze_comment
from app.ai.rules import unescape_text

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(ROOT / "data" / "eval_set_sample.csv"))
    parser.add_argument("--mode", choices=["rule", "dual"], default="rule")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    path = Path(args.csv)
    if not path.exists():
        raise SystemExit(f"评测文件不存在：{path}")

    app = create_app()
    app.config["AI_ENABLED"] = args.mode == "dual"
    app.config["DAILY_LLM_LIMIT"] = 0

    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if args.limit > 0:
        rows = rows[: args.limit]
    if not rows:
        raise SystemExit("评测文件没有数据")

    tp = fp = fn = tn = 0
    sentiment_ok = 0
    latencies = []
    engines = {"llm": 0, "rule": 0, "rule_fallback": 0}

    with app.app_context():
        for row in rows:
            content = unescape_text((row.get("content") or "").strip())
            target = (row.get("target_name") or "商品").strip()
            result = analyze_comment(content, target)
            latencies.append(result.analysis_ms)
            engines[result.engine] = engines.get(result.engine, 0) + 1

            true_sentiment = (row.get("sentiment_label") or "").strip()
            if result.sentiment == true_sentiment:
                sentiment_ok += 1

            true_violation = str(row.get("violation_label") or "0").strip() == "1"
            pred_violation = result.violation_type != "none"
            if true_violation and pred_violation:
                tp += 1
            elif not true_violation and pred_violation:
                fp += 1
            elif true_violation and not pred_violation:
                fn += 1
            else:
                tn += 1

            if args.verbose:
                print(
                    f"{row.get('id', '-'):>3} | true={true_sentiment}/{true_violation} "
                    f"pred={result.sentiment}/{pred_violation} | {result.engine} | {result.status}"
                )

    total = len(rows)
    accuracy = sentiment_ok / total
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    print(f"\n模式：{args.mode}（AI_ENABLED={app.config['AI_ENABLED']}）")
    print(f"样本：{total}")
    print(f"情感准确率：{accuracy:.2%} ({sentiment_ok}/{total})")
    print(f"违规精确率：{precision:.2%}  召回率：{recall:.2%}  F1：{f1:.2%}")
    print(f"混淆计数：TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"平均分析耗时：{avg_latency:.0f} ms")
    print(f"引擎分布：{engines}")
    if args.mode == "dual" and engines.get("rule_fallback", 0):
        print("提示：存在 rule_fallback，说明模型未配置/网络失败，已按规则兜底。")


if __name__ == "__main__":
    main()
