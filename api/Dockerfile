FROM python:3.12-slim

WORKDIR /app

# Provider keys come from the Compose secrets mount — never COPY .env.
COPY pyproject.toml ReadMe.md ./
# hatchling expects README.md when present in metadata; keep both names.
RUN cp ReadMe.md README.md
COPY packages/axiom_research ./packages/axiom_research
COPY api ./api
COPY verifier ./verifier

RUN pip install --no-cache-dir ".[a2a]" \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin app \
    && chown -R app:app /app

USER app
ENV PORT=8080
ENV AXIOM_LIVE_BOOTSTRAP=1
EXPOSE 8080

# compose secrets
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
