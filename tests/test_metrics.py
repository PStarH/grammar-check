from eval.metrics import aggregate, score_case


def test_metrics_overlap() -> None:
    pred = [
        {
            "type": "grammar",
            "plainRange": {"start": 3, "end": 8},
            "context": "go",
            "replacement": "went",
        }
    ]
    exp = [{"type": "grammar", "span": {"start": 4, "end": 9}}]
    score = score_case(pred, exp)
    result = aggregate([score])
    assert result.tp == 1
    assert result.fp == 0
    assert result.fn == 0
