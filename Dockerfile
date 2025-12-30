FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt \
    && useradd -m -u 10001 appuser

COPY snode_alert.py /app/snode_alert.py

USER appuser

ENTRYPOINT ["python", "snode_alert.py"]
