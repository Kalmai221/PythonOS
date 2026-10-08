#!/usr/bin/env bash
# Build the Linux packages, one per family of distributions (all are architecture independent: the same file runs on x86_64, arm64, armhf ...):
#   pythonos-<version>-linux.tar.gz          any Linux (Alpine, Void, Gentoo, NixOS ... unpack and run ./pythonos)
#   pythonos_<version>_all.deb               Debian, Ubuntu, Mint, Raspberry Pi OS
#   pythonos-<version>-1-any.pkg.tar.zst     Arch, Manjaro, EndeavourOS   (needs zstd)
#   pythonos-<version>-1.noarch.rpm          Fedora, RHEL, Rocky, AlmaLinux, openSUSE   (needs fpm and rpmbuild)
#
#   VERSION=1.2.0 bash OS_Export/Linux/build.sh
#
# The packages contain only a launcher and bootstrap.py - the OS itself is downloaded from the
# latest GitHub release on first run. Needs: python3, tar. The .deb additionally needs dpkg-deb.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="${OUT:-$REPO/dist/linux}"
VERSION="$(python3 "$REPO/OS_Export/stage.py" --print-version)"
NAME="pythonos-$VERSION-linux"

rm -rf "$OUT"
mkdir -p "$OUT/$NAME"

# --- portable tarball: extract anywhere and run ./pythonos
cp "$HERE/pythonos" "$OUT/$NAME/pythonos"
cp "$REPO/OS_Export/bootstrap.py" "$OUT/$NAME/bootstrap.py"
python3 "$REPO/OS_Export/stage.py" --write-export linux "$OUT/$NAME/export.json"   # which package this is (update detection)
cp "$HERE/pythonos.desktop" "$OUT/$NAME/pythonos.desktop"
chmod +x "$OUT/$NAME/pythonos"
cat > "$OUT/$NAME/README.txt" <<EOF
PythonOS $VERSION

Run:  ./pythonos
The first run downloads the latest PythonOS from GitHub (internet needed once), then sets up
a Python environment. PythonOS updates its own files after that.
Needs Python 3.8+ with venv support (Debian/Ubuntu: sudo apt install python3 python3-venv).
Your files and accounts are stored in ~/.local/share/pythonos (set PYTHONOS_HOME to change).
EOF
tar -C "$OUT" -cf - "$NAME" | gzip -9n > "$OUT/$NAME.tar.gz"
echo "Built $OUT/$NAME.tar.gz"

# --- one file tree for every distribution package: /opt/pythonos plus /usr/bin/pythonos and the menu entry.
# The packages hold only a launcher (a shell script) and bootstrap.py, so they are the same on every processor ("all" / "noarch" / "any").
ROOT="$OUT/pkg-root"
mkdir -p "$ROOT/opt/pythonos" "$ROOT/usr/bin" "$ROOT/usr/share/applications"
cp "$HERE/pythonos" "$ROOT/opt/pythonos/pythonos"
cp "$REPO/OS_Export/bootstrap.py" "$ROOT/opt/pythonos/bootstrap.py"
cp "$OUT/$NAME/export.json" "$ROOT/opt/pythonos/export.json"
chmod 755 "$ROOT/opt/pythonos/pythonos"
ln -s /opt/pythonos/pythonos "$ROOT/usr/bin/pythonos"
cp "$HERE/pythonos.desktop" "$ROOT/usr/share/applications/pythonos.desktop"
SIZE_KB="$(du -sk "$ROOT/opt" | cut -f1)"
DESCRIPTION="PythonOS - a terminal-based operating system simulator"
LONG="A modular, terminal-based pseudo operating system written in Python, with a shell, users, a package marketplace and more. Downloads and updates its own core files from GitHub releases."

# --- Debian, Ubuntu, Mint, Raspberry Pi OS ... : .deb
if command -v dpkg-deb >/dev/null 2>&1; then
    DEB="$OUT/deb-root"
    cp -a "$ROOT" "$DEB"
    mkdir -p "$DEB/DEBIAN"
    cat > "$DEB/DEBIAN/control" <<EOF
Package: pythonos
Version: $VERSION
Section: misc
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-venv, python3-pip
Installed-Size: $SIZE_KB
Maintainer: Kalmai221 <noreply@github.com>
Homepage: https://github.com/Kalmai221/PythonOS
Description: $DESCRIPTION
 $LONG
EOF
    dpkg-deb --root-owner-group --build "$DEB" "$OUT/pythonos_${VERSION}_all.deb"
    rm -rf "$DEB"
    echo "Built $OUT/pythonos_${VERSION}_all.deb"
else
    echo "dpkg-deb not found - skipping the .deb"
fi

# --- Arch Linux, Manjaro, EndeavourOS ... : .pkg.tar.zst (pacman -U). Same layout as makepkg's output: .PKGINFO plus the files.
if command -v zstd >/dev/null 2>&1; then
    PKG="$OUT/pacman-root"
    cp -a "$ROOT" "$PKG"
    cat > "$PKG/.PKGINFO" <<EOF
pkgname = pythonos
pkgbase = pythonos
pkgver = $VERSION-1
pkgdesc = $DESCRIPTION
url = https://github.com/Kalmai221/PythonOS
builddate = $(date +%s)
packager = Kalmai221 <noreply@github.com>
size = $((SIZE_KB * 1024))
arch = any
license = custom
depend = python
depend = python-pip
EOF
    (cd "$PKG" && tar --owner=0 --group=0 --numeric-owner -cf - .PKGINFO opt usr | zstd -19 -q -o "$OUT/pythonos-$VERSION-1-any.pkg.tar.zst")
    rm -rf "$PKG"
    echo "Built $OUT/pythonos-$VERSION-1-any.pkg.tar.zst"
else
    echo "zstd not found - skipping the Arch package"
fi

# --- Fedora, RHEL, Rocky, AlmaLinux, openSUSE ... : .rpm (needs fpm and rpmbuild; skipped if they are not installed)
if command -v fpm >/dev/null 2>&1 && command -v rpmbuild >/dev/null 2>&1; then
    fpm -s dir -t rpm -n pythonos -v "$VERSION" --iteration 1 --architecture noarch --license MIT \
        --url "https://github.com/Kalmai221/PythonOS" --maintainer "Kalmai221 <noreply@github.com>" --description "$DESCRIPTION" \
        --depends python3 --depends python3-pip -p "$OUT/pythonos-$VERSION-1.noarch.rpm" -C "$ROOT" opt usr >/dev/null
    echo "Built $OUT/pythonos-$VERSION-1.noarch.rpm"
else
    echo "fpm/rpmbuild not found - skipping the .rpm"
fi
rm -rf "$ROOT"

rm -rf "${OUT:?}/$NAME"
ls -la "$OUT"
