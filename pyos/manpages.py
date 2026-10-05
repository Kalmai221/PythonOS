# pyos/manpages.py - the manual: one page per command, plus topics. Shown by the `man` command.
#
# Each page: summary (one line), synopsis (list of usage lines), description, options [(flag, text)],
# examples [(command, what it does)], see (related pages).

PAGES = {}


def page(name, summary, synopsis, description, options=(), examples=(), see=()):
    PAGES[name] = {"name": name, "summary": summary, "synopsis": list(synopsis), "description": description,
                   "options": list(options), "examples": list(examples), "see": list(see)}


# ------------------------------------------------------------------ files
page("ls", "list files and folders", ["ls [-a] [-l] [path]"],
     "Shows what is in a folder (the current one by default). Folders are blue and end in /.",
     [("-a", "include hidden files (names starting with a dot)"), ("-l", "long format with size and modified time")],
     [("ls", "what is here"), ("ls -l ~/docs", "details for a folder"), ("ls | grep txt", "only names containing txt")],
     ["cd", "tree", "pwd"])
page("cd", "change folder", ["cd [path]"],
     "Moves to another folder. With no path it goes to your home folder (~). A path starting with / is from the top "
     "of the filesystem; ~ means your home; .. means the folder above.",
     examples=[("cd docs", "go into docs"), ("cd ..", "go up one"), ("cd /tmp", "go to the shared temporary folder"), ("cd", "go home")],
     see=["pwd", "ls", "files"])
page("pwd", "show the current folder", ["pwd"], "Prints where you are, for example /home/alex/docs.", see=["cd"])
page("cat", "show a file", ["cat <file>...", "<command> | cat"],
     "Prints files exactly as they are. With no file it prints what was piped into it.",
     examples=[("cat notes.txt", "read a file"), ("cat a.txt b.txt > both.txt", "join two files")], see=["head", "tail", "edit"])
page("head", "show the start of a file", ["head [-n N] [file]"], "Prints the first 10 lines (or N).",
     [("-n N", "how many lines")], [("head -n 3 log.txt", "first three lines"), ("ls | head -n 5", "first five names")], ["tail", "cat"])
page("tail", "show the end of a file", ["tail [-n N] [file]"], "Prints the last 10 lines (or N).",
     [("-n N", "how many lines")], [("tail -n 20 /var/log/system.log", "recent log entries")], ["head", "logs"])
page("wc", "count lines, words and characters", ["wc [file]"], "Prints three numbers: lines, words, characters.",
     examples=[("wc notes.txt", "size of a file"), ("ls | wc", "how many names ls printed")])
page("grep", "search for text", ["grep [-i] <pattern> [file...]"],
     "Prints the lines that match a pattern (a regular expression). It succeeds only if something matched, so it works "
     "with && and ||.",
     [("-i", "ignore upper/lower case")],
     [("grep todo notes.txt", "lines with todo"), ("cat log.txt | grep -i error", "search piped text"), ("grep x file && echo found", "act on the result")],
     ["find", "shell"])
page("find", "find files by name", ["find <pattern> [folder]"],
     "Searches a folder and everything inside it for names that match. A plain word matches any name containing it; * and ? "
     "are wildcards. Upper/lower case does not matter. It only shows what you are allowed to see.",
     examples=[("find *.txt", "every .txt file from here down"), ("find report ~/docs", "names containing report")], see=["ls", "grep", "tree"])
page("touch", "create an empty file", ["touch <file>..."], "Creates the file if it does not exist, otherwise updates its time.",
     examples=[("touch todo.txt", "start a new file")], see=["edit", "mkdir"])
page("mkdir", "make a folder", ["mkdir [-p] <name>..."], "Creates folders.", [("-p", "no error if it already exists")],
     [("mkdir projects", "new folder")], ["rm", "cd"])
page("rm", "remove files and folders", ["rm [-f] <path>..."],
     "Deletes files. Folders (and everything inside) ask first, unless you use -f or turn off the confirm_delete setting. "
     "There is no undo or recycle bin - make a backup first if unsure.",
     [("-f", "do not ask, and ignore missing files")], [("rm old.txt", "delete a file"), ("rm -f temp", "delete a folder without asking")],
     ["backup", "settings"])
page("cp", "copy a file or folder", ["cp <source> <destination>"], "Copies a file, or a whole folder.",
     examples=[("cp a.txt b.txt", "copy to a new name"), ("cp -r not needed", "folders are copied automatically")], see=["mv"])
page("mv", "move or rename", ["mv <source> <destination>"], "Moves a file or folder, or renames it.",
     examples=[("mv draft.txt final.txt", "rename"), ("mv a.txt docs", "move into docs")], see=["cp"])
page("tree", "show folders as a tree", ["tree [path]"], "Draws the folder and everything inside it (hidden files left out).", see=["ls"])
page("edit", "edit a text file", ["edit <file>"],
     "PythonOS's own editor. On a real terminal it opens full screen: type to edit, Ctrl+S saves, Ctrl+Q quits (twice if "
     "there are unsaved changes). On the Android app and in pipes it is a line editor: a adds lines (a single . finishes), "
     "p shows them, d deletes, r replaces, s changes text, f finds, u undoes, w saves, q quits, h shows help. A missing file is "
     "created when you save.",
     examples=[("edit notes.txt", "open or create a file")], see=["cat", "touch"])

# ------------------------------------------------------------------ the shell
page("shell", "how the command line works", ["<command> [args]", "a | b", "a > file", "a && b", "a || b", "a ; b", "a &"],
     "Quotes group words: echo \"hello world\". Several things can be combined on one line:\n"
     "  |    send the output of one command into the next\n"
     "  >    write the output to a file (>> adds to the end)\n"
     "  &&   run the next command only if the last one worked\n"
     "  ||   run the next command only if the last one failed\n"
     "  ;    run the next command no matter what\n"
     "  &    run it in the background (see jobs)\n"
     "$? holds how the last command ended (0 = worked). Tab completes commands and file names; the up arrow recalls earlier lines.",
     examples=[("ls | grep txt > found.txt", "save a filtered list"), ("mkdir d && cd d", "only enter if it was created"),
               ("cat missing || echo nope", "react to a failure"), ("sleep 5 && echo done &", "do it in the background")],
     see=["jobs", "help", "files"])
page("help", "list commands", ["help [name]"], "With no name, lists every command and program. With a name, describes it.", see=["man"])
page("man", "read the manual", ["man <name>", "man -k <word>", "man"],
     "Shows the manual page of a command or topic. man -k searches all pages for a word. Topics: shell, files, users, packages, "
     "updates, lockdown.", examples=[("man ls", "about ls"), ("man -k backup", "which pages mention backup")], see=["help", "tutorial"])
page("tutorial", "learn PythonOS step by step", ["tutorial"],
     "A short guided lesson series: you try real commands and it checks them. It uses a practice folder in your home that "
     "it offers to remove at the end.", see=["man", "help"])
page("run", "start a program", ["run <program> [args]"],
     "Programs are bigger applications (the marketplace, the calculator, installed games). Installed packages with a "
     "command name start with run too.", examples=[("run marketplace", "open the store"), ("run calc", "calculator")], see=["pkg", "help"])
page("reload", "re-read commands and programs", ["reload"], "Use after installing a package that added commands.")
page("exit", "leave the shell", ["exit"], "Logs you out.", see=["logout", "shutdown"])
page("clear", "clear the screen", ["clear [-x]"], "Wipes the terminal and its scrollback so old output stops piling up. Use -x to keep the scrollback. "
     "Set settings auto_clear_lines to a number (say 300) and the screen tidies itself before a prompt once that many lines have printed.",
     [("-x", "keep the scrollback")], [("clear", "wipe it all"), ("settings set auto_clear_lines 300", "tidy automatically")], ["settings"])
page("echo", "print text", ["echo <text>"], "Prints its words.", examples=[("echo hello > hi.txt", "write a file")])
page("date", "show the date and time", ["date"], "Prints the current day, date and time.", see=["uptime", "schedule"])
page("history", "show earlier commands", ["history"], "Lists what you typed before; the up arrow recalls them.")
page("whoami", "who am I", ["whoami"], "Shows your user name and whether you are an admin or a normal user.", see=["users"])

# ------------------------------------------------------------------ jobs, scheduling, notifications
page("jobs", "list background jobs", ["jobs [clear]"],
     "A command that ends with & runs in the background. This lists them with their state (running, done, failed, cancelled).",
     [("clear", "forget finished jobs")], [("sleep 30 &", "start one"), ("jobs", "see it")], ["fg", "kill", "sleep"])
page("fg", "show a background job's output", ["fg [job number]"], "Waits for the job to finish if needed, then prints what it printed.",
     see=["jobs"])
page("kill", "stop a background job", ["kill <job number>"],
     "Asks the job to stop. Jobs stop when they next check (for example while sleeping); a command that never checks finishes "
     "first. You can only stop your own jobs.", see=["jobs"])
page("sleep", "wait", ["sleep <seconds>"], "Pauses. Useful with && and & : sleep 5 && echo ready.", see=["jobs", "schedule"])
page("schedule", "run commands later", ["schedule add <in|at|every|daily> <when> <command>", "schedule list", "schedule remove <id>", "schedule run <id>"],
     "Tasks run while you are logged in and report back with a notification. Times: 90s, 5m, 2h, 1d; clock times as HH:MM.",
     examples=[("schedule add in 10m backup create", "once, in ten minutes"), ("schedule add daily 08:00 date", "every morning"),
               ("schedule add every 1h ls", "every hour")], see=["notifications", "jobs"])
page("notifications", "recent notifications", ["notifications [clear | test <message>]"],
     "Notices from background jobs, scheduled tasks and updates appear above your next prompt and are kept here. Turn them off with "
     "settings set notifications off.", see=["schedule", "settings"])

# ------------------------------------------------------------------ system
page("settings", "themes and options", ["settings", "settings list|get|set|reset|theme|themes"],
     "Run it alone for a menu. Themes: default, ocean, forest, sunset, mono, contrast. Other options: prompt_style (full/short/minimal), "
     "boot_speed, clock_24h, notifications, update_check, auto_lock_minutes, idle_logout_minutes (log out to the login screen after "
     "that many idle minutes), auto_clear_lines, confirm_delete. auto_lock_minutes and idle_logout_minutes can be set per person: "
     "settings set idle_logout_minutes 5 --user bob (you can set your own; administrators can set anyone's).",
     examples=[("settings set theme forest", "change colours"), ("settings set prompt_style short", "shorter prompt"),
               ("settings set auto_lock_minutes 10", "ask for the password after 10 idle minutes")], see=["lock"])
page("version", "version and package", ["version"],
     "Shows the PythonOS version, which package it runs in (Android app, Windows app, Linux package or ISO) and whether updates are waiting.",
     see=["updatecheck", "updates"])
page("uname", "system name", ["uname [-a]"], "Prints PyOS (and with -a the host name, kernel and Python).", see=["version", "sysinfo"])
page("hostname", "the computer's name", ["hostname [new name]"], "Shows the name shown in the prompt. Admins can change it.")
page("uptime", "how long it has been running", ["uptime"], "Time since PythonOS booted.", see=["date"])
page("free", "memory use", ["free"], "Total, used and free memory.", see=["df", "sysinfo"])
page("df", "disk space", ["df"], "How much the PythonOS filesystem uses and how much room the disk has.", see=["free"])
page("sysinfo", "information about this system", ["sysinfo"], "A table of the operating system, processor and memory.")
page("taskman", "task manager", ["taskman"], "Lists running processes and lets you sort them. Process killing and the machine's other "
     "processes are not available on a locked-down system.", see=["lockdown"])
page("logs", "system log", ["logs [N]", "logs --user U --level L --since T --until T --grep W", "logs --summary", "logs --crashes",
                            "logs --export FILE [--csv]"],
     "Shows the last N lines (20 by default) of the system log: boots, logins, account changes, crashes. Filter by user, by "
     "level (info, warn or error: warn shows warnings and errors), by time (today, yesterday, 2h, 3d, 2026-10-05) or by a word; "
     "--summary counts lines per level and user and shows recent failed logins; --export saves the matching lines to a file "
     "(--csv for a spreadsheet). Administrators see everything, other users their own lines and system lines.",
     [("--user U", "only this user"), ("--level L", "info, warn or error (and worse)"), ("--since T / --until T", "a time range"),
      ("--grep W", "lines containing W"), ("--summary", "counts and failed logins"), ("--crashes", "saved crash reports (admin)"),
      ("--export FILE", "write the result to a file")],
     [("logs --level warn --since yesterday", "yesterday's problems"), ("logs --user bob --export ~/bob.csv --csv", "bob's activity as a CSV")],
     ["tail", "doctor", "bootlog"])
page("ping", "test a network address", ["ping"], "Interactive: sets a target and sends test requests.", see=["ipinfo", "hwsetup"])
page("ipinfo", "public IP information", ["ipinfo"], "Shows your public IP address and where it appears to be.", see=["ping"])
page("zip", "make a zip archive", ["zip <archive.zip> <file or folder>..."],
     "Packs files and folders (and everything inside them) into one .zip file. Existing archives are replaced.",
     examples=[("zip ~/docs.zip ~/docs", "pack a folder"), ("zip all.zip a.txt b.txt", "pack two files")], see=["unzip", "tar", "backup"])
page("unzip", "unpack a zip archive", ["unzip [-l] [-o] <archive.zip> [-d folder]"],
     "Unpacks an archive into the current folder (or the folder after -d). It refuses names that would escape the destination, "
     "very large archives, and files that already exist unless you add -o.",
     [("-l", "list what is inside without unpacking"), ("-o", "overwrite files that already exist"), ("-d folder", "unpack somewhere else")],
     [("unzip -l ~/docs.zip", "see the contents"), ("unzip ~/docs.zip -d ~/out", "unpack into ~/out")], ["zip", "tar"])
page("tar", "make or unpack tar archives", ["tar -c[z]f <archive> <paths>...", "tar -x[z]f <archive> [-C folder] [-o]", "tar -t[z]f <archive>"],
     "Like the Unix tool: c creates, x extracts, t lists, z uses gzip compression (.tar.gz or .tgz) and f names the archive. "
     "Links and device files inside an archive are never created, and unsafe names are refused.",
     [("-C folder", "extract into this folder"), ("-o", "overwrite existing files")],
     [("tar -czf ~/p.tgz ~/p", "compress a folder"), ("tar -xzf ~/p.tgz -C ~/out", "unpack it"), ("tar -tf ~/p.tgz", "list it")], ["zip", "unzip"])
page("doctor", "check the installation", ["doctor", "doctor --fix", "doctor --yes"],
     "Looks at free disk space, system files, the account database, folder permissions, installed packages and stale data, and "
     "reports OK, WARN or FAIL for each. Where a fix is safe (missing folders, leftover temporary files, settings with bad values) it "
     "offers to apply it. Administrators only.",
     [("--fix", "offer every fix without the first question"), ("--yes", "apply every fix without asking")], [("doctor", "run the checks")],
     ["logs", "updatecheck", "bootlog"])
page("bootlog", "how the last boot went", ["bootlog", "bootlog list", "bootlog <number>"],
     "Every start-up runs a list of real steps (configuration, system files, services, dependencies, commands, programs, file "
     "system). Each one is timed and the last ten boots are kept, so you can see what was slow or what failed.",
     see=["bootspeed", "settings", "logs"])
page("bootspeed", "benchmark the start-up", ["bootspeed"],
     "Shows the average time per boot step from the saved boots, how much of it is the boot animation pause (the boot_speed "
     "setting) and runs a few quick tests of this machine.", see=["bootlog", "settings"])
page("cowsay", "a cow says it", ["cowsay <text>", "<command> | cowsay"],
     "Draws a speech bubble with a cow. It reads piped input when you give it no words, which makes it a nice way to learn pipes.",
     examples=[("fortune | cowsay", "the cow says a saying"), ("ls | cowsay", "the cow reads your files")], see=["fortune", "rainbow"])
page("fortune", "a random saying", ["fortune"],
     "Prints a saying, many of them tips about the shell. Use it to practise pipes and redirects.",
     examples=[("fortune | cowsay", "pipe it"), ("fortune > ~/today.txt", "save it in a file"), ("fortune >> ~/all.txt", "add to a file")],
     see=["cowsay", "rainbow", "echo"])
page("rainbow", "colour text like a rainbow", ["rainbow <text>", "<command> | rainbow"], "Colours every letter of piped text.",
     examples=[("fortune | rainbow", "a colourful saying")], see=["cowsay", "fortune"])
page("help", "see what you can do", ["help", "help <category>", "help <command>", "help search <word>", "help all"],
     "Without words it shows the groups of commands (Files, Jobs and scheduling, ...) with a few examples of each. help <group> lists "
     "one group, help <command> shows a single command, help search <word> looks through names, descriptions and the manual, and "
     "help all prints everything (in a pager on a real terminal). On a narrow screen it switches to a compact layout.",
     examples=[("help files", "the file commands"), ("help search backup", "find what mentions backup")], see=["man", "tutorial"])
page("rollback", "go back to the previous version", ["rollback"],
     "Goes back to the version that was installed before the last update. It works right after an update (one step back); the "
     "version you leave is not kept, so updating again downloads it. Your files and accounts are not touched. Administrators only.",
     see=["updatecheck", "whatsnew", "version"])
page("whatsnew", "what the last update changed", ["whatsnew"],
     "Shows the release notes and the files that changed in the last update. It also appears by itself the first time PythonOS "
     "starts after an update. Updates download only the files that changed and carry on where they stopped if the connection drops.",
     see=["updatecheck", "rollback", "version"])
page("hwsetup", "hardware, audio, network, keyboard and time zone setup", ["hwsetup", "hwsetup check|audio|network|keyboard|timezone"],
     "On the live ISO (and any Linux system as root): check devices, drivers and firmware; choose and test the sound output; "
     "connect to a wired or Wi-Fi network and test the internet; pick the keyboard layout and time zone. Your choices (and Wi-Fi "
     "networks, as a derived key rather than the password) are remembered and applied at every boot; with persistent storage they "
     "survive a power-off.", see=["ping", "persist"])
page("persist", "keep your data on the live system", ["persist", "persist list", "persist create [--encrypt] [device]", "persist resize",
                                                        "persist migrate [device]"],
     "The live ISO forgets everything when it shuts down, unless it has a data disk. 'persist create' turns a USB stick or "
     "spare disk into that data disk (it is erased first, and you must type its name to confirm) and copies your accounts, files "
     "and settings onto it. With --encrypt the disk is encrypted (LUKS) and the passphrase is asked for at every start. "
     "'persist' alone shows the disk's health: free space, whether the filesystem is clean, how many times it was used and when. "
     "'resize' grows the filesystem after you made the disk or partition bigger; 'migrate' moves everything to another disk "
     "(the old one is kept, relabelled PYOS_OLD). Administrators only; the disk PythonOS started from can never be chosen.",
     [("status", "is persistent storage active, and is it healthy?"), ("list", "disks that could be used"),
      ("create [--encrypt] [device]", "set one up"), ("resize", "grow to fill the disk"), ("migrate [device]", "move to another disk")],
     [("persist", "check"), ("persist create /dev/sdb", "use that USB stick"), ("persist create --encrypt /dev/sdb", "encrypted")],
     ["hwsetup", "backup"])
page("shutdown", "turn off", ["shutdown"], "Closes PythonOS. On the ISO this powers the machine off; in the Android app it closes the app.",
     see=["restart"])
page("restart", "restart", ["restart"], "Restarts PythonOS.", see=["shutdown"])
page("logout", "log out", ["logout"], "Ends your session and returns to the login screen.")
page("wipe", "reset to factory settings", ["wipe"], "Admins only. Erases all data and accounts. There is no undo.", see=["backup"])
page("manageusers", "manage accounts", ["manageusers"], "Admins only. Create and delete users, change roles and passwords.", see=["users", "passwd"])

page("passwd", "change a password", ["passwd", "passwd <user>"],
     "Changes your password (you must type the current one first). Passwords need at least 6 characters, must differ from the user name "
     "and cannot be one repeated character. Admins can change anyone's password with passwd <user>.",
     examples=[("passwd", "change mine"), ("passwd sam", "admins: reset sam's password")], see=["users", "lock"])
page("su", "work as another user", ["su <user>"],
     "Starts a shell as another user. Admins do not need a password; everyone else must enter the other user's. Type exit to come back.",
     examples=[("su sam", "become sam for a while")], see=["users", "whoami"])
page("lock", "lock the session", ["lock"],
     "Hides everything until your password is entered again (three tries, then you are logged out). PythonOS can also lock itself after you "
     "have been idle for a while: settings set auto_lock_minutes 10.", see=["settings", "passwd"])
page("last", "recent logins", ["last [N] [-f]"],
     "Shows logins, failed attempts, locks and password changes from the system log. Admins see everyone; others only their own.",
     [("-f", "only failed login attempts")], [("last 5", "the five most recent events"), ("last -f", "who got the password wrong")], ["logs", "users"])

# ------------------------------------------------------------------ files in motion
page("backup", "back up and restore", ["backup create [file]", "backup create --system [file]", "backup list", "backup restore <file> [-y] [--system]"],
     "Backups are .zip files. A normal backup holds your home folder; an admin's --system backup holds every user, the accounts, settings and "
     "schedule (and contains password hashes, so keep it private). Restoring asks before replacing files and refuses damaged or unsafe archives.",
     examples=[("backup create", "save to ~/backups"), ("backup restore backups/pythonos-me-2026.zip", "put it back")], see=["share", "files"])
page("share", "send files between devices", ["share send <file>", "share receive [folder]", "share get <link> [folder]"],
     "send makes a one-time link; open it on any device on your network. receive makes an upload page for a phone or PC. get downloads "
     "from a link. Links contain a random code and stop after one use or 10 minutes.",
     examples=[("share send photo.jpg", "give a link"), ("share receive inbox", "accept uploads into inbox"), ("share get http://192.168.1.5:8000/t/abc/photo.jpg", "download")],
     see=["backup"])

# ------------------------------------------------------------------ packages & updates
page("pkg", "package manager", ["pkg search <words>", "pkg install <name>", "pkg remove <name>", "pkg update [name]", "pkg list", "pkg info <name>"],
     "The marketplace from the command line (run marketplace opens the interactive store). Packages are checked against checksums "
     "before they are installed.", examples=[("pkg search game", "find games"), ("pkg install tictactoe", "install one"), ("pkg update", "update everything")],
     see=["packages", "run"])
page("updatecheck", "update PythonOS", ["updatecheck"],
     "Looks for a newer release and installs it. PythonOS's own files update themselves. If the package around PythonOS (the APK, "
     "Windows app, Linux package or ISO) has a newer version, it cannot update itself and you are told where to download it.", see=["updates", "version"])

# ------------------------------------------------------------------ topics
page("files", "the filesystem", ["/", "~", ".."],
     "PythonOS has its own filesystem, separate from the device it runs on:\n"
     "  /home/<you>   your home folder (~)           /tmp   shared temporary space\n"
     "  /etc          system settings (admins)        /var/log   the system log\n"
     "Normal users can write only in their own home and /tmp, and cannot enter other people's homes. Admins can change anything. "
     "Paths starting with / are from the top; others are from where you are.",
     see=["cd", "ls", "users"])
page("users", "accounts and permissions", ["whoami", "passwd", "su", "lock"],
     "The first account is an admin (the prompt ends in #); others are normal users ($). Admins manage accounts with manageusers. "
     "Passwords are stored as salted hashes, and logins are slowed after repeated mistakes.", see=["passwd", "lock", "settings"])
page("packages", "marketplace packages", ["pkg", "run marketplace"],
     "Packages add apps and commands. They live in /installed_<category> and start with run <name>. A package can depend on others "
     "(they are installed together) and the store lists them by category.", see=["pkg", "run"])
page("updates", "how updating works", ["updatecheck", "version"],
     "There are two kinds of update. The core (everything inside PythonOS) updates itself from the latest release - your files and "
     "accounts are never touched. The package around it (APK, Windows app, Linux package, ISO) cannot be replaced from inside, so PythonOS "
     "tells you when a newer one exists and where to get it.", see=["updatecheck", "version"])
page("lockdown", "locked-down mode", ["PYOS_LOCKDOWN=1 or \"lockdown\": true in config.json"],
     "Used by the bootable ISO (and optionally kiosks): nothing can reach the system underneath PythonOS. No external editor, no process "
     "killing, no installer scripts, and only catalog-approved packages that are unchanged since installation will run.", see=["pkg", "taskman"])
