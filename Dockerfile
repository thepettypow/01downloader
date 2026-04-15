FROM python:3.12-slim

# Install FFmpeg and python3-venv (for spotdl if needed)
RUN apt-get update && \
    apt-get install -y ffmpeg python3-venv && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bot.main"]
