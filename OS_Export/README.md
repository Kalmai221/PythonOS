# OS_Export

Everything GitHub Actions (or you, locally) need to turn PythonOS into installable
packages. Nothing in here changes how the OS itself runs.

| Folder | Produces | Contains the OS? |
|---|---|---|
| [`Linux/`](Linux) | `pythonos-<version>-linux.tar.gz` and `pythonos_<version>_all.deb` | No - downloads it on first run |
| [`Windows/`](Windows) | `PythonOS-<version>-windows-portable.zip` and `PythonOS-<version>-setup.exe` | No - downloads it on first start |
| [`Android/`](Android) | `PythonOS-<version>-android.apk`, an app | No - downloads it on first launch |
| [`ISO/`](ISO) | `pythonos-<version>-x86_64.iso`, a bootable live image | Yes - it is a live CD with no installer |

## How the OS gets onto a device, and how it updates

Every release has two extra files besides the installers: **`pythonos-core-<version>.zip`**
(the OS: `main.py`, `shell.py`, `users.py`, `commands/`, `core/`, `programs/`, `pyos/`, ...) and
**`core-manifest.json`** (version and SHA-256 checksums). They are built by
[`make_core.py`](make_core.py) and never contain marketplace packages, user data or build tooling.

* **Install:** the Linux, Windows and Android packages hold only a small launcher and
  [`bootstrap.py`](bootstrap.py). On first run `bootstrap.py` downloads the latest core from the
  newest GitHub release, verifies it, and installs it into the user's data folder. So a fresh
  install is always the latest release, and it needs internet once.
* **Update:** from inside PythonOS, the `sysupdate` command (it also runs on first setup) checks the
  newest release, downloads the core, verifies every file, swaps the core files in and rolls back if
  anything goes wrong. Users' files, accounts and `config.json` are never touched.
* **Packaged builds vs. a source checkout:** a folder with a `VERSION` file (written by `stage.py`) is
  a packaged build and updates from releases. A plain git checkout has no `VERSION` file and keeps
  updating from the repository's `main` branch.
* **Android and the ISO** ship their Python libraries and cannot install new ones. If a release adds
  a dependency, their updater says a new app/image is needed instead of installing a broken update.
* **ISO:** it is a live image that boots straight into the OS, so it carries the core inside. An
  update applies until the next reboot; build a new ISO for a permanent one.

### Two kinds of update

* **Core updates install themselves** (everything inside PythonOS: the shell, commands, apps, the updater).
* **Export updates can't.** The APK and its terminal screen, the Windows launcher and bundled Python, the Linux
  launcher and the ISO's kernel, boot menu and lockdown are the package *around* PythonOS and cannot be replaced
  from inside it. PythonOS detects these and says so plainly: *"A newer Android app is available ... PythonOS can't
  update it automatically"*, with the download links (`updatecheck`, and a notification after login). If a new core
  needs something the installed package lacks, the core update is held back and the user is told to install the new
  package first. Each export carries a tiny identity (`export.json`: platform, version, api); `version` shows it.

### Unchanged exports are not rebuilt

A release only builds the exports that actually changed. Before building, the `plan` job in the workflow fingerprints each
export's inputs (`OS_Export/inputs.py`; the files listed under `inputs` in `exports.json`) and compares them with the
fingerprints stored in the previous release's `core-manifest.json`. If they match and the old download still works, the
export's job is skipped, the new release **links to and re-attaches the old file**, and that export's version stays at the
release it last changed in (so installs of it are not told to update). Nothing to bump by hand.

* The Android, Windows and Linux packages do not contain the core, so **a core-only change skips all three**.
* The ISO embeds the core (`"embeds_core": true`), so it is rebuilt whenever the core changes. Set it to `false` if you would
  rather reuse the ISO and let it self-update the core on each boot.
* Manual runs from the Actions tab, re-runs of an existing tag, and the first release with fingerprints build everything.
* If an export that had to be built fails, the release is not published (its manifest would link to a missing file).
* `exports.json` still holds the one thing that is a decision: **`api`**. Raise it when a core change needs something older
  packages lack; that also forces the export to rebuild, and older packages are held back from the new core until reinstalled.

`PYOS_UPDATE_URL` can point the downloader and updater at a different `core-manifest.json`
(self-hosting, testing).

## What a release contains

The release page (written by `release_notes.py` from `CHANGELOG.md`) lists every file with its size and what it is for. In short:

| Platform | Files |
|---|---|
| Windows | `PythonOS-<v>-web-setup.exe` (100 KB; downloads and checks the rest, light/dark, four languages, repair and uninstall), `PythonOS-<v>-setup.exe` (offline Inno Setup installer), `PythonOS-<v>-windows-portable.zip`. `PythonOS.exe` is its own window (WebView2 + xterm.js + ConPTY, `Windows/native/host`); `PythonOS-console.exe` is the plain console it falls back to. |
| Android | `PythonOS-<v>-android-installer.apk` (about 1 MB: finds the right app for the device, downloads and checks it, installs it; module `OS_Export/Android/installer`), `PythonOS-<v>-android-arm64-v8a.apk` (nearly every phone) and `-x86_64.apk`. There is no universal APK any more |
| Linux | `.deb` and `.tar.gz`; also a Docker image, `ghcr.io/kalmai221/pythonos` |
| ISO | `pythonos-<v>-x86_64.iso` (full: Bluetooth, printing, `installos`, VM guest tools), `-minimal-x86_64.iso`, the VM images (`-vm.ova`, `-vm.qcow2`, `-vm-kit.zip`) and the Setup Wizard `pythonos-wizard-<v>.zip` (own export: `OS_Export/Wizard`, built per system by CI) |
| All | `SHA256SUMS`, `SHA256SUMS.sigstore.json` (keyless signature) and build provenance attestations |

`COMPATIBILITY.md` says what each is tested on. The download page and the build status page (`site/`, published to GitHub Pages by
`.github/workflows/site.yml`; turn on Settings > Pages > Source: GitHub Actions once) read the same GitHub data.

### Re-running after a failed build

Every export job uploads its files as an Actions artifact named `export-<platform>[-<variant>]-<fingerprint>-<version>`. When a tag is run
again (for example after fixing the ISO), `plan.py` finds the artifacts of the earlier run whose inputs are unchanged and the release job
takes them instead of building again; only what failed is rebuilt. Exports unchanged since the previous release are still linked, not rebuilt.

### Other workflows

* `test.yml` - every push and pull request: lockdown audit, catalog index check, `tools/smoke_test.py` (starts PythonOS and runs real commands) on Linux and Windows
* `security.yml` - weekly `pip-audit` and the lockdown audit; opens an issue when a dependency is vulnerable
* The release job fails if `pip-audit` finds a vulnerable dependency; set the repository variable `ALLOW_VULNERABLE=true` to publish anyway

## Building with GitHub Actions

The workflow is [`.github/workflows/build-os.yml`](../.github/workflows/build-os.yml).

* **Manual run:** Actions tab → *Build PythonOS* → *Run workflow*. Each platform's output is
  attached to the run as an artifact.
* **Release:** push a tag such as `v1.2.0`. All builds run, and the installers plus the core update
  package are attached to a GitHub release.

```bash
git tag v1.2.0
git push origin v1.2.0
```

> The installers download the core from the **latest published release**, so the first release must
> exist before they can install anything. Builds from a manual run (no release) fetch whatever the
> latest release currently is.

## Building locally

From the repository root (set `VERSION` to stamp a version, otherwise `config.json`'s is used):

```bash
VERSION=1.2.0 bash OS_Export/Linux/build.sh          # -> dist/linux/
VERSION=1.2.0 bash OS_Export/ISO/build-iso.sh        # -> dist/iso/   (needs Docker)
VERSION=v1.2.0 python OS_Export/make_core.py         # -> dist/core/  (the release's update package)
```

```powershell
$env:VERSION = "1.2.0"; ./OS_Export/Windows/build.ps1   # -> dist\windows\
```

```bash
cp OS_Export/bootstrap.py OS_Export/Android/app/src/main/python/bootstrap.py
cd OS_Export/Android && gradle assembleRelease          # -> app/build/outputs/apk/release/
```

`stage.py` copies the OS files into a folder (used by `make_core.py` and the ISO). It refuses to
include anything that is not part of the OS, such as `online_packages/`. If you add a new top-level
file or folder to the OS, add it to `PAYLOAD_FILES` / `PAYLOAD_DIRS` there.

## Notes per platform

**Linux** - the launcher keeps each user's files, accounts and a private virtual environment in
`~/.local/share/pythonos` (override with `PYTHONOS_HOME`), so the install location can be read-only.

**Windows** - the package carries its own Python (the official *embeddable* build) with all
dependencies, so nothing has to be installed. `PythonOS.exe` is a small PyInstaller launcher that
starts it. PythonOS itself is deliberately *not* frozen into one exe: it loads commands and
marketplace packages from disk and installs packages with pip, which a frozen exe cannot do.
The installer puts PythonOS in `%LOCALAPPDATA%\PythonOS` (no admin rights needed) because the OS
writes its files next to itself.

**Android** - a real app: a terminal screen (with colours) that runs PythonOS through
[Chaquopy](https://chaquo.com/chaquopy/). The OS is downloaded into the app's private storage on
first launch, and users' files survive app updates. Differences from desktop: pip is not available
(dependencies ship in the app, `PYOS_BUNDLED=1`), so marketplace packages that install pip
libraries (Chess, Typing Test, IPython) cannot be set up there; the rest work. `shutdown` closes
the app. Android only installs an update over an installed app when both are signed with the same key, so releases are
signed with one permanent key: run `python tools/android_signing_setup.py` once (it makes the key outside the repository and pins its
fingerprint in `OS_Export/Android/signing.sha256`), back the key up, then `--upload` stores it as the repository secrets CI reads
(`ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`). CI checks that every APK carries
the pinned key and refuses to publish a release that does not. Without the secrets (a branch build) the APK is signed with a throwaway
key: fine for sideloading, but it cannot update or be updated by another build. Losing the key means everyone must uninstall and
reinstall once, so keep a backup. The in-app update (`updatecheck`, or Menu, Check for app update) downloads the new APK, checks it
against the release checksums and hands it to Android's installer, which asks you to confirm.

**ISO** - an Alpine Linux live image built with Alpine's `mkimage`. It boots (BIOS or UEFI)
straight into PythonOS on the first console and powers off when you shut PythonOS down; Alt+F2 is
a recovery shell. It is a live CD: everything runs from RAM and is lost at power off. Try it with
`qemu-system-x86_64 -m 1024 -cdrom pythonos-<version>-x86_64.iso`.
It uses Alpine's full `lts` kernel with the complete firmware bundle, so it boots normal PCs and
most Wi-Fi cards and GPUs work. On every boot it offers a hardware setup (also available any time
as the `hwsetup` command): a hardware and firmware check, choosing and testing the audio output,
and picking a network and connecting to the internet (wired or Wi-Fi). Building locally with
`ISO_KERNEL=virt` gives a smaller image that only suits virtual machines.

## Keeping data on the ISO

A live system forgets everything at power-off. `persist create` (an administrator, inside PythonOS) turns a USB stick or spare
disk into a data disk labelled `PYOS_DATA` and copies the accounts, files and settings onto it. At boot,
`ISO/overlay/pythonos-persist` mounts that disk (`nosuid,nodev,noexec`) and points PythonOS's `files/`, `.OSData/` and account
database (`PYOS_USERS_FILE`) at it. `persist` never offers the disk PythonOS booted from, or anything that is mounted, and the
build fails if the persistence script could start a shell or mount without `noexec`. The keyboard layout, time zone, audio output
and known Wi-Fi networks chosen in `hwsetup` are saved in the same place and re-applied at every boot.

## Windows installer artwork

`Windows/make_art.py` draws the installer's wizard images and icon (Pillow) at build time, so the repository holds no binary art.
Change the colours or text there.

## The ISO is locked down

The ISO exists to run PythonOS and nothing else, so the Linux system underneath is closed off:

* **Boot menu:** the BIOS menu has no `boot:` prompt and cannot be interrupted or given options; the UEFI
  (GRUB) menu cannot be edited or opened to a command line (the password is random per build and thrown away).
  So `init=/bin/sh` and friends are not possible.
* **Consoles:** `inittab` starts only PythonOS. No login, no `getty`, no shell on any virtual terminal or the
  serial port, root cannot log in anywhere, and SysRq is off. If PythonOS stops it is restarted, never replaced
  by a shell; `shutdown` powers off.
* **Inside PythonOS:** `PYOS_LOCKDOWN=1` turns on lockdown mode (`pyos/lockdown.py`): no external editor, no way to
  list or kill other processes, installer scripts never run, and marketplace packages only run if the catalog marks
  them `lockdown_safe` **and** their files still match the hashes recorded when they were installed (that record is in
  `.OSData`, which PythonOS commands cannot write), so a package planted by hand does not run. The filesystem sandbox
  also resolves symlinks.
* **Checked on every build:** `tools/audit_lockdown.py` fails CI if OS code starts spawning processes or evaluating code
  without being reviewed, and `in-container.sh` opens the finished ISO and fails the build unless the boot configs are
  locked, `inittab` has no login or shell, and the session cannot fall back to one.

What this cannot stop: someone with the machine in front of them can still boot different media, open the BIOS/UEFI
setup, or read the ISO file itself; and if the boot media cannot be found at all, Alpine's own initramfs may offer an
emergency shell before PythonOS has started. The same lockdown mode works on any build with `"lockdown": true` in
`config.json` (for a kiosk or a shared machine).

## Bundled mode

Builds that cannot run pip at runtime (Android, ISO) start the OS with `PYOS_BUNDLED=1`. In that
mode `main.py` and the boot sequence skip dependency installation and the internet check, and a
`site-packages` folder next to `main.py` is added to the import path.
