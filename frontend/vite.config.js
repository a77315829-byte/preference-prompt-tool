import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // changeOrigin: false - 브라우저가 보낸 Host(localhost:5175)를 그대로 넘긴다.
      // 문자열 축약형은 Host 를 API 서버 주소로 바꾸는데, 그러면 서버의 다른 사이트
      // 요청 차단(api_server._cross_site)이 같은 화면의 요청까지 막는다.
      "/api": { target: `http://127.0.0.1:${process.env.PPT_API_PORT || '8000'}`, changeOrigin: false, xfwd: true },
    },
  },
});
