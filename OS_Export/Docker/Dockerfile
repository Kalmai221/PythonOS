# PythonOS in a container:   docker run -it --rm ghcr.io/kalmai221/pythonos
# Keep your accounts and files between runs:   docker run -it --rm -v pythonos-data:/opt/pythonos/data ghcr.io/kalmai221/pythonos
# Distrobox / Toolbx:   distrobox create --image ghcr.io/kalmai221/pythonos --name pythonos && distrobox enter pythonos
#
# CI builds this from the staged OS folder (OS_Export/stage.py) in the build context: payload/ plus tools_smoke.py.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 PYOS_BUNDLED=1 TERM=xterm-256color LANG=C.UTF-8

COPY payload/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY payload/ /opt/pythonos/
COPY tools_smoke.py /opt/tools_smoke.py
WORKDIR /opt/pythonos

# user data lives in these folders; mount a volume on them to keep it
RUN mkdir -p /opt/pythonos/files /opt/pythonos/.OSData /opt/pythonos/data

# PYOS_BUNDLED=1: dependencies are in the image, so the OS never tries to run pip while starting
CMD ["python", "main.py"]
