FROM python:3.12-slim

# Install uv
RUN pip install --no-cache-dir uv

# Create non-root user
RUN useradd -m -u 1000 simulator

# Copy the simulator repo (dependencies resolve from PyPI via uv.lock)
COPY . /app

# Set working directory
WORKDIR /app

# Install runtime dependencies plus provider plugins from the lockfile.
# No dev tooling: only the providers group is added on top of the
# project's runtime dependencies.
RUN uv sync --frozen --no-dev --group providers

# Switch to non-root user (AFTER all RUN/COPY)
USER simulator

# Expose port
EXPOSE 9000

# Run simulator with virtual environment
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "getpaid_simulator"]
