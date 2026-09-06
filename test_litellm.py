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
