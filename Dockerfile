FROM python:3.12-slim AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /src

COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

# Install the four local packages before gcs-cli resolves them by name.
COPY vendor/gcs/ ./gcs/
RUN pip install --no-cache-dir --no-deps \
    ./gcs/gcs-core ./gcs/gcs-api-client ./gcs/gcs-docker-tools ./gcs/gcs-cli


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

ARG APP_UID=1000
RUN useradd --create-home --uid "$APP_UID" app

COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app manage.py ./
COPY --chown=app:app apps/ ./apps/
COPY --chown=app:app omicshub/ ./omicshub/
COPY --chown=app:app docker_tools/healthcheck.py ./docker_tools/healthcheck.py

RUN mkdir -p /app/staticfiles && chown app:app /app/staticfiles

USER app

EXPOSE 8000
