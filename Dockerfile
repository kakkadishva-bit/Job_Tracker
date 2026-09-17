# JobAgent Enterprise - Production Docker Image
# Multi-stage build for optimization

# ─── Stage 1: Build ───────────────────────────────────────────────
FROM python:3.11-slim-bullseye AS builder

# Set working directory
WORKDIR /app

# Every dependency ships a prebuilt CPython 3.11 manylinux wheel, and
# --only-binary=:all: makes the build fail fast if any ever lacks a wheel,
# so no compiler is needed. The virtualenv lives under /opt — NOT /root —
# because the production stage runs as the non-root appuser, which cannot
# access /root; executables (gunicorn, python) must be world-executable.

RUN python -m venv /opt/venv

# Copy requirements
COPY requirements.txt .

# Install Python dependencies into /opt/venv (no --user, wheels only)
RUN /opt/venv/bin/pip install --no-cache-dir --only-binary=:all: -r requirements.txt


# ─── Stage 2: Production ──────────────────────────────────────────
FROM python:3.11-slim-bullseye

# Set working directory
WORKDIR /app

# No runtime system packages needed:
# - no PostgreSQL client headers (psycopg2 is not in requirements.txt)
# - no curl (health check uses Python urllib instead)

# Copy the virtualenv from the builder (root-owned, world-readable and
# world-executable, so the appuser runtime can run its binaries)
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Ensure instance directory exists for SQLite (PostgreSQL via DATABASE_URL bypasses this)
RUN mkdir -p /app/instance

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Use the virtualenv executables (gunicorn, python) in production
ENV PATH="/opt/venv/bin:$PATH"

# Port (hosting platforms like Render set $PORT dynamically)
ENV PORT=5000

# Expose port
EXPOSE 5000

# Health check (Python-based — no curl dependency)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

# Run with Gunicorn for production
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 4 --threads 2 --timeout 120 --access-logfile - --error-logfile - app:app"]
