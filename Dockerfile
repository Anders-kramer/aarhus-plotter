FROM python:3.11-slim-bookworm
LABEL org.opencontainers.image.source="https://github.com/Anders-kramer/aarhus-plotter"
LABEL org.opencontainers.image.title="Aarhus Plotter"
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 libgomp1 && \
    rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    groupadd -g 10001 plotter && useradd -u 10001 -g plotter -M plotter && \
    mkdir /data && chown plotter:plotter /data
COPY app ./app
ENV DATA_DIR=/data PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
CMD ["uvicorn","app.main:create_app","--factory","--host","0.0.0.0","--port","8080","--workers","1","--no-access-log"]
