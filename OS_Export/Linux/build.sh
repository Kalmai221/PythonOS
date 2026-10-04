#!/usr/bin/env bash
# Build the Linux packages:  dist/linux/pythonos-<version>-linux.tar.gz  and  pythonos_<version>_all.deb
#
#   VERSION=1.2.0 bash OS_Export/Linux/build.sh
#
# Needs: python3, tar. The .deb additionally needs dpkg-deb (present on Debian/Ubuntu runners).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="${OUT:-$REPO/dist/linux}"
VERSION="$(python3 "$REPO/OS_Export/stage.py" --print-version)"
NAME="pythonos-$VERSION-linux"

rm -rf "$OUT"
mkdir -p "$OUT/$NAME"

# --- portable tarball: extract anywhere and run ./pythonos
python3 "$REPO/OS_Export/stage.py" "$OUT/$NAME/app"
cp "$HERE/pythonos" "$OUT/$NAME/pythonos"
cp "$HERE/pythonos.desktop" "$OUT/$NAME/pythonos.desktop"
chmod +x "$OUT/$NAME/pythonos"
cat > "$OUT/$NAME/README.txt" <<EOF
PythonOS $VERSION

Run:  ./pythonos
Needs Python 3.8+ with venv support (Debian/Ubuntu: sudo apt install python3 python3-venv).
Your files and accounts are stored in ~/.local/share/pythonos (set PYTHONOS_HOME to change).
EOF
tar -C "$OUT" -czf "$OUT/$NAME.tar.gz" "$NAME"
echo "Built $OUT/$NAME.tar.gz"

# --- Debian package: installs to /opt/pythonos and adds /usr/bin/pythonos
if command -v dpkg-deb >/dev/null 2>&1; then
    DEB="$OUT/deb-root"
    mkdir -p "$DEB/DEBIAN" "$DEB/opt/pythonos" "$DEB/usr/bin" "$DEB/usr/share/applications"
    cp -R "$OUT/$NAME/app" "$DEB/opt/pythonos/app"
    cp "$HERE/pythonos" "$DEB/opt/pythonos/pythonos"
    chmod 755 "$DEB/opt/pythonos/pythonos"
    ln -s /opt/pythonos/pythonos "$DEB/usr/bin/pythonos"
    cp "$HERE/pythonos.desktop" "$DEB/usr/share/applications/pythonos.desktop"
    SIZE="$(du -sk "$DEB/opt" | cut -f1)"
    cat > "$DEB/DEBIAN/control" <<EOF
Package: pythonos
Version: $VERSION
Section: misc
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-venv, python3-pip
Installed-Size: $SIZE
Maintainer: Kalmai221 <noreply@github.com>
Homepage: https://github.com/Kalmai221/PythonOS
Description: PythonOS - a terminal-based operating system simulator
 A modular, terminal-based pseudo operating system written in Python,
 with a shell, users, a package marketplace and more.
EOF
    dpkg-deb --root-owner-group --build "$DEB" "$OUT/pythonos_${VERSION}_all.deb"
    rm -rf "$DEB"
    echo "Built $OUT/pythonos_${VERSION}_all.deb"
else
    echo "dpkg-deb not found - skipping the .deb"
fi

rm -rf "${OUT:?}/$NAME"
ls -la "$OUT"
