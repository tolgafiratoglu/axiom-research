FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY packages/axiom_research ./packages/axiom_research
COPY api ./api
COPY verifier ./verifier

RUN pip install --no-cache-dir ".[a2a]" \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin app \
    && chown -R app:app /app

USER app
ENV PORT=9000
ENV VERIFIER_HOST=0.0.0.0
EXPOSE 9000

CMD ["python", "-m", "verifier"]
