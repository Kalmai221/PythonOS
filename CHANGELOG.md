# Changelog

One section per release, newest first. The section for a version is shown to users when they update
(the "What's in it" box in updatecheck, and the "What's new" screen after the restart).

Every version is split by who gets the change: **PythonOS** (the core: `updatecheck` installs it by itself, and it is all PythonOS shows when it updates),
**Exports** (the packages around it: Windows, Android, Linux, the ISO and VM images, Docker; a new download is needed to get these), **Website** and
**Development** (tests and tools, not user-visible). Versions before 1.0.8 are not split and count as PythonOS.

## 1.0.12

### PythonOS

- New command `gh`: the real GitHub CLI, run in the PythonOS terminal (`gh issue list`, `gh pr list`, `gh auth login`, and everything else it does). PythonOS has no browser, so `gh auth login` shows a one-time code to approve on another device (your phone or another computer). In a pipe the output is captured, so `gh issue list | grep bug` works.
- `report` can now send a report for you. **GitHub**: it uses `gh`, asking you to sign in first on another device if needed, posts the report as an issue under your own account, and deletes the sign-in afterwards unless you choose to stay signed in. **Discord**, for people with no GitHub account: the report goes to the developer's channel. You read the whole report first and nothing is sent without your choice. `report status` shows the state and replies of a report you sent, with no sign-in. The Discord way is only offered once it is set up in the build.
- New command `sudo`: run one command as an administrator. An administrator confirms with their own password; a standard user gives an administrator's name and password and is a standard user again when the command ends. `sudo -k` forgets the password. Every use is in `logs --admin`.
- `doctor` (and any command that needs an administrator) now says why it did not see you as one, so a wrong refusal can be traced, and the account lookup no longer fails on a file it cannot read as text.
- PythonOS is a command line system and cannot open links: `report` no longer tries to open a browser or prints a very long pre-filled address. It saves the report and shows the short GitHub address to type on any device, with `share send` to move the file there. `updatecheck` says the same beside its download addresses, and a new test keeps browser opening and hyperlinks out of the system.
- `installos` no longer stops half way with "unable to select packages: acct, linux-lts (no such package)". It now checks, before erasing anything, that the base system can really be fetched; when the live system's repositories hold only the disc, it adds Alpine's online ones (and says no disk was touched if they cannot be reached).

### Exports

- Android: updating the app now really updates PythonOS. Installing a new app over an old one replaced the app but left the OS (kept in the app's own folder) at the old version, so it still showed the old version number and `updatecheck` still offered an update. The first start after the app changed now brings PythonOS up to the newest release (it tries again at the next start when offline). The version shown is also kept in step whenever the OS is downloaded or refreshed by a launcher.
- The Android installer app no longer offers the same app for ever. A release that only changed PythonOS itself carries the app of an older release, so installing it never produced the release's version number; the installer now compares the installed app with the version of the app file the release really carries, and says when the newest release is PythonOS only (it updates from inside with `updatecheck`, nothing to install).
- The ISO and virtual machine images (full variant) now include the GitHub CLI (`gh`), which they install as part of their own system. Every other export (Windows, Linux, Docker) does not install anything: the `gh` command offers to download GitHub's release into PythonOS's own folder the first time it is used. There is no `gh` on Android yet.

## 1.0.11

### PythonOS

- `doctor` is much more thorough: it also checks Python and the clock, memory, every command file, optional libraries, aliases that point at nothing, the schedule, storage and old crash reports. It gives a health score out of 100, says what is new or fixed since the last run, tells you what to do when it cannot fix something itself, and checks again after applying fixes. New options: `--online` (internet and newer releases), `--problems`, `--only`, `--json`, `--timings`, `--list`.
- `tracert` has a third way to send its probes that needs no rights (an unprivileged ICMP socket, which Android and Linux let programs use), and when the system refuses them all it lists why and what still works (`ping`, `nslookup`). `ifconfig`, `lscpu` and `netstat` no longer fail on Android, which hides the interface list, the processor load and the connection list from apps: they show what they can and say what is hidden.

### Apps

- Thirteen new apps. Seven need nothing extra and also run on the live USB: **Wikipedia** (`wiki`: summaries, search, random, other languages), **Dictionary** (`define`), **World Clock** (`worldclock`: `worldclock 15:00 london to tokyo`), **CSV Viewer** (`csvview`: sort, filter, columns, number summary), **Hex Viewer** (`hexview`), **Dice Roller** (`roll 4d6kh3+2`, advantage) and **Journal** (`journal`: a private diary with search). Six bring their own libraries (marketplace API 2, Windows and Linux): **Algebra** (`algebra solve x**2-4`, simplify, factor, diff, integrate; sympy), **Banner** (big letters in hundreds of fonts; pyfiglet), **Spell Checker** (`spell file notes.txt`, nine languages; pyspellchecker), **Plot** (charts in the terminal from numbers or a CSV; plotext), **PDF Reader** (`pdfread`: text by page, details, search; pypdf) and **Book Reader** (`epub`: chapters and text; ebooklib).
- New apps with libraries (marketplace API 2): **Units** (`pint`: `units 5 miles to km`, `units 20 degC to degF`, thousands of units) and **Image Viewer** (`Pillow` and `rich-pixels`: `imgview photo.jpg` draws a picture in colour in the terminal). Neither runs on the live USB.
- Improved apps: **RSS** reads feeds that are not valid XML (feedparser), **JSON Formatter** reads and writes YAML, **Date Calculator** understands "next friday" and, with dateutil, almost any date, **Password Generator** also spots common passwords and patterns (zxcvbn).

### Exports

- The Windows web installer now reads the version PythonOS really reports (not the one it last wrote to the registry), records that version, and says so when the newest files could not be downloaded instead of announcing an update that did not happen. The optional libraries are reinstalled after an update replaces the bundled Python.
- The Android installer app is redone: a calmer screen that follows the system's light or dark setting, a status card that says what is installed and what the latest version is (with its size and date), and the steps while it works (check, find, download, check, install) with the amount downloaded and the speed. New: a download that is cut off carries on where it stopped; a warning before a big download on mobile data; a clear step when Android has not yet allowed this app to install apps; **What is new** (the release notes), **Other versions** (install any of the last releases), **Uninstall**, and **Copy details** for a bug report. The downloaded file is now kept until PythonOS is installed (a failed install can be retried without downloading again) and is removed only after the install succeeds. When it does, a **successfully installed** screen shows the installed version, what to do next and an **Open PythonOS** button.

## 1.0.10

### PythonOS

- Optional libraries (new `requirements-extra.txt`; PythonOS uses each one when installed and works without it): `date -d "next friday"` and any date you write (python-dateutil); `file` says what a file is and `cat` no longer prints a picture or program as text (filetype; `cat --force` overrides); `web <url>` reads a web page as text with numbered links (beautifulsoup4, with a built-in fallback); `convert` turns JSON into YAML and back (PyYAML); `passwd` tells you honestly how strong a new password is (zxcvbn); better "did you mean" and help search (rapidfuzz); `uptime` in words (humanize).
- New apps with libraries (marketplace API 2): **Units** (`pint`: `units 5 miles to km`, `units 20 degC to degF`, thousands of units) and **Image Viewer** (`Pillow` and `rich-pixels`: `imgview photo.jpg` draws a picture in colour in the terminal). Neither runs on the live USB.
- Improved apps: **RSS** reads feeds that are not valid XML (feedparser), **JSON Formatter** reads and writes YAML, **Date Calculator** understands "next friday" and, with dateutil, almost any date, **Password Generator** also spots common passwords and patterns (zxcvbn).
- The DNS reader no longer raises on a damaged or cut-short answer (property testing found it): `nslookup` says so instead.
- A better prompt: with a real terminal, `Ctrl+R` searches your history as you type, a grey suggestion from your history appears (Right arrow accepts it), `Tab` shows a menu, and commands are coloured green when they exist and red when nothing could match. It works on Windows too. `history` can search (`history git`), show the last N, or clear (`-c`); `!!`, `!n`, `!-n` and `!word` repeat earlier commands. New settings `fancy_prompt` (off = the plain prompt) and `prompt_keys` (the prompt now uses emacs-style keys by default; `settings set prompt_keys vi` brings vi back).
- `cat` colours code, JSON, Markdown and other known file types on a terminal (`--plain` turns it off; piped output is never coloured).

### Exports

- The optional libraries (requirements-extra.txt) come with the Windows installer (installed once, in the background of the first start), the Linux launcher, the Docker image, the bootable USB and virtual machines (as Alpine packages) and, for the ones that are pure Python, the Android app.
- The Windows web installer now also applies the newest PythonOS files of the release (the core update, checked against the release checksums) on top of the package. A release does not rebuild a package that did not change, so it could hold an older PythonOS than the release is called: 1.0.9 re-attached the 1.0.8 Windows package, and installing or updating from it said it had updated while still running 1.0.8.
- The VM `.ova` imports in VirtualBox again: the empty third disk added in 1.0.9 had no data blocks at all, which VirtualBox cannot import (VERR_EOF). It now carries a short label, and the build stops if the disk has no data.

### Website

- The website is redone: plain typography, light and dark, and a download page that picks the right file for your computer. New documentation: getting started, a command reference generated from the manual, where PythonOS runs, recovery tools, the **Apps API** (package format, permissions, limits, settings, libraries, API versions, exports and run files), how to test and publish an app, **pull requests**, tests and CI, and releases.

### Development

- Property tests with hypothesis (`tools/test_properties.py`), tests of every optional-library feature with and without the library (`tools/test_libs.py`), of the library apps (`tools/test_pipapps.py`) and of the prompt (`tools/test_prompt.py`); `requirements-dev.txt` lists the libraries the tests and CI use. New docs page: Libraries.
- The website is built from `site_src/` by `tools/build_site.py` (the command reference is generated from the manual), and CI checks that `site/` is current and that its links and scripts work. There is now a `CONTRIBUTING.md` and a pull request template.

## 1.0.9

### PythonOS

- Recovery tools: an emergency console (read the logs and crash reports, pack them into a zip for a USB stick; no login, no shell) opened from the new boot menu (press M at the start, or `main.py --menu` / `--emergency`) or offered after repeated crashes; safe mode (`--safe`, or `safe on` in the emergency console) that leaves out marketplace apps, startup commands and background checks; crash reports are now also written ready to send, redacted, so `report --pending` works without a network.
- Shell variables and aliases: `NAME=value` and `export NAME=value`, then `$NAME` / `${NAME}` in any command (`$USER`, `$HOME`, `$HOST`, `$PWD` and `$?` always exist); `alias ll="ls -l"` (kept per person) and `unalias`; `unset`; `source <file>` (also `.`); and `~/.pyosrc` runs at every login. An exact command name now wins over another command's alias, and the old `export` alias of `backup` is gone (use `backup`).
- `help` is easier to use: the first screen has numbered groups (`help 3` opens group 3) and an "I want to..." table (see a folder, copy files, check the internet, update...); `help <command>` now shows the usage lines, examples and related commands from the manual; and you can ask in your own words: `help copy a file`, `help how do i check the internet` find the commands, best match first, understanding words like delete, folder, internet, wifi. `help find` explains the find command instead of searching.
- `ping` is simple again: `ping <host>` (also `-c count`, `-p port`, `host:port`) times TCP connections and ends with a summary; no more menu. It needs no special rights and works on every export.
- New text commands: `sort`, `uniq`, `cut`, `tr`, `tee`, `rev`, `tac`, `nl`, `seq`, `xargs`, `less` (also `more`), `time`, `watch`, `cal`, `basename`, `dirname`, `which`, `du`, `stat`, `env`.
- New network commands: `tracert` (also `traceroute`: the system's ICMP service on Windows, the kernel's error queue on Linux and the ISO, no special rights), `nslookup` (also `dig`, `host`: A, AAAA, MX, NS, TXT, CNAME, SOA and reverse lookups), `whois`, `curl`, `wget`, `netstat` (also `ss`), `ifconfig` (also `ipconfig`).
- New system commands: `arch`, `nproc`, `lscpu`, `id` (also `groups`), `who` (also `users`), `pgrep`.
- Seven new apps, all of them run on the live ISO / VMs: Flashcards (spaced repetition), Expenses (monthly summary), Habits (streaks), Pomodoro (focus timer), and the games Sokoban (five levels, checked solvable), Lights Out (always solvable, with hints) and Slide Puzzle (3x3, 4x4, 5x5).
- `updatecheck` on the ISO / VM images and installed systems now also refreshes the system package lists (`apk update`) and offers the waiting upgrades (`apk upgrade`) before the PythonOS update. On the live system the upgrades last until it is switched off (it says so, and the default is no); on an installed system they are kept.
- `installos` shows the real reason when the installer fails (the tool's error output was being dropped), keeps the full output in `/tmp/pythonos-install.log`, and checks before erasing anything that the package repositories can be reached.
- `installos` works in the VM images, which have only a boot disk and a data disk: the data disk can now be chosen as the target (with a clear warning that its saved files and accounts are erased; they are released first so the session keeps working), and when no disk can be used it lists every disk and why, and how to add one.
- New `timesync` command, and `updatecheck` points to it when a secure connection fails (a wrong clock is the usual cause).
- `updatecheck` and the "What's new" screen now show only the PythonOS part of a release (what the core update brings), under the title "What's new in PythonOS". A new package for your export is announced separately, with its own notes.
- `lscpu` works on Apple silicon Macs (it no longer stops when the system does not report a processor speed).

### Exports

- Automatic resolution: virtual machines whose console comes up small (under 1024 wide) switch by themselves to the biggest resolution the screen offers up to 1920x1080 (`display auto off` stops it). Needs the new ISO or VM image.
- The VM `.ova` ships a third, empty 8 GB disk for `installos`.
- The ISO and VM images react to the power button: VirtualBox's "Send the shutdown signal" (and the ACPI power button of QEMU, VMware and real computers) now starts PythonOS's own shutdown, with its shutdown screens, instead of being ignored. The image runs `acpid` with a small handler that signals PythonOS; if PythonOS has not taken it up within 30 seconds the machine powers off the normal way.
- The start-up script of the ISO and VM images opens the emergency console after three stops within two minutes. Needs the new ISO or VM image.

### Website

- Website: the App Library has a "Works on" filter (Windows, Linux, Android, ISO / VM), shows each app's exports on its card and detail window, the per-export start files of API 2, and the "Live USB" filter now also needs the ISO in the app's exports.

### Development

- Test CI is much wider: the smoke test on Linux, Windows and macOS and on Python 3.9 and 3.14; static checks (undefined names, Python 3.9 compatibility, all three catalog files current, manual and help-group completeness, website links and scripts, shell scripts, the Alpine package names of the ISO); and on Windows the installer is compiled and the PowerShell scripts parsed. (The first run found a real bug: the chess app used `os` without importing it.)
- The changelog is split into PythonOS, Exports, Website and Development parts for every version (this file's own header explains it); the release page shows the parts under their own headings, the core manifest carries the PythonOS part as its notes and the Exports part as `export_notes`, and `tools/test_changelog.py` checks the format.
- The macOS test run found the `lscpu` problem (fixed before release).

## 1.0.8

### PythonOS

- Marketplace API 2: per-export run files (`run_windows`, `run_linux`, `run_android`, `run_iso` in `scripts`), checked by the catalog builder. Apps that need libraries or `exec` may leave the ISO out of their exports (ytaudio and python now say Windows and Linux; wifimeter says Linux and ISO).
- YouTube Audio now plays the sound itself with pip libraries (`av`, `miniaudio`, installed by the marketplace): no mpv, VLC or ffplay, nothing outside PythonOS (issue 2).
- Commands and apps can limit themselves to some exports (`"exports"`): `installos`, `persist`, `hwsetup` and the new `display` exist only on the ISO/VM; apps must run on the ISO/VM and list the exports they work on, shown in the store and the App Library (issues 3 and 6).
- `updatecheck` on the live ISO / VM warns before downloading when there is no data disk to keep the update on (it would be gone after a restart); with the data disk (the VM images ship one) the update is kept (issue 4).
- New `display` command: change the console resolution on the ISO/VM; remembered at boot (issue 8).
- Long output of listing commands (`ls`, `cat`, `man`, `history`...) is shown a screen at a time (settings `auto_page`), since the Linux console cannot scroll back (issue 9).
- New setting `clear_style`: clear the screen before a command when the last output filled it (default) or before every command (issue 10).

### Exports

- `display 1280x720` now really changes the resolution on the ISO and VM images: the kernel restarts with that `video=` option (kexec, a few seconds, files kept) and the choice is applied again at every start. If the firmware refuses, nothing changes and it says so.
- Windows installer: the progress text under the bar is no longer cut off; updating keeps `config.json` (your settings) but now brings its version up to date, so the system reports the new version (issues 1 and 5).
- Terminal window on Windows: tables and wrapped text no longer break after the window is resized (issue 7).

### Website

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
