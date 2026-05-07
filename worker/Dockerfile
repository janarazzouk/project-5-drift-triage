FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./

RUN uv sync --no-dev

COPY . .

CMD ["uv", "run", "python", "-m", "app.main"]