"""코딩 데모용 합성 자료. 실제 사용자의 선호 라벨은 포함하지 않는다."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path


@lru_cache(maxsize=1)
def load_corpus():
    path = Path(__file__).resolve().parents[1] / "benchmarks/coding_style/v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def select_coding_task(source_text, answered):
    """데모의 현재 비교 과제. 사용자가 적은 기능을 구현하는 선택은 아니다."""
    tasks = [task for task in load_corpus()["tasks"] if task["split"] == "elicitation"]
    offset = int.from_bytes(sha256(source_text.encode("utf-8")).digest()[:4], "big")
    return tasks[(offset + answered) % len(tasks)]


def generate_coding_pair(source_text, answered, combo_a, combo_b):
    """동일한 과제의 두 스타일을 반환한다. holdout은 절대 비교에 사용하지 않는다.

    입력은 과제 순서를 결정할 뿐, 임의의 개발 요청을 구현하는 것은 아니다.
    UUID를 제외한 후보 코드와 순서는 같은 입력/선택 이력에서 재현된다.
    """
    corpus = load_corpus()
    task = select_coding_task(source_text, answered)
    variants = [v for v in corpus["variants"] if v["task_id"] == task["id"] and v["split"] == "elicitation"]

    def render(combo):
        variant = next(v for v in variants if v["profile"] == combo)
        files = "\n\n".join(
            f"`{name}`\n```{'tsx' if name.endswith('.tsx') else 'ts'}\n{code}```"
            for name, code in variant["files"].items()
        )
        return f"준비된 비교 과제: {task['request']}\n\n{files}"

    return [render(combo_a), render(combo_b)]
