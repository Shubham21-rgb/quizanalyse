FROM python:3.9-slim

# Install required OS dependencies for Playwright first
RUN apt-get update && apt-get install -y \
    wget gnupg libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libasound2 \
    libpangocairo-1.0-0 libpango-1.0-0 libcairo2 libx11-xcb1 libx11-6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install dependencies (while still root)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser runtime + deps
RUN playwright install --with-deps chromium

# Create user AFTER dependencies are installed
RUN useradd -m -u 1000 user
USER user

ENV PATH="/home/user/.local/bin:$PATH"

# Copy project files as non-root user
COPY --chown=user . .

EXPOSE 7476

# Start FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7476"]
