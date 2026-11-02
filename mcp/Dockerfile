FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY packages/axiom_research ./packages/axiom_research

RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin app \
    && chown -R app:app /app

USER app
ENV PORT=8080
EXPOSE 8080

# Override per service: axiom-mcp-literature | axiom-mcp-materials | axiom-mcp-research-data
CMD ["axiom-mcp-literature"]
