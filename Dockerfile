FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
RUN mkdir -p /node-runtime \
    && cp -L /usr/local/bin/node /node-runtime/node \
    && cp -L /usr/lib/*-linux-gnu/libstdc++.so.6 /node-runtime/libstdc++.so.6

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PPT_STORAGE_DIR=/var/data \
    PPT_DB_PATH=/var/data/data/app.db \
    PPT_COOKIE_SECURE=1 \
    PPT_API_HOST=0.0.0.0
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# Node and the existing TypeScript parser are needed by JS/TS GEPA checks.
# No new Python or JavaScript dependencies are introduced.
COPY --from=frontend /node-runtime/node /usr/local/bin/node
COPY --from=frontend /node-runtime/libstdc++.so.6 /usr/local/lib/libstdc++.so.6
RUN ldconfig && node --version
COPY --from=frontend /build/frontend/node_modules/typescript ./frontend/node_modules/typescript
COPY --from=frontend /build/frontend/dist ./frontend/dist
COPY frontend/package.json ./frontend/package.json
COPY *.py ./
COPY engine/ ./engine/
COPY domains/ ./domains/
COPY checks/ ./checks/
COPY demos/ ./demos/
COPY optimize/ ./optimize/
COPY agents/ ./agents/
COPY prompt_workspace/ ./prompt_workspace/
COPY scripts/ ./scripts/
COPY benchmarks/coding_style/v1.json ./benchmarks/coding_style/v1.json
RUN mkdir -p /var/data/data /var/data/cache && ln -s /var/data/cache /app/cache
EXPOSE 8000
CMD ["python", "-X", "utf8", "hosting_server.py"]
