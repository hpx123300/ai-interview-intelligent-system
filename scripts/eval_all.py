"""统一评测入口：一条命令跑完检索层 / 编排层 / 面试闭环，并和基线对比。

为什么要有这个文件：

三个 eval_*.py 各自能跑，但各自为战的问题很实际——没人记得住跑哪三个、
数字散落在终端里、改完提示词不知道「比上次好了还是坏了」。
评测的价值不在于某一次的绝对数字，而在于**可比较**。

所以这里做三件事：
1. 统一执行与汇总，输出一份带元信息（提示词版本 / git commit / 时间）的 JSON；
2. 对每个指标设下限，低于下限直接退出码 1，可以挂进 CI；
3. 支持 --baseline 对比，把「涨了多少 / 跌了多少」打出来。

用法：
    python scripts/eval_all.py                 # 全量（会真实调用模型）
    python scripts/eval_all.py --offline       # 只跑检索层，不花 token
    python scripts/eval_all.py --baseline data/eval/reports/xxx.json
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

REPORT_DIR = PROJECT_ROOT / "data" / "eval" / "reports"

# 指标下限。定得比当前实测值略低一点，留出模型随机性的空间，
# 否则偶发波动就会天天报警，最后没人看。
THRESHOLDS = {
    "rag.base.recall@3": 0.95,
    "rag.paraphrase.recall@3": 0.80,
    "rag.base.mrr": 0.90,
    "agent.route_accuracy": 0.90,
    "agent.tool_accuracy": 0.80,
    "agent.completion_rate": 0.95,
    "interview.question_rate": 0.90,
    "interview.feedback_rate": 0.90,
    "interview.evaluate_ok": 1.0,
    "interview.review_ok": 1.0,
}

# 相对基线允许的下降幅度，超过就算回归
REGRESSION_TOLERANCE = 0.05


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def _flatten(results: dict) -> dict:
    """把三份异构结果压成「指标名 -> 数值」，便于比较和设阈值。"""
    flat: dict[str, float] = {}
    rag = results.get("rag")
    if rag:
        for group in ("base", "paraphrase"):
            for key, value in (rag.get(group) or {}).items():
                if key != "n":
                    flat[f"rag.{group}.{key}"] = value
    agent = results.get("agent")
    if agent:
        for key in ("route_accuracy", "tool_accuracy", "completion_rate"):
            if key in agent:
                flat[f"agent.{key}"] = agent[key]
    interview = results.get("interview")
    if interview:
        flat["interview.question_rate"] = round(
            interview["question_ok"] / max(interview["question_total"], 1), 3
        )
        flat["interview.feedback_rate"] = round(
            interview["feedback_ok"] / max(interview["feedback_total"], 1), 3
        )
        flat["interview.evaluate_ok"] = float(interview["evaluate_ok"])
        flat["interview.review_ok"] = float(interview["review_ok"])
    return flat


def _run(name: str, module_name: str) -> dict:
    print(f"\n{'=' * 60}\n▶ {name}\n{'=' * 60}")
    module = __import__(module_name)
    return module.run_eval()


def main() -> int:
    parser = argparse.ArgumentParser(description="统一评测入口")
    parser.add_argument("--offline", action="store_true", help="只跑检索层（不调用模型，不花钱）")
    parser.add_argument("--only", default="", help="只跑某几项，逗号分隔：rag,agent,interview")
    parser.add_argument("--baseline", default="", help="基线报告路径，用于对比")
    parser.add_argument("--save", action="store_true", help="把结果写入 data/eval/reports/")
    parser.add_argument("--no-fail", action="store_true", help="低于阈值也不返回非 0（本地调试用）")
    args = parser.parse_args()

    if args.only:
        selected = [s.strip() for s in args.only.split(",") if s.strip()]
    elif args.offline:
        selected = ["rag"]
    else:
        selected = ["rag", "agent", "interview"]

    results: dict[str, dict] = {}
    if "rag" in selected:
        results["rag"] = _run("检索层：Recall@3 / MRR", "eval_rag")
    if "agent" in selected:
        results["agent"] = _run("编排层：路由 / 工具 / 完整率", "eval_agent")
    if "interview" in selected:
        results["interview"] = _run("面试闭环：出题 / 点评 / 评分 / 复盘", "eval_interview")

    flat = _flatten(results)

    from backend.app.agent.roles import PROMPT_VERSION  # 延迟导入，避免 offline 也拉起依赖

    meta = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "commit": _git_commit(),
        "prompt_version": PROMPT_VERSION,
        "selected": selected,
        "offline": args.offline,
    }
    report = {"meta": meta, "metrics": flat, "raw": results}

    # ---------- 阈值 ----------
    failures = []
    print(f"\n{'=' * 60}\n指标汇总\n{'=' * 60}")
    print(f"{'指标':<34}{'实测':>8}{'下限':>8}  状态")
    for key, value in flat.items():
        floor = THRESHOLDS.get(key)
        if floor is None:
            continue
        ok = value >= floor
        if not ok:
            failures.append(f"{key}={value} < {floor}")
        print(f"{key:<34}{value:>8}{floor:>8}  {'通过' if ok else '不达标'}")

    # ---------- 基线对比 ----------
    if args.baseline:
        base_path = Path(args.baseline)
        if not base_path.exists():
            print(f"\n基线文件不存在：{base_path}")
        else:
            base = json.loads(base_path.read_text(encoding="utf-8"))
            base_metrics = base.get("metrics", {})
            print(f"\n{'=' * 60}\n与基线对比（{base.get('meta', {}).get('time', '?')}）\n{'=' * 60}")
            print(f"{'指标':<34}{'基线':>8}{'当前':>8}{'变化':>9}")
            for key, value in flat.items():
                if key not in base_metrics:
                    continue
                old = base_metrics[key]
                delta = value - old
                flag = ""
                if delta < -REGRESSION_TOLERANCE:
                    flag = "  ← 回归"
                    failures.append(f"{key} 相对基线下降 {delta:.3f}")
                elif delta > 0:
                    flag = "  ↑"
                print(f"{key:<34}{old:>8}{value:>8}{delta:>+9.3f}{flag}")

    # ---------- 保存 ----------
    if args.save:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n报告已保存：{out.relative_to(PROJECT_ROOT)}")

    print(f"\n提示词版本 {meta['prompt_version']} | commit {meta['commit']}")
    if failures:
        print("\n不达标项：")
        for item in failures:
            print(f"  - {item}")
        return 0 if args.no_fail else 1
    print("\n全部指标达标。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
