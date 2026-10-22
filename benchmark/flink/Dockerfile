FROM python:3.11-slim-bookworm

# apache-flink publishes no aarch64 wheel; build-essential lets pip compile it natively,
# so Flink runs on the same architecture as the Spark image it is compared with.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -U "pip>=25.1" && pip install --no-cache-dir "apache-flink==2.2.1" pyyaml

WORKDIR /srv
ENV PYTHONPATH=/srv PYTHONUNBUFFERED=1
