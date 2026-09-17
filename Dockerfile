# JobAgent Enterprise - Production Docker Image
# Multi-stage build for optimization

# ─── Stage 1: Build ───────────────────────────────────────────────
FROM python:3.11-slim-bullseye AS builder

# Set working directory
WORKDIR /app

# No system packages required: every dependency in requirements.txt ships a
# prebuilt CPython 3.11 manylinux wheel, so nothing is compiled from source.
# --only-binary=:all: makes the build fail fast with a clear error if any
# dependency ever lacks a wheel, instead of silently requiring a compiler.

# Copy requirements
COPY requirements.txt .

# Install Python dependencies (wheels only — no compiler available or needed)
RUN pip install --no-cache-dir --only-binary=:all: --user -r requirements.txt


# ─── Stage 2: Production ──────────────────────────────────────────
FROM python:3.11-slim-bullseye

# Set working directory
WORKDIR /app

# No runtime system packages needed:
# - no PostgreSQL client headers (psycopg2 is not in requirements.txt)
# - no curl (health check uses Python urllib instead)

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY . .

# Ensure instance directory exists for SQLite (PostgreSQL via DATABASE_URL bypasses this)
RUN mkdir -p /app/instance

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Add local packages to PATH
ENV PATH=/root/.local/bin:$PATH

# Port (hosting platforms like Render set $PORT dynamically)
ENV PORT=5000

# Expose port
EXPOSE 5000

# Health check (Python-based — no curl dependency)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

# Run with Gunicorn for production
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 4 --threads 2 --timeout 120 --access-logfile - --error-logfile - app:app"]
