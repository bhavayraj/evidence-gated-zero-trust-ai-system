# Build once, before the demo, with network access:
#   docker build -t agent-sandbox .
#
# executor.py then runs containers from this image with --network=none —
# deps are already baked in, so no network is needed AT RUN TIME.

FROM python:3.11-slim
RUN pip install --no-cache-dir pytest ruff
WORKDIR /scratch
