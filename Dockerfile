# JobAgent Enterprise - Production Docker Image
# Multi-stage build for optimization

# ─── Stage 1: Build ───────────────────────────────────────────────
FROM python:3.11-slim-bullseye AS builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt


# ─── Stage 2: Production ──────────────────────────────────────────
FROM python:3.11-slim-bullseye

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY . .

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

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run with Gunicorn for production
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 4 --threads 2 --timeout 120 --access-logfile - --error-logfile - app:app"]