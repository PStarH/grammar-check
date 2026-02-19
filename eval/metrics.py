from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvalResult:
    precision: float
    recall: float
    suggestion_quality: float
    tp: int
    fp: int
    fn: int


def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def score_case(predicted: list[dict], expected: list[dict]) -> tuple[int, int, int, int, int]:
    matched_expected: set[int] = set()
    tp = 0
    fp = 0
    sq_ok = 0
    sq_total = 0

    for pred in predicted:
        pstart, pend = pred["plainRange"]["start"], pred["plainRange"]["end"]
        ptype = pred["type"]
        matched = False
        for idx, exp in enumerate(expected):
            if idx in matched_expected or exp.get("type") != ptype:
                continue
            estart, eend = exp["span"]["start"], exp["span"]["end"]
            if _overlap(pstart, pend, estart, eend) > 0:
                matched = True
                matched_expected.add(idx)
                tp += 1
                # Score suggestion quality against the matched expected issue
                expected_should_change = exp.get("expectedShouldChange", True)
                if expected_should_change:
                    sq_total += 1
                    expected_repl = exp.get("expectedReplacement")
                    if expected_repl is not None:
                        pred_repl = pred.get("replacement")
                        if (
                            isinstance(pred_repl, str)
                            and isinstance(expected_repl, str)
                            and pred_repl.strip() == expected_repl.strip()
                        ):
                            sq_ok += 1
                break
        if not matched:
            fp += 1

    fn = len(expected) - len(matched_expected)
    return tp, fp, fn, sq_ok, sq_total


def aggregate(scores: list[tuple[int, int, int, int, int]]) -> EvalResult:
    tp = sum(s[0] for s in scores)
    fp = sum(s[1] for s in scores)
    fn = sum(s[2] for s in scores)
    sq_ok = sum(s[3] for s in scores)
    sq_total = sum(s[4] for s in scores)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    suggestion_quality = sq_ok / sq_total if sq_total else 0.0
    return EvalResult(
        precision=precision,
        recall=recall,
        suggestion_quality=suggestion_quality,
        tp=tp,
        fp=fp,
        fn=fn,
    )
