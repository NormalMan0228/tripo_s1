FROM python:3.13-slim
WORKDIR /app
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt && useradd -m -u 10001 tripothon
COPY server /app/server
COPY tools/backup_server.py /app/tools/backup_server.py
COPY game/assets/sample_stool.glb /app/game/assets/sample_stool.glb
# /health reports the release this image was built from (config/version).
COPY game/project.godot /app/game/project.godot
RUN mkdir -p /data /backups && chown tripothon:tripothon /data /backups
USER tripothon
ENV TRIPOTHON_DATA_DIR=/data TRIPOTHON_MODE=live
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765", "--workers", "1", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
