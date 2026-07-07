FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /tmp/recon-scraper-requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/recon-scraper-requirements.txt \
    && python -m playwright install --with-deps chromium

COPY . ./scraper

CMD ["python", "-m", "scraper.main", "--all", "--write-db", "--headless", "--facebook-browser", "chromium"]
