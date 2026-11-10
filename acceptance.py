"""10 条 AI 验收用例（真实调用 qwen-plus）。

用法：
    python acceptance.py
    python acceptance.py --limit 3
    python acceptance.py --csv data/acceptance_cases.csv --out data/acceptance_results.json
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean

from app import create_app
from app.ai.pipeline import analyze_comment
from app.ai.rules import unescape_text

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(ROOT / "data" / "acceptance_cases.csv"))
    parser.add_argument("--out", default=str(ROOT / "data" / "acceptance_results.json"))
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"验收文件不存在：{csv_path}")

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    if args.limit > 0:
        rows = rows[: args.limit]
    if not rows:
        raise SystemExit("验收文件没有数据")

    app = create_app()
    results = []
    with app.app_context():
        for row in rows:
            result = analyze_comment(
                unescape_text((row.get("content") or "").strip()),
                (row.get("target_name") or "商品").strip(),
            )
            expected_status = (row.get("expected_status") or "").strip()
            expected_type = (row.get("expected_type") or "").strip()
            expected_sentiment = (row.get("expected_sentiment") or "").strip()
            item = {
                "name": row.get("name") or "",
                "content": row.get("content") or "",
                "expected_status": expected_status,
                "expected_type": expected_type,
                "expected_sentiment": expected_sentiment,
                "status": result.status,
                "violation_type": result.violation_type,
                "sentiment": result.sentiment,
                "risk_score": round(float(result.risk_score), 3),
                "engine": result.engine,
                "analysis_ms": result.analysis_ms,
                "keywords": result.keywords,
                "reason": result.reason,
            }
            item["status_ok"] = result.status == expected_status
            item["type_ok"] = result.violation_type == expected_type
            item["sentiment_ok"] = result.sentiment == expected_sentiment
            results.append(item)
            print(
                f"{item['name']}: status={result.status} type={result.violation_type} "
                f"sentiment={result.sentiment} engine={result.engine} "
                f"risk={result.risk_score} {result.analysis_ms}ms"
            )

    total = len(results)
    status_ok = sum(1 for r in results if r["status_ok"])
    type_ok = sum(1 for r in results if r["type_ok"])
    sentiment_ok = sum(1 for r in results if r["sentiment_ok"])
    llm_latencies = [r["analysis_ms"] for r in results if r["engine"] == "llm"]
    all_latencies = [r["analysis_ms"] for r in results]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== 验收汇总 =====")
    print(f"样本：{total}")
    print(f"状态正确：{status_ok}/{total}")
    print(f"类型正确：{type_ok}/{total}")
    print(f"情感正确：{sentiment_ok}/{total}")
    avg_llm = mean(llm_latencies) if llm_latencies else 0
    print(f"模型参与：{len(llm_latencies)} 次；平均模型耗时：{avg_llm:.0f} ms")
    print(f"总平均耗时：{mean(all_latencies):.0f} ms；最慢：{max(all_latencies)} ms")
    print(f"结果已写入：{out_path}")

    if status_ok != total or type_ok != total or sentiment_ok != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
