"""모델 호출 없이 제공하는 언어별 작성 방식 비교. 코드를 실행하지 않는다."""
from __future__ import annotations

from coding_framework_examples import build_framework_examples

# 금액은 정수 단위, 수량은 음수가 아닌 값이라는 동일한 가정의 작은 예시다.
# 각 항목: 전체 코드, 역할 분리 코드, 변경된 한 줄, 주석 문법.
SNIPPETS = {
    "Python": (
        "def order_total(price, quantity):\n    return price * quantity + 3000",
        "def subtotal(price, quantity):\n    return price * quantity\n\ndef order_total(price, quantity):\n    return subtotal(price, quantity) + 3000",
        "    return price * quantity + 2500", "#",
    ),
    "Java": (
        "class Order {\n    static int orderTotal(int price, int quantity) {\n        return price * quantity + 3000;\n    }\n}",
        "class Order {\n    static int subtotal(int price, int quantity) {\n        return price * quantity;\n    }\n    static int orderTotal(int price, int quantity) {\n        return subtotal(price, quantity) + 3000;\n    }\n}",
        "        return price * quantity + 2500;", "//",
    ),
    "JavaScript": (
        "function orderTotal(price, quantity) {\n  return price * quantity + 3000;\n}",
        "function subtotal(price, quantity) {\n  return price * quantity;\n}\nfunction orderTotal(price, quantity) {\n  return subtotal(price, quantity) + 3000;\n}",
        "  return price * quantity + 2500;", "//",
    ),
    "TypeScript": (
        "function orderTotal(price: number, quantity: number): number {\n  return price * quantity + 3000;\n}",
        "function subtotal(price: number, quantity: number): number {\n  return price * quantity;\n}\nfunction orderTotal(price: number, quantity: number): number {\n  return subtotal(price, quantity) + 3000;\n}",
        "  return price * quantity + 2500;", "//",
    ),
    "C": (
        "int order_total(int price, int quantity) {\n    return price * quantity + 3000;\n}",
        "static int subtotal(int price, int quantity) {\n    return price * quantity;\n}\nint order_total(int price, int quantity) {\n    return subtotal(price, quantity) + 3000;\n}",
        "    return price * quantity + 2500;", "//",
    ),
    "C++": (
        "int orderTotal(int price, int quantity) {\n    return price * quantity + 3000;\n}",
        "int subtotal(int price, int quantity) {\n    return price * quantity;\n}\nint orderTotal(int price, int quantity) {\n    return subtotal(price, quantity) + 3000;\n}",
        "    return price * quantity + 2500;", "//",
    ),
    "C#": (
        "class Order {\n    public static int OrderTotal(int price, int quantity) {\n        return price * quantity + 3000;\n    }\n}",
        "class Order {\n    static int Subtotal(int price, int quantity) {\n        return price * quantity;\n    }\n    public static int OrderTotal(int price, int quantity) {\n        return Subtotal(price, quantity) + 3000;\n    }\n}",
        "        return price * quantity + 2500;", "//",
    ),
    "Go": (
        "package order\n\nfunc OrderTotal(price, quantity int) int {\n    return price * quantity + 3000\n}",
        "package order\n\nfunc subtotal(price, quantity int) int {\n    return price * quantity\n}\nfunc OrderTotal(price, quantity int) int {\n    return subtotal(price, quantity) + 3000\n}",
        "    return price * quantity + 2500", "//",
    ),
    "Rust": (
        "fn order_total(price: i64, quantity: i64) -> i64 {\n    price * quantity + 3000\n}",
        "fn subtotal(price: i64, quantity: i64) -> i64 {\n    price * quantity\n}\nfn order_total(price: i64, quantity: i64) -> i64 {\n    subtotal(price, quantity) + 3000\n}",
        "    price * quantity + 2500", "//",
    ),
    "Kotlin": (
        "fun orderTotal(price: Int, quantity: Int): Int {\n    return price * quantity + 3000\n}",
        "fun subtotal(price: Int, quantity: Int): Int {\n    return price * quantity\n}\nfun orderTotal(price: Int, quantity: Int): Int {\n    return subtotal(price, quantity) + 3000\n}",
        "    return price * quantity + 2500", "//",
    ),
    "Swift": (
        "func orderTotal(price: Int, quantity: Int) -> Int {\n    return price * quantity + 3000\n}",
        "func subtotal(price: Int, quantity: Int) -> Int {\n    return price * quantity\n}\nfunc orderTotal(price: Int, quantity: Int) -> Int {\n    return subtotal(price: price, quantity: quantity) + 3000\n}",
        "    return price * quantity + 2500", "//",
    ),
    "Dart": (
        "int orderTotal(int price, int quantity) {\n  return price * quantity + 3000;\n}",
        "int subtotal(int price, int quantity) {\n  return price * quantity;\n}\nint orderTotal(int price, int quantity) {\n  return subtotal(price, quantity) + 3000;\n}",
        "  return price * quantity + 2500;", "//",
    ),
    "PHP": (
        "<?php\nfunction orderTotal(int $price, int $quantity): int {\n    return $price * $quantity + 3000;\n}",
        "<?php\nfunction subtotal(int $price, int $quantity): int {\n    return $price * $quantity;\n}\nfunction orderTotal(int $price, int $quantity): int {\n    return subtotal($price, $quantity) + 3000;\n}",
        "    return $price * $quantity + 2500;", "//",
    ),
    "Ruby": (
        "def order_total(price, quantity)\n  price * quantity + 3000\nend",
        "def subtotal(price, quantity)\n  price * quantity\nend\n\ndef order_total(price, quantity)\n  subtotal(price, quantity) + 3000\nend",
        "  price * quantity + 2500", "#",
    ),
}


def build_coding_examples(profile: dict) -> dict:
    """검증된 profile을 받아 한 항목만 다른 네 쌍의 답변을 반환한다."""
    framework_examples = build_framework_examples(profile)
    if framework_examples is not None:
        return framework_examples
    if profile["language"] not in SNIPPETS:
        raise ValueError("이 언어의 코드 예시는 아직 준비 중이에요. 목록의 언어를 선택하거나 직접 설정으로 지침을 만들어 주세요.")
    full, modular, changed_line, comment = SNIPPETS[profile["language"]]
    annotated = full
    # PHP 선언과 Go package 앞뒤를 건드리지 않고 계산식 바로 위에 주석을 넣는다.
    lines = full.splitlines()
    for i, line in enumerate(lines):
        if "3000" in line:
            indent = line[:len(line) - len(line.lstrip())]
            annotated = "\n".join(lines[:i] + [indent + comment + " 상품 금액을 계산하고 고정 배송비를 더합니다."] + lines[i:])
            break
    fields = [
        ("explanation", "설명 방식", "같은 코드를 받을 때 어느 설명이 편한가요?", [
            ("brief", "핵심만", full, "단가에 수량을 곱하고 배송비 3,000을 더합니다."),
            ("steps", "단계별 설명", full, "1. price는 상품 하나의 금액, quantity는 수량입니다.\n2. 두 값을 곱해 상품 금액을 계산합니다.\n3. 고정 배송비 3,000을 더해 반환합니다.\n예: 단가 10,000, 수량 2이면 합계는 23,000입니다."),
        ]),
        ("comments", "주석 정도", "같은 계산에서 어느 주석 방식이 편한가요?", [
            ("essential", "필요한 주석만", full, "단순한 계산은 코드로 읽고, 주의할 의도가 있을 때 주석을 붙입니다."),
            ("detailed", "핵심 로직에 주석", annotated, "계산 의도를 주석으로 함께 확인합니다."),
        ]),
        ("structure", "코드 구성", "같은 기능을 어느 구성으로 받고 싶나요?", [
            ("compact", "한 함수에 간결하게", full, "작은 계산을 한곳에서 바로 확인합니다."),
            ("modular", "역할별 함수로", modular, "상품 금액 계산을 별도 함수로 나눠 재사용합니다."),
        ]),
        ("output", "코드 출력", "아래 기존 코드의 배송비를 3,000에서 2,500으로 바꾼다면?", [
            ("complete", "전체 코드", full.replace("3000", "2500"), "수정된 전체 예시입니다. 기존 코드를 이 내용으로 교체하세요."),
            ("changes", "변경 부분 중심", changed_line, "기존 주문 합계 함수의 계산식 한 줄을 교체하세요. 나머지 코드는 유지합니다."),
        ]),
    ]
    return {"version": 1, "language": profile["language"], "framework": profile["framework"],
            "source": {"id": "language-basics-v1", "kind": "language", "label": f"{profile['language']} 기본 문법"},
            "task": "정수 단가 × 음수가 아닌 수량 + 고정 배송비를 계산하는 작은 함수",
            "notice": ((f"{profile['framework']} 전용 예시는 아직 없어 {profile['language']} 기본 문법을 비교합니다. " if profile["framework"] else "")
                       + "준비된 언어 기본 문법 예시이며 프레임워크 전용 코드나 실행 검증 결과가 아닙니다. 선택한 프레임워크는 완성 지침에 반영합니다."),
            "pairs": [{"axis": axis, "label": label, "question": question,
                       "before": full if axis == "output" else None,
                       "options": [{"value": value, "label": title, "code": code, "explanation": explanation}
                                   for value, title, code, explanation in options]}
                      for axis, label, question, options in fields]}
