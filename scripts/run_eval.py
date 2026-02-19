from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.grammar_service import GrammarService
from app.schemas import CheckRequest
from eval.metrics import aggregate, score_case


def _load_cases(cases_dir: Path) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(cases_dir.glob("*.json"))
    ]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-dir", default="eval/cases")
    parser.add_argument("--output", default="eval/results.json")
    args = parser.parse_args()

    cases = _load_cases(Path(args.cases_dir))
    service = GrammarService()
    per_case = []
    summary_tuples = []

    for case in cases:
        req = CheckRequest(
            requestId=case.get("id"),
            language=case.get("language", "en-US"),
            html=case["html"],
            options=case.get("options", {}),
        )
        resp = await service.check(req)
        pred = [
            {
                "type": i.type,
                "plainRange": {"start": i.plainRange.start, "end": i.plainRange.end},
                "context": i.context,
                "replacement": i.replacement,
            }
            for i in resp.issues
        ]
        score = score_case(pred, case.get("expectedIssues", []))
        summary_tuples.append(score)
        per_case.append(
            {"id": case.get("id"), "score": {"tp": score[0], "fp": score[1], "fn": score[2]}}
        )

    totals = aggregate(summary_tuples)
    output = {
        "summary": {
            "precision": round(totals.precision, 4),
            "recall": round(totals.recall, 4),
            "suggestionQuality": round(totals.suggestion_quality, 4),
            "tp": totals.tp,
            "fp": totals.fp,
            "fn": totals.fn,
        },
        "cases": per_case,
    }
    Path(args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
