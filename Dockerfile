FROM python:3.12-slim

# Install FFmpeg and python3-venv (for spotdl if needed)
RUN apt-get update && \
    apt-get install -y ffmpeg python3-venv curl unzip && \
    rm -rf /var/lib/apt/lists/*

ENV DENO_VERSION=v2.5.5
RUN curl -fsSL -o /tmp/deno.zip "https://github.com/denoland/deno/releases/download/${DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip" && \
    unzip /tmp/deno.zip -d /usr/local/bin && \
    rm -f /tmp/deno.zip

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m venv /opt/spotdl && \
    /opt/spotdl/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/spotdl/bin/pip install --no-cache-dir spotdl

COPY . .

CMD ["python", "-m", "bot.main"]
