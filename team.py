"""팀 모드: 여러 사람의 선택을 합쳐 팀 공통 프롬프트를 만든다.

Streamlit 을 import 하지 않는다 (`service.py`, `exporters.py` 와 같은 층).

타깃을 "AI 를 매일 쓰는 작은 개발팀"으로 잡은 근거가 되는 기능이다. 예를 들어
팀원 셋이 각자 코딩 비교를 하면, 세 사람의 비교를 모두 한 추정기에 넣어 팀
선호를 정하고, 사람마다 갈린 축은 "합의가 필요한 항목"으로 보여 준다.

**저장하는 것:** 팀 코드, 이름, 선택 기록(어느 두 조합 중 무엇을 골랐는지).
원문과 생성 결과는 저장하지 않는다. 서버 메모리에만 두므로 재시작하면
사라진다 - 최소 버전이다. 오래 두려면 JSON 파일 저장소로 옮긴다(프로젝트
규칙상 서버형 DB 는 쓰지 않는다).

이 모듈은 도메인을 모른다. 축 이름과 값은 도메인 정의에서 읽는다.
"""

from __future__ import annotations

import re
import threading
from collections import Counter
from dataclasses import dataclass, field

from engine.domain_loader import Domain
from engine.estimator import Comparison, Estimator

MAX_MEMBERS_PER_TEAM = 20
MAX_TEAMS = 200
_CODE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
MAX_NAME_CHARS = 20

History = list[tuple[dict[str, str], dict[str, str], str]]


class TeamError(ValueError):
    pass


@dataclass
class Member:
    name: str
    history: History


@dataclass
class _Team:
    domain_key: str
    members: dict[str, Member] = field(default_factory=dict)


class TeamStore:
    """팀 코드 -> 팀. 스레드 안전. 서버 프로세스가 하나를 공유한다."""

    def __init__(self) -> None:
        self._teams: dict[str, _Team] = {}
        self._lock = threading.Lock()

    def add(self, code: str, domain_key: str, name: str, history: History) -> list[Member]:
        """이름이 같으면 그 사람의 기록을 새것으로 바꾼다 (다시 해 본 경우)."""
        if not _CODE.match(code or ""):
            raise TeamError("팀 코드는 영문·숫자·-·_ 3~32자여야 합니다.")
        name = (name or "").strip()
        if not name or len(name) > MAX_NAME_CHARS:
            raise TeamError(f"이름은 1~{MAX_NAME_CHARS}자여야 합니다.")
        if not history:
            raise TeamError("선택 기록이 없는 세션은 팀에 더할 수 없습니다.")
        with self._lock:
            team = self._teams.get(code)
            if team is None:
                if len(self._teams) >= MAX_TEAMS:
                    raise TeamError("지금은 새 팀을 만들 수 없습니다. 잠시 뒤 다시 시도해 주세요.")
                team = self._teams[code] = _Team(domain_key)
            if team.domain_key != domain_key:
                raise TeamError(f"이 팀 코드는 다른 카테고리({team.domain_key})에 쓰이고 있습니다.")
            if name not in team.members and len(team.members) >= MAX_MEMBERS_PER_TEAM:
                raise TeamError(f"한 팀은 {MAX_MEMBERS_PER_TEAM}명까지입니다.")
            team.members[name] = Member(name, [tuple(c) for c in history])
            return list(team.members.values())

    def get(self, code: str) -> tuple[str, list[Member]]:
        with self._lock:
            team = self._teams.get(code)
            if team is None:
                raise TeamError("아직 아무도 참여하지 않은 팀 코드입니다.")
            return team.domain_key, list(team.members.values())


def _estimator(domain: Domain, histories: list[History]) -> Estimator:
    estimator = Estimator(domain)
    for history in histories:
        for combo_a, combo_b, winner in history:
            estimator.update(Comparison(combo_a=combo_a, combo_b=combo_b, winner=winner))
    return estimator


@dataclass(frozen=True)
class AxisAgreement:
    axis: str
    team_value: str
    votes: dict[str, int]  # 값 -> 그 값을 1위로 고른 사람 수
    agreed: bool
    # 최다 득표가 둘 이상이면 팀 프롬프트의 값은 비교를 합친 결과일 뿐
    # 다수결이 아니다. 화면에서 "팀이 정해야 한다"고 알린다.
    tied: bool = False


def summarize(domain: Domain, members: list[Member]) -> tuple[Estimator, list[AxisAgreement]]:
    """모든 팀원의 비교를 한 추정기에 넣은 팀 추정과, 축마다 사람들이 어떻게
    갈렸는지. 사람별 1위는 각자의 기록만으로 따로 추정한다."""
    team_estimator = _estimator(domain, [m.history for m in members])
    personal = [_estimator(domain, [m.history]) for m in members]
    agreements = []
    for axis in team_estimator.enum_axis_names():
        votes = Counter(e.preferred_value(axis) for e in personal)
        agreements.append(AxisAgreement(
            axis=axis,
            team_value=team_estimator.preferred_value(axis),
            votes=dict(votes.most_common()),
            agreed=len(votes) == 1,
            tied=len(votes) > 1 and sum(1 for n in votes.values() if n == max(votes.values())) > 1,
        ))
    return team_estimator, agreements
