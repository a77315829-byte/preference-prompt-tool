"""검토한 프레임워크별 예시. 앱에서는 표시만 하며 실행·모델 호출하지 않는다."""
from __future__ import annotations

FASTAPI_MAIN = '''from fastapi import FastAPI, Query

app = FastAPI()

@app.get("/orders/total")
def order_total(
    price: int = Query(ge=0),
    quantity: int = Query(ge=0),
) -> dict[str, int]:
    return {"total": price * quantity + 3000}
'''

FASTAPI_ROUTER_MAIN = '''from fastapi import FastAPI
from orders import router

app = FastAPI()
app.include_router(router)
'''

FASTAPI_ORDERS = FASTAPI_MAIN.replace('FastAPI, Query', 'APIRouter, Query').replace(
    'app = FastAPI()', 'router = APIRouter(prefix="/orders")'
).replace('@app.get("/orders/total")', '@router.get("/total")')

SPRING_CONTROLLER = '''package com.example.demo;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
public class OrderController {
    @GetMapping("/orders/total")
    public Map<String, Long> orderTotal(
        @RequestParam("price") int price,
        @RequestParam("quantity") int quantity
    ) {
        if (price < 0 || quantity < 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST);
        }
        return Map.of("total", (long) price * quantity + 3000);
    }
}
'''

SPRING_MODULAR_CONTROLLER = '''package com.example.demo;

import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OrderController {
    private final OrderService service;

    public OrderController(OrderService service) {
        this.service = service;
    }

    @GetMapping("/orders/total")
    public Map<String, Long> orderTotal(
        @RequestParam("price") int price,
        @RequestParam("quantity") int quantity
    ) {
        return Map.of("total", service.total(price, quantity));
    }
}
'''

SPRING_SERVICE = '''package com.example.demo;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class OrderService {
    public long total(int price, int quantity) {
        if (price < 0 || quantity < 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST);
        }
        return (long) price * quantity + 3000;
    }
}
'''

FRAMEWORK_EXAMPLES = {
    ("Python", "fastapi"): {
        "id": "fastapi-orders-v1", "framework": "FastAPI", "comment": "#",
        "setup": "Python 3.10+와 FastAPI가 설치된 환경의 예시입니다. main.py와 분리한 orders.py는 같은 폴더에 둡니다.",
        "files": [("main.py", FASTAPI_MAIN)],
        "modular": [("main.py", FASTAPI_ROUTER_MAIN), ("orders.py", FASTAPI_ORDERS)],
        "brief": "GET /orders/total에서 단가와 수량을 받아 상품 금액과 배송비를 합한 JSON을 반환합니다.",
        "steps": "1. FastAPI가 price와 quantity를 쿼리 매개변수로 받습니다.\n2. Query(ge=0)로 음수를 거절합니다.\n3. 상품 금액과 배송비를 계산해 total JSON으로 반환합니다.\n예: /orders/total?price=10000&quantity=2 → {\"total\":23000}",
        "structure_note": "앱 생성은 main.py, 경로 처리는 orders.py의 APIRouter로 나눕니다. 요청 경로와 응답은 같습니다.",
        "change_line": '    return {"total": price * quantity + 2500}',
        "references": ["https://fastapi.tiangolo.com/tutorial/bigger-applications/"],
    },
    ("Java", "springboot"): {
        "id": "spring-boot-orders-v1", "framework": "Spring Boot", "comment": "//",
        "setup": "Java 17+와 Spring Web이 포함된 Spring Boot 3 프로젝트 예시입니다. 기존 실행 클래스 아래 com.example.demo 패키지에 파일을 추가합니다.",
        "files": [("OrderController.java", SPRING_CONTROLLER)],
        "modular": [("OrderController.java", SPRING_MODULAR_CONTROLLER), ("OrderService.java", SPRING_SERVICE)],
        "brief": "GET /orders/total에서 단가와 수량을 받아 상품 금액과 배송비를 합한 JSON을 반환합니다.",
        "steps": "1. @GetMapping이 GET /orders/total 요청을 연결합니다.\n2. @RequestParam이 price와 quantity를 받고 음수이면 400 응답을 보냅니다.\n3. Map의 total 값이 JSON 응답으로 변환됩니다.\n예: /orders/total?price=10000&quantity=2 → {\"total\":23000}",
        "structure_note": "HTTP 처리는 OrderController, 검증과 계산은 OrderService로 나눠 생성자로 주입합니다. 요청 경로와 응답은 같습니다.",
        "change_line": '        return Map.of("total", (long) price * quantity + 2500);',
        "references": ["https://spring.io/guides/gs/rest-service/"],
    },
}


def framework_example_source(language: str, framework: str) -> dict | None:
    key = (language, "".join(framework.lower().split()).replace("-", ""))
    entry = FRAMEWORK_EXAMPLES.get(key)
    if not entry:
        return None
    return {"id": entry["id"], "kind": "framework", "label": f"{language} · {entry['framework']} · 주문 합계 API"}


def build_framework_examples(profile: dict) -> dict | None:
    source = framework_example_source(profile["language"], profile["framework"])
    if source is None:
        return None
    entry = next(item for item in FRAMEWORK_EXAMPLES.values() if item["id"] == source["id"])
    full = entry["files"]
    annotated = []
    for name, code in full:
        lines = code.splitlines()
        for i, line in enumerate(lines):
            if "3000" in line:
                indent = line[:len(line) - len(line.lstrip())]
                lines.insert(i, indent + entry["comment"] + " 상품 금액과 고정 배송비를 합산합니다.")
                break
        annotated.append((name, "\n".join(lines) + "\n"))
    changed = [(name, code.replace("3000", "2500")) for name, code in full]

    def option(value, label, files, explanation):
        return {"value": value, "label": label, "files": [{"name": n, "code": c} for n, c in files],
                "code": "\n\n".join(f"{entry['comment']} {n}\n{c}" for n, c in files), "explanation": explanation}

    pairs = [
        {"axis": "explanation", "label": "설명 방식", "question": "같은 API 코드에서 어느 설명이 편한가요?", "options": [
            option("brief", "핵심만", full, entry["brief"]),
            option("steps", "단계별 설명", full, entry["steps"])]},
        {"axis": "comments", "label": "주석 정도", "question": "같은 API 코드에서 어느 주석 방식이 편한가요?", "options": [
            option("essential", "필요한 주석만", full, "코드로 드러나는 흐름은 반복해서 설명하지 않습니다."),
            option("detailed", "핵심 로직에 주석", annotated, "계산 의도를 주석으로 함께 확인합니다.")]},
        {"axis": "structure", "label": "코드 구성", "question": "같은 API를 어느 파일 구성으로 받고 싶나요?", "options": [
            option("compact", "한 파일에 간결하게", full, "작은 API의 경로 처리와 계산을 한 파일에서 확인합니다."),
            option("modular", "역할별 파일로", entry["modular"], entry["structure_note"])]},
        {"axis": "output", "label": "코드 출력", "question": "아래 기존 API의 배송비를 3,000에서 2,500으로 바꾼다면?",
         "before": option("before", "기존 코드", full, "")["code"], "options": [
             option("complete", "전체 코드", changed, "예시에 필요한 전체 파일을 교체합니다. 프로젝트 설정과 기존 실행 진입점은 유지합니다."),
             option("changes", "변경 부분 중심", [(full[0][0], entry["change_line"])],
                    f"기존 {full[0][0]}의 주문 합계 반환식 한 줄을 교체하세요. 나머지 코드는 유지합니다.")]},
    ]
    return {"version": 2, "language": profile["language"], "framework": profile["framework"], "source": source,
            "task": "GET /orders/total?price=10000&quantity=2 → {\"total\":23000}",
            "notice": f"{entry['framework']}용으로 준비한 API 예시입니다. {entry['setup']} 이 화면은 코드를 실행하지 않습니다.",
            "references": entry["references"], "pairs": pairs}
