# Changelog

One section per release, newest first. The section for a version is shown to users when they update
(the "What's in it" box in updatecheck, and the "What's new" screen after the restart).

## 1.0.8 (continued)

- `help` is easier to use: the first screen has numbered groups (`help 3` opens group 3) and an "I want to..." table (see a folder, copy files, check the internet, update...); `help <command>` now shows the usage lines, examples and related commands from the manual; and you can ask in your own words: `help copy a file`, `help how do i check the internet` find the commands, best match first, understanding words like delete, folder, internet, wifi. `help find` explains the find command instead of searching.

- `ping` is simple again: `ping <host>` (also `-c count`, `-p port`, `host:port`) times TCP connections and ends with a summary; no more menu. It needs no special rights and works on every export.
- New text commands: `sort`, `uniq`, `cut`, `tr`, `tee`, `rev`, `tac`, `nl`, `seq`, `xargs`, `less` (also `more`), `time`, `watch`, `cal`, `basename`, `dirname`, `which`, `du`, `stat`, `env`.
- New network commands: `tracert` (also `traceroute`: the system's ICMP service on Windows, the kernel's error queue on Linux and the ISO, no special rights), `nslookup` (also `dig`, `host`: A, AAAA, MX, NS, TXT, CNAME, SOA and reverse lookups), `whois`, `curl`, `wget`, `netstat` (also `ss`), `ifconfig` (also `ipconfig`).
- New system commands: `arch`, `nproc`, `lscpu`, `id` (also `groups`), `who` (also `users`), `pgrep`.

- Seven new apps, all of them run on the live ISO / VMs: Flashcards (spaced repetition), Expenses (monthly summary), Habits (streaks), Pomodoro (focus timer), and the games Sokoban (five levels, checked solvable), Lights Out (always solvable, with hints) and Slide Puzzle (3x3, 4x4, 5x5).

- `updatecheck` on the ISO / VM images and installed systems now also refreshes the system package lists (`apk update`) and offers the waiting upgrades (`apk upgrade`) before the PythonOS update. On the live system the upgrades last until it is switched off (it says so, and the default is no); on an installed system they are kept.

- `installos` shows the real reason when the installer fails (the tool's error output was being dropped), keeps the full output in `/tmp/pythonos-install.log`, and checks before erasing anything that the package repositories can be reached.

- `installos` works in the VM images, which have only a boot disk and a data disk: the data disk can now be chosen as the target (with a clear warning that its saved files and accounts are erased; they are released first so the session keeps working), and when no disk can be used it lists every disk and why, and how to add one.

- Website: the App Library has a "Works on" filter (Windows, Linux, Android, ISO / VM), shows each app's exports on its card and detail window, the per-export start files of API 2, and the "Live USB" filter now also needs the ISO in the app's exports.

- `display 1280x720` now really changes the resolution on the ISO and VM images: the kernel restarts with that `video=` option (kexec, a few seconds, files kept) and the choice is applied again at every start. If the firmware refuses, nothing changes and it says so.

- Marketplace API 2: per-export run files (`run_windows`, `run_linux`, `run_android`, `run_iso` in `scripts`), checked by the catalog builder. Apps that need libraries or `exec` may leave the ISO out of their exports (ytaudio and python now say Windows and Linux; wifimeter says Linux and ISO).

## 1.0.8

- Windows installer: the progress text under the bar is no longer cut off; updating keeps `config.json` (your settings) but now brings its version up to date, so the system reports the new version (issues 1 and 5).
- YouTube Audio now plays the sound itself with pip libraries (`av`, `miniaudio`, installed by the marketplace): no mpv, VLC or ffplay, nothing outside PythonOS (issue 2).
- Commands and apps can limit themselves to some exports (`"exports"`): `installos`, `persist`, `hwsetup` and the new `display` exist only on the ISO/VM; apps must run on the ISO/VM and list the exports they work on, shown in the store and the App Library (issues 3 and 6).
- `updatecheck` on the live ISO / VM warns before downloading when there is no data disk to keep the update on (it would be gone after a restart); with the data disk (the VM images ship one) the update is kept (issue 4).
- Terminal window on Windows: tables and wrapped text no longer break after the window is resized (issue 7).
- New `display` command: change the console resolution on the ISO/VM; remembered at boot (issue 8).
- Long output of listing commands (`ls`, `cat`, `man`, `history`...) is shown a screen at a time (settings `auto_page`), since the Linux console cannot scroll back (issue 9).
- New setting `clear_style`: clear the screen before a command when the last output filled it (default) or before every command (issue 10).

- Website: a "How do you want to run it?" row of cards (Windows, Android, Linux, USB, virtual machine, Docker, Setup Wizard) that takes you to the right download, a "See it" section with the file manager, task manager and settings, new feature and app cards, a Setup Wizard banner, a Recommended mark on the main file of each platform, a questions section, and better detection notes.

## 1.0.7

- Marketplace API 2: a package may list Python libraries it needs (`"pip": ["yt-dlp"]` in its data.json, with `"api": 2`). The marketplace shows them before asking, installs them (wheels only, plain requirements only, from PyPI) into the app's own `.libs` folder, keeps them when the app updates unchanged, and removes them with the app. Not on locked-down systems, the Android app or the live ISO (no pip there). Older systems keep reading the API 1 catalog and never see these packages.
- New apps: AI Assistant (`assistant`, also `ai`): chat with OpenAI, Anthropic, Google Gemini, OpenRouter, Ollama or any OpenAI-compatible address. It asks which service, for your API key (hidden, kept only in your own folder, or not at all) and the model: pick from the list the service gives, or type its name; answers stream in. YouTube Audio (`ytaudio`): search YouTube, play a link or playlist, queue, plays the sound itself with pip libraries (API 2), no external player.
- `fm` (also `explorer`): a full-screen file manager with a folder list and a preview pane. Open folders, edit files, mark several with Space, copy / cut / paste (a taken name gets (2); nothing is overwritten), move to the trash with undo, rename, make files and folders, filter, sort, show hidden files. It follows the shell's permission rules. Without a full-screen terminal it lists the folder.
- The Settings app: `settings` opens every setting in one full-screen program, grouped (Display, System, Security, Updates, Storage, Power, Services, Apps, About). Change things in place, step through choices with the arrow keys, reset one with r, switch services on or off, and set the options of installed apps.
- `service` lists the background services and lets administrators stop, start, restart, enable and disable them; `limits` holds each marketplace app to a memory and processor-time limit (a quarter of PythonOS's memory by default, set per app by you or by the app).
- Setup Wizard (`pythonos-wizard-<version>.zip`, replaces the Python flash tool): a program for Windows and Linux that needs no Python (there is no Mac version: Macs use Docker or a virtual machine). It detects the computer (system, real processor also when emulated, what is installed), asks what you want (install here, Android, bootable USB stick, virtual machine with your choice of program, Docker, or any file), downloads the right file of the latest release, checks it against SHA256SUMS and does the next step. Window by default (light or dark like the system), `--cli` for the terminal, `--goal ... --yes` for scripts. Only the part that writes a USB stick runs elevated.
- Android: a small installer app (`PythonOS-<version>-android-installer.apk`, about 1 MB, no Python inside) finds out which processor the device has, downloads the right PythonOS app, checks it and hands it to Android's installer. The big universal APK is gone; the arm64 and x86_64 APKs stay.
- The release page has a table for every system (Windows, Android, Linux, macOS, Docker, bootable USB, virtual machines) saying which file to download for which situation, and the release carries `release-catalog.json`, a machine-readable list of every file with its system, processor and kind.
- Processor detection looks at the real processor (Windows on ARM running an x64 program, an Intel program under Rosetta, 32-bit programs on 64-bit systems): in the wizard, the Windows installer, the in-app updaters (Android picks the APK for the device's real ABI) and the website (graphics chip and browser report).
- Installers: the Windows installer shows the steps as dots and a time-remaining estimate while downloading; the Inno installer follows the system's dark mode.
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
