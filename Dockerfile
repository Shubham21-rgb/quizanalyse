FROM python:3.9-slim

# Create a non-root user
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy app code
COPY --chown=user . .

# Expose the port (must match README)
EXPOSE 7476

# Run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7890"]
