FROM python:3.12-slim

# Install uv
RUN pip install --no-cache-dir uv

# Create non-root user
RUN useradd -m -u 1000 simulator

# Copy all sibling packages (build context is parent directory)
COPY getpaid-core/ /app/getpaid-core/
COPY getpaid-payu/ /app/getpaid-payu/
COPY getpaid-paynow/ /app/getpaid-paynow/
COPY getpaid-simulator/ /app/getpaid-simulator/

# Set working directory
WORKDIR /app/getpaid-simulator

# Install dependencies (no dev tools, include e2e group for PayU/PayNow)
RUN uv sync --group e2e --no-dev

# Switch to non-root user (AFTER all RUN/COPY)
USER simulator

# Expose port
EXPOSE 9000

# Run simulator with virtual environment
ENV PATH="/app/getpaid-simulator/.venv/bin:$PATH"
CMD ["python", "-m", "getpaid_simulator"]
