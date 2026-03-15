# Sandboxed container for static security analyzers.
# Slither and Mythril are installed in separate virtual environments
# because they have incompatible dependency trees.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=180 \
    PIP_PREFER_BINARY=1

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libssl-dev libffi-dev curl git && \
    rm -rf /var/lib/apt/lists/*

# Install solc-select globally and a default solc version
RUN pip install --prefer-binary solc-select && \
    solc-select install 0.8.19 && \
    solc-select use 0.8.19

# Slither venv
RUN python -m venv /opt/slither-env && \
    /opt/slither-env/bin/pip install --upgrade pip setuptools wheel && \
    /opt/slither-env/bin/pip install --prefer-binary slither-analyzer==0.10.4

# Mythril venv
RUN python -m venv /opt/mythril-env && \
    /opt/mythril-env/bin/pip install --upgrade pip setuptools wheel && \
    /opt/mythril-env/bin/pip install --prefer-binary mythril==0.24.8

# App dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --prefer-binary -r requirements.txt

COPY app.py .

RUN mkdir -p /tmp

EXPOSE 8001

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
