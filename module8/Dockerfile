# Агент у контейнері. Збірка з кореня module8/:
#   docker build -t agentpro-m8 .
#   docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-... agentpro-m8
# Ключ — тільки через env/Secret Manager. В образі його немає.

FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir anthropic python-dotenv fastapi uvicorn

COPY config.py run.py api.py ./
COPY core/ core/
COPY domain/ domain/
COPY modules/ modules/
COPY data/ data/
RUN mkdir -p out

EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
