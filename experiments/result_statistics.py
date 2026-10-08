"""실험 집계와 관문 기준. 모델 SDK·네트워크 없이 사용한다."""
import math

import pandas as pd

CONDITIONS = ("A_no_prompt", "B_custom_instruction", "B_plus_knows_preference", "D_our_tool")
COMPARISONS = (
    ("D_our_tool", "B_custom_instruction"),
    ("D_our_tool", "B_plus_knows_preference"),
    ("B_plus_knows_preference", "B_custom_instruction"),
    ("D_our_tool", "A_no_prompt"),
)
FAIR_BPLUS = "B_plus_word_count"
FAIR_COMPARISONS = (
    ("D_our_tool", FAIR_BPLUS),
    (FAIR_BPLUS, "B_plus_knows_preference"),
    (FAIR_BPLUS, "B_custom_instruction"),
)
HUMAN = {"short": 0.053, "normal": 0.103, "long": 0.154}
TOLERANCE = 0.03
N_DOCS = 12


def sign_test_p(wins: int, total: int) -> float:
    if total == 0:
        return 1.0
    extreme = min(wins, total - wins)
    return min(1.0, 2 * sum(math.comb(total, k) for k in range(extreme + 1)) / 2 ** total)


def summarize(df: pd.DataFrame, conditions=CONDITIONS, comparisons=COMPARISONS) -> dict:
    out = {"n": int(df["persona"].nunique()), "means": {}, "paired": {}}
    for metric in ("length_ratio", "checks_score", "rouge_l"):
        if metric not in df:
            continue
        pivot = df.pivot(index="persona", columns="condition", values=metric)
        out["means"][metric] = {c: round(float(pivot[c].mean()), 4) for c in conditions if c in pivot}
        if metric == "length_ratio":
            continue
        for a, b in comparisons:
            diff = pivot[a] - pivot[b]
            wins, losses = int((diff > 0).sum()), int((diff < 0).sum())
            out["paired"][f"{metric}: {a} vs {b}"] = {
                "wins": wins, "losses": losses, "ties": int((diff == 0).sum()),
                "mean_diff": round(float(diff.mean()), 4),
                "sign_test_p": round(sign_test_p(wins, wins + losses), 4),
            }
    return out


def evaluate_gate(medians: dict, human: dict, tolerance: float) -> dict:
    within = all(abs(medians[v] - human[v]) <= tolerance for v in HUMAN)
    ordered = medians["short"] < medians["normal"] < medians["long"]
    return {"within_tolerance": within, "ordered": ordered, "passed": within and ordered}
