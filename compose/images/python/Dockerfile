FROM python:3.11-slim-bookworm

ARG GROUP
WORKDIR /srv
COPY pyproject.toml .
RUN pip install --no-cache-dir -U "pip>=25.1" && pip install --no-cache-dir --group "$GROUP"

ENV PYTHONPATH=/srv PYTHONUNBUFFERED=1
