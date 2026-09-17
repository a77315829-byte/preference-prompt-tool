"""실제 저자별 (질문, 답변) 쌍을 Stack Exchange 공개 API 로 모은다.

**왜 필요한가.** `experiments/form_feature_spread.py` 가 MACSum 에서는
길이 외의 형식 특징이 저자를 구분하지 못한다고 판정했다 - 글머리 기호
비율과 문단 수는 요약문 2,954개 전체에서 값이 한 번도 변하지 않는다
(macdoc 120개, macdial 2,954개 모두). MACSum 요약은 전부 1문단 산문이다.
그래서 넓힌 지표를 시험할 수 없다. 지표가 나쁜지, 걸릴 신호가 없는지를
가를 코퍼스가 필요하다.

**왜 Stack Exchange 인가.** 필요한 조건이 네 개다.

  1. 한 사람이 여러 과제에 답한 것 - 저자 단위가 성립해야 한다.
  2. 과제(질문)가 답변과 함께 있어야 한다 - 압축률을 재려면 원문이 필요하다.
  3. 문체가 실제로 갈려야 한다 - 글머리 기호, 문단, 코드 블록이 섞여 있다.
  4. 게이팅·키·새 의존성이 없어야 한다.

공개 API 는 키 없이 하루 300회를 준다(실측 확인). 표준 라이브러리만으로
받는다. 그리고 이 코퍼스는 **제품이 노리는 실제 상황 그 자체**다 -
"자기 전문 분야에서 답을 많이 써둔 사람의 데이터를 넣으면 그 사람처럼
쓰는 프롬프트가 나오는가".

**저작권.** Stack Exchange 사용자 기여물은 CC BY-SA 다. 이 코퍼스는
로컬 캐시로만 두고(`data/` 는 커밋 금지) 재배포하지 않는다. 보고에
수치만 싣고 본문을 옮기지 않는다.

**HTML 을 어떻게 텍스트로 만드나.** 답변 본문은 HTML 이다. 태그를 그냥
지우면 글머리 기호와 문단 구분이 사라져서 정작 재려던 특징이 날아간다.
그래서 `<li>` 는 "- " 로, `<p>`·`<pre>` 는 빈 줄로 구분해 옮긴다.
표준 라이브러리 `html.parser` 를 쓴다 - 새 의존성 없음(절대 규칙 3).

실행:
    python -m experiments.expert_corpus_se --site cooking --authors 4
    python -m experiments.expert_corpus_se --site writing --authors 4 --refresh
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "stackexchange"

API = "https://api.stackexchange.com/2.3"

# 한 번에 받을 수 있는 최대. API 상한이 100 이다.
PAGE_SIZE = 100

# 저자당 최소 답변 수. 학습 12개 + 홀드아웃 여유를 생각하면 이보다
# 적은 저자는 실험에 못 쓴다.
MIN_ANSWERS = 25

# 너무 짧은 답변은 형식을 재봐야 잡히는 게 없고, 너무 긴 것은 한두 개가
# 평균을 지배한다. 양쪽을 자른다.
MIN_ANSWER_WORDS = 30
MAX_ANSWER_WORDS = 800

# 연속 호출 사이 간격. 쿼타가 하루 300회뿐이라 백오프보다 예방이 싸다.
REQUEST_PAUSE_SECONDS = 0.4


class _TextExtractor(HTMLParser):
    """HTML 을 텍스트로 옮기되 글머리 기호와 문단 구분을 살린다.

    태그를 전부 지우는 방식으로는 안 된다. 이 코퍼스를 쓰는 이유가
    바로 `bullet_line_ratio` 와 `paragraphs_per_answer` 를 재려는 것인데,
    그 두 값은 줄바꿈 구조에만 담겨 있다. 지우면 측정 대상이 사라진다.
    """

    _BLOCK = {"p", "div", "blockquote", "h1", "h2", "h3", "h4", "pre", "table", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._in_code_block = False
        self.code_blocks = 0

    def handle_starttag(self, tag, attrs) -> None:
        if tag == "li":
            self._parts.append("\n- ")
        elif tag == "br":
            self._parts.append("\n")
        elif tag == "pre":
            self._in_code_block = True
            self.code_blocks += 1
            self._parts.append("\n\n")
        elif tag in self._BLOCK:
            self._parts.append("\n\n")

    def handle_endtag(self, tag) -> None:
        if tag == "pre":
            self._in_code_block = False
        if tag in self._BLOCK or tag == "li":
            self._parts.append("\n")

    def handle_data(self, data) -> None:
        self._parts.append(data)

    def text(self) -> str:
        joined = "".join(self._parts)
        # 줄 안의 공백은 접고, 빈 줄은 최대 하나만 남긴다. 그래야
        # 문단 수가 원저자의 의도대로 잡힌다.
        lines = [" ".join(line.split()) for line in joined.splitlines()]
        collapsed: list[str] = []
        for line in lines:
            if not line and collapsed and not collapsed[-1]:
                continue
            collapsed.append(line)
        return "\n".join(collapsed).strip()


def html_to_text(html: str) -> tuple[str, int]:
    """(텍스트, 코드 블록 수) 를 돌려준다."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.text(), parser.code_blocks


def _get(path: str, params: dict[str, str | int]) -> dict:
    """API 를 한 번 호출한다. 응답은 gzip 으로 온다.

    캐싱은 호출하는 쪽에서 파일 단위로 한다(절대 규칙 2). 여기서는
    쿼타 소진만 막는다 - 남은 쿼타를 응답에서 읽어 0 이 되기 전에 멈춘다.
    """
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{API}/{path}?{query}",
        # 헤더는 latin-1 로만 인코딩된다. 한글을 넣으면 요청 자체가 터진다.
        headers={"Accept-Encoding": "gzip", "User-Agent": "preference-prompt-tool/research"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    payload = json.loads(raw.decode("utf-8"))
    if "error_message" in payload:
        raise SystemExit(f"API 오류: {payload['error_message']}")
    remaining = payload.get("quota_remaining")
    if remaining is not None and remaining < 5:
        raise SystemExit(f"쿼타가 거의 없다 ({remaining}회). 내일 다시 돌릴 것.")
    time.sleep(REQUEST_PAUSE_SECONDS)
    return payload


def top_answerers(site: str, count: int) -> list[dict]:
    """평판 상위 사용자를 후보로 돌려준다.

    답변 수로 먼저 거르려 했는데 `answer_count` 가 기본 필터 응답에
    없어서 전원이 탈락했다. 커스텀 필터를 쓰는 대신 여기서는 후보만
    넉넉히 뽑고, **실제로 쓸 수 있는 쌍이 MIN_ANSWERS 개 이상인지는
    받아본 뒤에 건다**(`collect`). 질문·편집으로 평판을 쌓은 사람은
    그 단계에서 걸러진다.
    """
    payload = _get(
        "users",
        {
            "site": site,
            "sort": "reputation",
            "order": "desc",
            "pagesize": min(PAGE_SIZE, max(count * 3, 20)),
            "filter": "default",
        },
    )
    return payload["items"]


def author_pairs(site: str, user_id: int, limit: int) -> list[dict]:
    """한 저자의 (질문 본문, 답변 본문) 쌍. 질문은 배치로 한 번에 받는다."""
    answers = _get(
        f"users/{user_id}/answers",
        {
            "site": site,
            "sort": "votes",
            "order": "desc",
            "pagesize": min(PAGE_SIZE, limit),
            "filter": "withbody",
        },
    )["items"]

    question_ids = sorted({a["question_id"] for a in answers})
    questions: dict[int, dict] = {}
    for start in range(0, len(question_ids), PAGE_SIZE):
        batch = question_ids[start : start + PAGE_SIZE]
        payload = _get(
            "questions/" + ";".join(str(i) for i in batch),
            {"site": site, "pagesize": PAGE_SIZE, "filter": "withbody"},
        )
        for item in payload["items"]:
            questions[item["question_id"]] = item

    pairs = []
    for answer in answers:
        question = questions.get(answer["question_id"])
        if not question or "body" not in answer:
            continue
        answer_text, code_blocks = html_to_text(answer["body"])
        question_text, _ = html_to_text(question.get("body", ""))
        words = len(answer_text.split())
        if not (MIN_ANSWER_WORDS <= words <= MAX_ANSWER_WORDS):
            continue
        if not question_text.split():
            continue
        pairs.append(
            {
                "answer": answer_text,
                # 질문 제목과 본문을 합쳐 과제로 쓴다. 제목만으로는
                # 압축률의 분모가 너무 작아 값이 불안정하다.
                "task": (question.get("title", "") + "\n" + question_text).strip(),
                "answer_id": answer["answer_id"],
                "question_id": answer["question_id"],
                "code_blocks": code_blocks,
            }
        )
    return pairs


def collect(site: str, authors: int, per_author: int, refresh: bool = False) -> dict:
    """저자별 코퍼스를 모아 캐시에 쓴다. 이미 있으면 그대로 읽는다."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{site}_a{authors}_n{per_author}.json"
    if path.exists() and not refresh:
        print(f"캐시 사용: {path.relative_to(ROOT)}")
        return json.loads(path.read_text(encoding="utf-8"))

    candidates = top_answerers(site, authors)
    if not candidates:
        raise SystemExit("후보 사용자를 못 받았다. --site 를 확인할 것.")

    corpus = {"site": site, "authors": []}
    for user in candidates:
        if len(corpus["authors"]) >= authors:
            break
        pairs = author_pairs(site, user["user_id"], per_author)
        print(f"  저자 {user['user_id']}: 쓸 수 있는 쌍 {len(pairs)}개")
        if len(pairs) < MIN_ANSWERS:
            print(f"    건너뜀 - 쌍이 {MIN_ANSWERS}개 미만")
            continue
        corpus["authors"].append(
            {
                # 표시 이름은 저장하지 않는다. 실험에 필요하지 않고,
                # 사람 이름을 저장소 주변에 두지 않는 편이 낫다.
                "user_id": user["user_id"],
                "pairs": pairs,
            }
        )

    if len(corpus["authors"]) < 2:
        raise SystemExit("쓸 수 있는 저자가 2명 미만이다. 비교가 성립하지 않는다.")

    path.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    print(f"저장: {path.relative_to(ROOT)} (저자 {len(corpus['authors'])}명)")
    return corpus


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default="cooking", help="Stack Exchange 사이트 이름")
    parser.add_argument("--authors", type=int, default=4, help="모을 저자 수")
    parser.add_argument("--per-author", type=int, default=PAGE_SIZE, help="저자당 답변 상한")
    parser.add_argument("--refresh", action="store_true", help="캐시를 무시하고 다시 받는다")
    args = parser.parse_args()

    try:
        corpus = collect(args.site, args.authors, args.per_author, args.refresh)
    except urllib.error.URLError as error:
        raise SystemExit(f"네트워크 실패: {error}")

    print()
    for author in corpus["authors"]:
        pairs = author["pairs"]
        words = [len(p["answer"].split()) for p in pairs]
        with_code = sum(1 for p in pairs if p["code_blocks"])
        print(
            f"저자 {author['user_id']}: 쌍 {len(pairs)}개, "
            f"답변 {min(words)}~{max(words)}단어 (평균 {sum(words) / len(words):.0f}), "
            f"코드 블록 있는 답변 {with_code}개"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
