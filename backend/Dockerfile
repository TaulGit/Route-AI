FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements-agent.lock.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

ENV PORT=8000
EXPOSE 8000

CMD ["uvicorn", "app.api.agent_app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

