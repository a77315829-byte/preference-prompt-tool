"""1주차 관통용 스크립트: litellm으로 API 호출이 실제로 되는지 확인."""

from dotenv import load_dotenv
from litellm import completion

load_dotenv()


def main() -> None:
    response = completion(
        model="openai/gpt-4.1-mini",
        messages=[{"role": "user", "content": "한 문장으로: 오늘 날씨 어때?"}],
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()


# --- 자동 회귀 테스트 ------------------------------------------------------
# main() 은 눈으로 응답을 보려고 남겨둔 것이고, 아래가 실패할 수 있는 검사다.

import pytest


@pytest.mark.api
def test_completion_returns_text(model) -> None:
    """litellm 배선이 살아 있는지. 여기서 깨지면 나머지 API 테스트가
    전부 같은 이유로 깨지므로, 원인을 빨리 좁히려고 최소 호출만 한다."""
    response = completion(
        model=model,
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
    )
    content = response.choices[0].message.content
    assert isinstance(content, str)
    assert content.strip()
