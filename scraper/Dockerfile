FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/scraper

WORKDIR /app

COPY requirements.txt /tmp/recon-scraper-requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini xvfb xauth \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/recon-scraper-requirements.txt \
    && python -m playwright install --with-deps chrome

RUN groupadd --gid 10001 scraper \
    && useradd --uid 10001 --gid scraper --create-home --home-dir /home/scraper --shell /usr/sbin/nologin scraper \
    && mkdir -p /app/scraper/.logs /app/scraper/.state /app/scraper/facebook/.facebook-profile \
    && chown -R scraper:scraper /app /home/scraper

COPY --chown=scraper:scraper . ./scraper

USER scraper

ENTRYPOINT ["tini", "--", "xvfb-run", "-a", "--server-args=-screen 0 1365x768x24"]
CMD ["python", "-m", "scraper.scheduler", "--once", "--write-db"]
