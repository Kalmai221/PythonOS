# PythonOS in a container:   docker run -it --rm ghcr.io/kalmai221/pythonos
# Keep your accounts, files and updates between runs:   docker run -it --rm -v pythonos-data:/data ghcr.io/kalmai221/pythonos
# Distrobox / Toolbx:   distrobox create --image ghcr.io/kalmai221/pythonos --name pythonos && distrobox enter pythonos
#
# CI builds this from the staged OS folder (OS_Export/stage.py) in the build context: payload/ plus tools_smoke.py.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 PYOS_BUNDLED=1 TERM=xterm-256color LANG=C.UTF-8

# the GitHub CLI, which the PythonOS `gh` command runs (and `report` uses to file a GitHub issue); the image still works without it
RUN (apt-get update && apt-get install -y --no-install-recommends gh ca-certificates && rm -rf /var/lib/apt/lists/*) || echo "gh is not available for this base image"

COPY payload/requirements.txt payload/requirements-extra.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt && (pip install --no-cache-dir -r /tmp/requirements-extra.txt || true) && rm /tmp/requirements*.txt

COPY payload/ /opt/pythonos/
COPY tools_smoke.py /opt/tools_smoke.py
WORKDIR /opt/pythonos

# user data (accounts, files, settings, updates) is kept on the volume mounted at /data; entrypoint.sh links it in
RUN mkdir -p /opt/pythonos/files /opt/pythonos/.OSData
COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh

# PYOS_BUNDLED=1: dependencies are in the image, so the OS never tries to run pip while starting
ENTRYPOINT ["/opt/entrypoint.sh"]
CMD ["python", "main.py"]
