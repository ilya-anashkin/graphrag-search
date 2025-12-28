FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/home/app/.local/bin:${PATH}"

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN pip install --upgrade pip && \
    pip install . --no-warn-script-location

USER app

EXPOSE 8000

CMD ["uvicorn", "hybrid_graphrag_search.main:app", "--host", "0.0.0.0", "--port", "8000"]
