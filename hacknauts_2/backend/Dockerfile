FROM python:3.12-slim

# Install dependencies: git, curl, ca-certificates, and k6 for load testing
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates && \
    # Install k6 via official repository
    curl -s https://dl.k6.io/key.gpg | gpg --dearmor -o /usr/share/keyrings/k6-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | tee /etc/apt/sources.list.d/k6.list && \
    apt-get update && apt-get install -y k6 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
RUN useradd -m appuser
USER appuser

