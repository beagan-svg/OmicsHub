# One image, four processes: web, both Celery workers, and beat all run from it, differing
# only by command. That is deliberate — they cannot drift apart on dependency versions,
# which matters most for the submission worker, the one process that shells out to `ocs`.

FROM python:3.12-slim AS build

# Wheels cover almost everything; build-essential is here for the few sdists in the
# aibs-informatics tree that still compile. It stays in this stage and out of the runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# A venv rather than the system site-packages, so the runtime stage can take the whole
# tree with one COPY and nothing else.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /src

# Dependencies before source: this layer is the slow one, and it should not rebuild every
# time a template changes.
#
# Two files, two jobs. pyproject.toml says *what* this project depends on and stays the one
# place a dependency is added or removed. requirements.lock says *which versions*, resolved
# from pyproject once and committed — without it `django>=5.2,<6.0` means two builds of the
# same commit can ship two different Djangos, and the one that breaks is the one built at
# 2 a.m. during an incident. `-r` installs the locked set exactly; `-c` applies the same
# pins to resolving `.`, so anything reachable from pyproject lands on a locked version or
# the build fails rather than drifting. CI checks the lock still matches pyproject.
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock -c requirements.lock .

# The `ocs` CLI. Installed properly into the venv rather than reached through the PYTHONPATH
# the interactive shell function sets up — which is what makes OCS_CLI_PYTHONPATH unnecessary
# in the container, and what makes the CLI work the same on every machine.
#
# Two steps because gcs-cli depends on the other three by name: they have to be installed
# before pip resolves it, or it goes looking for them on an index that does not have them.
#
# Deliberately NOT installed under `-c requirements.lock`, unlike the app's own dependencies
# above, because it would fail today: gcs-core requires `boto3~=1.35.12` while the lock —
# resolved from this project's own `boto3>=1.35` — carries 1.43.x. So this step downgrades
# boto3 for the whole venv, and the image's boto3 is not the one the test suite ran against.
# It has worked because the app's floor is 1.35 either way. Narrowing pyproject's boto3 to
# match gcs-core, or lifting gcs-core's cap upstream, is the fix; both are decisions for
# whoever owns the OCS dependency, so this records the situation rather than guessing.
COPY vendor/gcs/ ./gcs/
RUN pip install --no-cache-dir ./gcs/gcs-core ./gcs/gcs-api-client ./gcs/gcs-docker-tools \
    && pip install --no-cache-dir ./gcs/gcs-cli


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Nothing here runs as root. The uid is a build arg because the AWS credentials file is
# bind-mounted from the host at mode 600: Docker Desktop maps ownership for you, but on a
# Linux host the container user has to be the file's owner to read it.
ARG APP_UID=1000
RUN useradd --create-home --uid "$APP_UID" app

COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app . .

# collectstatic writes here at container start, so it has to belong to the app user. Owned
# rather than a volume: the files are rebuilt from the image on every start and are not
# state anyone needs to keep.
RUN mkdir -p /app/staticfiles && chown app:app /app/staticfiles

USER app

EXPOSE 8000

# No default CMD. Every service in compose.yaml names its own command, and a container
# started without one should fail loudly rather than quietly run the wrong process.
