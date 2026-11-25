# Built by factory/adapter_click.py from a context holding click/ (the pinned
# checkout) and requirements.lock. Never use a floating tag in FROM.
FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b
ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock
COPY click /work/click
# Editable install: a patched copy mounted over /work/click at run time is what gets imported.
RUN pip install --no-cache-dir --no-deps --no-build-isolation -e /work/click
WORKDIR /work/click
