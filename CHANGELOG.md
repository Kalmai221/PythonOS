# Changelog

One section per release, newest first. The section for a version is shown to users when they update
(the "What's in it" box in updatecheck, and the "What's new" screen after the restart).

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
