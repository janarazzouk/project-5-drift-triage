FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./pyproject.toml

RUN pip install --no-cache-dir uv \
    && uv sync

COPY . .

EXPOSE 8501

CMD ["uv", "run", "streamlit", "run", "dashboard.py", "--server.address=0.0.0.0", "--server.port=8501"]