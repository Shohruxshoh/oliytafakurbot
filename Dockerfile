FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Tashkent

WORKDIR /app

# Avval faqat requirements — kod o'zgarganda pip qayta ishlamaydi (kesh)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY tests ./tests

# root ostida ishlatmaymiz
RUN useradd --create-home --uid 1000 botuser \
    && mkdir -p /app/data \
    && chown -R botuser:botuser /app
USER botuser

CMD ["python", "-m", "bot.main"]
