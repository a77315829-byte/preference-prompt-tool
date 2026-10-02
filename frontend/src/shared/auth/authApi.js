// 로그인 API (api_server.py 의 /api/auth/*). 세션은 HttpOnly 쿠키라 화면 코드는
// 토큰을 보지도 저장하지도 않는다 - 같은 출처 요청이면 브라우저가 쿠키를 붙인다.

async function request(path, body) {
  const response = await fetch(`/api/auth${path}`, body === undefined
    ? {}
    : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `요청에 실패했습니다 (${response.status})`);
  return data;
}

export const fetchMe = () => request('/me');
export const login = (username, password) => request('/login', { username, password });
export const signup = (username, password) => request('/signup', { username, password });
export const logout = () => request('/logout', {});
