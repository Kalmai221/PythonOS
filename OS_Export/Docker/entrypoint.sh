#!/bin/sh
# Container entrypoint. With a volume mounted on /data, your accounts, files, settings and PythonOS updates are kept there:
#
#   docker run -it --rm -v pythonos-data:/data ghcr.io/kalmai221/pythonos
#
# Without a volume nothing is kept (a container starts empty every time) and PythonOS says so at the first start.
# Any other command is run as it is:  docker run --rm <image> python /opt/tools_smoke.py --dir /opt/pythonos
set -e
HOME_DIR=/opt/pythonos
DATA=/data
cd "$HOME_DIR"

if grep -q " $DATA " /proc/self/mountinfo 2>/dev/null && [ -w "$DATA" ]; then
    mkdir -p "$DATA/files" "$DATA/.OSData"
    # first use: keep the standard folder layout the image ships with
    if [ -z "$(ls -A "$DATA/files" 2>/dev/null)" ] && [ -d "$HOME_DIR/files" ] && [ ! -L "$HOME_DIR/files" ]; then
        cp -a "$HOME_DIR/files/." "$DATA/files/" 2>/dev/null || true
    fi
    for name in files .OSData; do
        [ -L "$HOME_DIR/$name" ] || rm -rf "${HOME_DIR:?}/$name"
        [ -L "$HOME_DIR/$name" ] || ln -s "$DATA/$name" "$HOME_DIR/$name"
    done
    export PYOS_USERS_FILE="$DATA/users.json"
    # libraries a newer core needs are installed here by updatecheck (the image cannot change); they come first on the search path
    export PYOS_LIBS_DIR="$DATA/site-packages"
    mkdir -p "$PYOS_LIBS_DIR"
    export PYTHONPATH="$PYOS_LIBS_DIR${PYTHONPATH:+:$PYTHONPATH}"
    export PYOS_PERSISTENT=1
    # an update made with updatecheck is saved on the volume too; a newer image replaces it (see core_overlay.py)
    export PYOS_CORE_OVERLAY=1
    python core_overlay.py >/dev/null 2>&1 || true
else
    export PYOS_VOLATILE=1
fi

if [ "$#" -eq 0 ]; then
    set -- python main.py
fi
exec "$@"
