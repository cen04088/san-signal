# Railway 배포용. 사이트를 빌드하고, Python 서버가 정적 파일과 매시간 실시간 데이터 수집을 맡는다.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js ./
COPY src src
COPY public public
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1
COPY scripts/common.py scripts/fetch_live.py scripts/serve.py scripts/
COPY --from=build /app/dist dist
CMD ["python", "scripts/serve.py"]
