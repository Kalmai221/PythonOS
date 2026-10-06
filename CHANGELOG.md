# Changelog

One section per release, newest first. The section for a version is shown to users when they update
(the "What's in it" box in updatecheck, and the "What's new" screen after the restart).

## Unreleased

- You choose how much memory PythonOS owns: the first-time setup asks (512 MB, 1 GB, 2 GB, 4 GB or all), and both Windows installers ask on a fresh install (`/MEMORY=2048` or `/MEMORY=all` for silent installs). `settings set memory_limit_mb ...` now takes effect right away (no restart) and, on Windows, the system enforces the new limit.
- Export update strategies (`core/exportupdate.py`): `updatecheck` can now install a newer package of the export itself, always after asking and after checking the download against the release's `SHA256SUMS`. Windows: the web installer (as before). Linux: installed from a .deb, .rpm or Arch package, it downloads and installs the new package with your distribution's tool (sudo or pkexec asks for your password); from the tarball it replaces the launcher files in place. Android: the app downloads the APK and hands it to Android's installer, which asks you to confirm (needs the app signed with a stable key). Live ISO: it writes the new ISO over the disk the system started from, reads it back to check, and restarts. Docker: the image cannot change, but new Python libraries are installed onto the data volume so a core update that needs them goes ahead.
- Android APKs are signed with one permanent key (`tools/android_signing_setup.py` makes it; its fingerprint is pinned in `OS_Export/Android/signing.sha256`). CI checks every APK against the pin and refuses to publish a release signed with any other key, so each APK can be installed over the previous one, including by the in-app update. APKs from releases before this one were signed with throwaway keys: install the first signed one by uninstalling the old app once (the backup command keeps your files).
- Updates now survive restarts where the program files do not: on the live ISO with persistent storage, and in Docker with a volume, `updatecheck` also saves the new program files on the data disk (`.OSData/core_overlay`) and `core_overlay.py` puts them back at the next start. A newer image or ISO always wins over an older saved update, and every saved file is checked against its checksum.
- The `.qcow2` virtual machine disk has a matching `-vm-data.qcow2` data disk (attach it second and the VM keeps your accounts and files), like the OVA already had.
- Docker: `docker run -it --rm -v pythonos-data:/data ghcr.io/kalmai221/pythonos` really keeps your accounts, files, settings and updates (the old hint pointed at a folder PythonOS does not use). CI checks that a file written in one container is there in the next.

- The `bootspeed` command and the `boot_speed` setting are gone (boot pauses are a fixed short time; light mode has none). `bootlog` still shows what each start-up step took.
- More realistic boot and shutdown. Boot is a log with time stamps (seconds since PythonOS started), a header that says what it runs on (version, processor, memory, mode), "Loaded/Checked/Started/Mounted ..." lines for each real step, new real steps (hardware detection, kernel services, file system check) and a "Reached target" line with the start-up time. Shutdown stops the services that are really running, newest first ("Stopped Task Scheduler.", "Stopped Battery Monitor."...), warns when one does not answer, then jobs, sign-out, log and file system, and ends with "Reached target Power-Off."

## 1.0.6

- PythonOS owns a fixed amount of memory (setting `memory_limit_mb`, 1024 MB by default; 0 = the whole machine). `free`, `sysinfo` and the task manager show that amount as the whole computer, everything PythonOS runs counts as used, and on Windows the system enforces the limit. The live ISO always uses all of the machine's memory.
- Task manager (`taskman`, also `top`) and the new `ps` show PythonOS's own tasks instead of the host computer's processes: init, kernel, your shell, services (scheduler, battery and memory watch...), background jobs and whatever is open (marketplace, editor, games), each with a PID, parent, state, CPU time and memory. `kill <pid>` stops a job (or, for administrators, a service).
- The virtual machine appliance (.ova) now includes a 2 GB data disk, so accounts, files and settings are kept between runs (before, the live system forgot everything at power off and setup had to be redone).
- The marketplace has an API version (`pyos/marketapi.py`): packages say which one they were written for (`"api"`, default 1) and the catalog is published per version (`index-api<N>.json`, plus the unchanged `index.json` for the oldest systems), so the marketplace can change later without breaking systems already installed. Apps that need a newer PythonOS are hidden and refused with a clear message, and apps get `PYOS_PACKAGE_API` in their environment.
- Live ISO: shutdown and restart are shown entirely by PythonOS (jobs, sessions, data disk, system services) and the machine then powers off or restarts with no system messages on the screen.

## 1.0.5
- More processors: Windows on ARM (portable zip and installer; the web installer picks the right one), 64-bit ARM live ISOs (full and minimal, UEFI), a multi-architecture Docker image (amd64 and arm64)
- More Linux distributions: Arch and Manjaro (.pkg.tar.zst) and Fedora, RHEL, openSUSE (.rpm) packages next to the .deb and the tarball (all work on any processor)
- Android covers every processor Chaquopy supports for Python 3.13 (arm64-v8a and x86_64, plus the universal APK)
- The release page and website list the new files; extra builds never hold a release back

## 1.0.4
- Windows: the web installer now recognises older installs (made by the offline installer or a portable copy) and updates them in place, and an update no longer deletes files it does not own (it removed boot-requirements.txt, which stopped PythonOS starting)
- Every installer and launcher checks its requirements and downloads what is missing: the PythonOS system files and the Python libraries (Windows, Linux, Android); the web installer shows this as its own step
- Windows: both installers offer a Start menu shortcut and a desktop shortcut; the PythonOS window always shows colour, has a slim scrollbar, smooth wheel and keyboard scrolling, and a Latest button
- Windows: the web installer picks the ARM64 package on Windows on ARM when a release has one
- Linux: an Arch Linux package (.pkg.tar.zst) is built next to the .deb and .tar.gz
- Website: redesigned download and build status pages

## 1.0.3
- Trash and undo: rm moves things to a per-user trash; undo brings the last one back; trash lists, restores and empties
- Search tools: find (type, size, age, depth), grep (-r -n -c -l -v -w, context), tree options, and a new diff
- Admin actions are recorded (logs --admin) and the risky ones ask the administrator for their password again
- Apps can have settings pages: settings apps / settings app <app> (typing test, chess and weather use it)
- A much bigger tutorial (28 lessons, saves your place, jump with tutorial <n>), and screens clear themselves between menus and programs
- Realistic power: orderly shutdown with stop-job messages, restart is a fresh start, unexpected shutdowns are noticed (whathappened), real uptime, faster boot
- report prepares a redacted problem report you read first, then send as a GitHub issue link or a file
- The system's own messages speak Spanish, French and German (settings language, asked at first start)
- Live USB: network clock, memory check with light mode, press D for diagnostics (diag), battery warnings and clean shutdown, a two-minute quick start, storage suggestions, quiet boot with a splash
- installos: install PythonOS from the live USB onto a disk (experimental); full and minimal ISO images; VM images (.ova, .qcow2); a USB writer that checks and verifies
- Windows: PythonOS now opens in its own window (no Command Prompt), a tiny web installer (light and dark, four languages, checks every download, repair, uninstall), update in place from inside PythonOS
- Android: per-processor APKs (arm64 is about half the size), bottom-sheet menu and dialogs, colour schemes, hardware keyboard shortcuts, box drawing and tables line up
- Every release file is listed in SHA256SUMS (signed), with build provenance and a release page that says what each file is for

## 1.0.2
- Windows installer asks before updating an existing install; the uninstaller offers to delete your PythonOS data
- Restart after an update works; theme preview during setup
- help is now grouped by category, searchable and phone-friendly
- New blue screen with a stop code; the full crash report is saved in /var/log
- Idle logout (per user), zip/unzip/tar, logs filters and export, doctor, bootlog and bootspeed
- Updates download only the files that changed, resume if interrupted, and can be rolled back (rollback, whatsnew)
- Real boot and shutdown steps with progress bars
- cowsay, fortune and rainbow for practising pipes

## 1.0.1
- Marketplace dependencies, featured apps, changelogs and an offline cache; 13 new apps
- ISO persistent storage, keyboard layout, time zone and saved Wi-Fi; one merged first-time setup
