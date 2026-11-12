"""Collect completed offline runs without copying accounts, cookies or databases."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
RUN=ROOT/"tmp/integration-20261112"
subprocess.run([sys.executable,str(HERE/"source_receipt.py"),"verify"],check=True)
xml=ET.parse(RUN/"pytest-final.xml").getroot()
cases=xml.findall(".//testcase")
failures=xml.findall(".//failure")+xml.findall(".//error")
skips=xml.findall(".//skipped")
assert not failures and cases
pylog=(RUN/"pytest-final.log").read_text(encoding="utf-8-sig")
passed,skipped,deselected,seconds=re.search(r"(\d+) passed, (\d+) skipped, (\d+) deselected in ([\d.]+)s",pylog).groups()
assert int(passed)==len(cases)-len(skips) and int(skipped)==len(skips)
frontend=(RUN/"frontend-final.log").read_text(encoding="utf-8-sig")
front_pass=int(re.search(r"# pass (\d+)",frontend)[1])
assert re.search(r"# fail 0\b",frontend)
build=(RUN/"build-run2.log").read_text(encoding="utf-8-sig")
assert "built in" in build
browser=json.loads((RUN/"browser-run3/result.json").read_text(encoding="utf-8"))
assert browser["pass"] and len(browser["results"])==18 and all(s["pass"] for s in browser["results"])
guard=json.loads((RUN/"pytest-offline-guard.json").read_text(encoding="utf-8"))
assert guard["non_loopback_denials"]==[]
out=HERE/"results"
out.mkdir(exist_ok=True)
source_files={
    "backend-final.log":RUN/"pytest-final.log", "backend-before-fix.log":RUN/"pytest-run2.log",
    "frontend-final.log":RUN/"frontend-final.log", "frontend-focused.log":RUN/"handoff-fix-tests.log",
    "domain-focused.log":RUN/"domain-fix.log", "build.log":RUN/"build-run2.log",
    "browser.json":RUN/"browser-run3/result.json", "browser-before-fix.json":RUN/"browser-run2/result.json",
    "source-hashes.json":RUN/"final-source-hashes.json", "offline-guard.json":RUN/"pytest-offline-guard.json",
}
for name,src in source_files.items():
    shutil.copyfile(src,out/name)
receipt={
    "date":"2026-11-12", "backend":{"passed":int(passed),"skipped":int(skipped),"deselected":int(deselected),"failed":0,"seconds":float(seconds),"skip_reasons":[x.attrib.get("message") for x in skips]},
    "backend_before_fix":{"passed":1353,"failed":4,"skipped":1,"deselected":16},
    "frontend":{"passed":front_pass,"failed":0},"build":{"passed":True,"large_chunk_warning":True},
    "integration":{"passed":18,"failed":0,"browser":browser["browser"],"http_and_ui":True,"real_human_study":False},
    "paid_model_api_calls":0,"external_python_connections":0,
    "fixes":["권한 회수 확인 후 인수인계 화면·초안 정리; 버전 충돌/일시 장애의 입력은 보존", "보조 요약 설정과 엔진 도메인의 테스트 수집 분리; 영어·한국어 보조 설정 형식 검사 추가"],
    "source_files_checked":len(json.loads((RUN/"final-source-hashes.json").read_text())),
    "evidence":{name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in source_files},
    "limits":["합성 계정·자료의 로컬 Chromium/HTTP 검증으로 실사용자 효과나 공개 배포 검증이 아님", "Windows 심볼릭 링크 생성 권한이 없어 관련 1검사 건너뜀", "실제 모델 API 검사 16개는 비용 금지 조건에 따라 제외", "기존 비교 메모리 세션의 계정 접근 정책은 별도 개선 범위", "이미 다운로드한 파일이나 클립보드 사본을 회수하는 기능은 아님"],
}
(HERE/"results.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"backend":receipt["backend"],"frontend":receipt["frontend"],"integration":receipt["integration"]},ensure_ascii=False))
