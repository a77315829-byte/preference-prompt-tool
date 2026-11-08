"""Read-only React/API deployment check. No account creation or model calls."""
from __future__ import annotations

import argparse
import json
import re
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen


def check(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('자격 증명·쿼리가 없는 서비스 주소를 입력해 주세요.')
    if parsed.scheme != 'https' and parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('공개 서비스는 HTTPS 주소를 사용해 주세요.')
    base = url.rstrip('/') + '/'
    with urlopen(urljoin(base, 'api/health'), timeout=45) as response:
        health = json.load(response)
    if health.get('ok') is not True:
        raise ValueError('API 상태 확인 실패')
    with urlopen(base, timeout=45) as response:
        html = response.read(2_000_000).decode('utf-8')
    assets = re.findall(r'(?:src|href)=[\"\'](/assets/[^\"\']+\.(?:js|css))[\"\']', html)
    if 'id="root"' not in html or not assets:
        raise ValueError('React 진입 화면 또는 빌드 파일을 찾지 못했습니다.')
    for asset in assets:
        with urlopen(urljoin(base, asset), timeout=45) as response:
            if response.status != 200 or 'text/html' in response.headers.get('Content-Type', ''):
                raise ValueError('정적 파일 응답이 올바르지 않습니다.')
    return len(assets)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    print(f'OK: API·React 진입 화면·정적 파일 {check(parser.parse_args().url)}개 확인 (브라우저 상호작용 검사는 별도)')
