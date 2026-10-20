# ==========================================
# TraceGuard Backend Production Dockerfile
# Milestone 7: Production Deployment & Containerization
# ==========================================

FROM python:3.11-slim AS builder

WORKDIR /build

# Install compilation tools if any wheels require it
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final production stage
FROM python:3.11-slim AS runner

# Set secure execution environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/home/appuser/.local/bin:$PATH \
    TRACEGUARD_ENV=production \
    DATABASE_PATH=/app/data/traceguard.db \
    API_HOST=0.0.0.0 \
    API_PORT=8000

# Create non-root system user and group
RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application source code
COPY backend ./backend
COPY data ./data
COPY README.md ./

# Create data directory with appropriate non-root ownership for SQLite persistence
RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data /home/appuser/.local

# Switch to unprivileged non-root user
USER appuser

# Expose backend API service port
EXPOSE 8000

# Health check without relying on external curl
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; res = urllib.request.urlopen('http://localhost:8000/health'); exit(0 if res.getcode() == 200 else 1)"

# Production execution entrypoint
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
