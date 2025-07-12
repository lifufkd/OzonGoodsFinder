FROM mcr.microsoft.com/playwright/python:v1.53.0-jammy

RUN apt-get update && apt-get install -y \
    fonts-noto \
    fonts-liberation \
    fonts-dejavu \
    fonts-freefont-ttf \
    libasound2 \
    libnss3 \
    libxss1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgtk-3-0 \
    libgbm1 \
    xvfb \
    x11-utils \
    x11-apps \
    dos2unix \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .
COPY requirements.txt .
COPY entrypoint.sh .
COPY parser.sh .

# Приводим к UNIX-формату и даём права на исполнение
RUN dos2unix ./entrypoint.sh
RUN chmod +x ./entrypoint.sh
RUN dos2unix ./parser.sh
RUN chmod +x ./parser.sh

RUN pip install --upgrade pip && pip install -r requirements.txt

ENTRYPOINT ["./entrypoint.sh"]
