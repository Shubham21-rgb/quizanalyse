FROM python:3.9-slim

# Update first, then install deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget ca-certificates curl git \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libasound2 libpangocairo-1.0-0 libpango-1.0-0 libcairo2 \
    libx11-xcb1 libx11-6 libxss1 libxcursor1 \
    libdrm2 libgbm1 fonts-liberation ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install Python modules
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright engine + dependencies automatically
RUN playwright install --with-deps chromium

# Create non-root user
RUN useradd -m -u 1000 user
USER user

ENV PATH="/home/user/.local/bin:$PATH"

# Copy app
COPY --chown=user . .

EXPOSE 7476

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7476"]
