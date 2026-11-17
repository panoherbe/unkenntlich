# Unkenntlich: läuft auf dem eigenen Rechner, ohne Internet, ohne Grafikkarte.
#   docker compose up -d --build   →   http://localhost:8080
FROM python:3.13-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr ffmpeg libglib2.0-0 \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# PyTorch nur für die CPU, feste Fassung (geprüft am 17.11.2026).
RUN pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt /tmp/requirements.txt
# ultralytics zieht opencv-python mit; es bleibt nur die Variante ohne Bildschirm.
RUN pip install -r /tmp/requirements.txt \
 && pip uninstall -y opencv-python opencv-contrib-python || true \
 && pip install --force-reinstall --no-deps opencv-python-headless==5.0.0.93

# Modelle beim Bauen laden, jede Datei mit fester Prüfsumme; danach kein Netz mehr nötig.
COPY werkzeuge/modelle_laden.py /tmp/modelle_laden.py
RUN python /tmp/modelle_laden.py /modelle

# Kein Nachladen, keine Statistik an Dritte.
ENV UNKENNTLICH_MODELLE=/modelle UNKENNTLICH_DATEN=/daten TESSDATA_PREFIX=/modelle/tessdata \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 YOLO_OFFLINE=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics DO_NOT_TRACK=1 OMP_NUM_THREADS=8 OPENCV_LOG_LEVEL=ERROR
RUN mkdir -p /tmp/ultralytics && python -c "from ultralytics import settings; settings.update({'sync': False})" \
 && chmod -R a+rwX /tmp/ultralytics

WORKDIR /app
COPY pyproject.toml /app/
COPY unkenntlich /app/unkenntlich
COPY pruefsatz /app/pruefsatz
RUN mkdir -p /daten && chmod 1777 /daten
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/api/gesundheit')"
CMD ["uvicorn", "unkenntlich.server:app", "--host", "0.0.0.0", "--port", "8080"]
