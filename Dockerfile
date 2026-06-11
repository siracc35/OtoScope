FROM node:22-alpine AS frontend
WORKDIR /client
COPY client/package*.json ./
RUN npm install
COPY client/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libgomp1 && rm -rf /var/lib/apt/lists/*
COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ ./server/
COPY --from=frontend /client/dist ./client/dist
EXPOSE 8000
CMD ["sh", "-c", "cd server && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
