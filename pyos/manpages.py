# pyos/manpages.py - the manual: one page per command, plus topics. Shown by the `man` command.
#
# Each page: summary (one line), synopsis (list of usage lines), description, options [(flag, text)],
# examples [(command, what it does)], see (related pages).

PAGES = {}


def page(name, summary, synopsis, description, options=(), examples=(), see=()):
    PAGES[name] = {"name": name, "summary": summary, "synopsis": list(synopsis), "description": description,
                   "options": list(options), "examples": list(examples), "see": list(see)}


def cmd_page(name, summary, synopsis, description, examples=(), see=()):
    """page() for commands that have no option list: (name, summary, synopsis, description, examples, see)."""
    page(name, summary, synopsis, description, [], examples, see)


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
page("cat", "show a file", ["cat [--plain] [--force] <file>...", "<command> | cat"],
     "Prints files exactly as they are. On a terminal, code, JSON, Markdown and other known file types are coloured; --plain turns that off, and piped output is never coloured. "
     "A file that is not text (a picture, a program) is not printed unless you add --force; file says what it is. With no file it prints what was piped into it.",
     examples=[("cat notes.txt", "read a file"), ("cat a.txt b.txt > both.txt", "join two files")], see=["head", "tail", "edit"])
page("head", "show the start of a file", ["head [-n N] [file]"], "Prints the first 10 lines (or N).",
     [("-n N", "how many lines")], [("head -n 3 log.txt", "first three lines"), ("ls | head -n 5", "first five names")], ["tail", "cat"])
page("tail", "show the end of a file", ["tail [-n N] [file]"], "Prints the last 10 lines (or N).",
     [("-n N", "how many lines")], [("tail -n 20 /var/log/system.log", "recent log entries")], ["head", "logs"])
page("wc", "count lines, words and characters", ["wc [file]"], "Prints three numbers: lines, words, characters.",
     examples=[("wc notes.txt", "size of a file"), ("ls | wc", "how many names ls printed")])
page("grep", "search for text", ["grep [-inrvwclF] [-A n] [-B n] [-C n] <pattern> [file or folder...]"],
     "Prints the lines that match a pattern (a regular expression). It succeeds only if something matched, so it works "
     "with && and ||. With a folder and -r it searches every text file inside (hidden files and huge or binary files are skipped).",
     [("-i", "ignore upper/lower case"), ("-n", "show line numbers"), ("-r", "search folders"), ("-v", "lines that do NOT match"),
      ("-w", "whole words only"), ("-c", "only count matches"), ("-l", "only list file names"), ("-F", "plain text, not a pattern"),
      ("-A/-B/-C n", "show n lines after / before / around each match")],
     [("grep todo notes.txt", "lines with todo"), ("grep -rn error /var/log", "search a whole folder"), ("cat log.txt | grep -i error", "search piped text"),
      ("grep -C 2 crash log.txt", "matches with context"), ("grep x file && echo found", "act on the result")],
     ["find", "diff", "shell"])
page("find", "find files", ["find [folder] [pattern] [-name p] [-iname p] [-type f|d] [-size +10k] [-mtime -7] [-maxdepth N] [-l]"],
     "Searches a folder and everything inside it. A plain word matches any name containing it; * and ? are wildcards. "
     "Tests can be combined: all of them must match. It only shows what you are allowed to see.",
     [("-type f|d", "files or folders only"), ("-size +10k", "bigger than 10 KB (use - for smaller; k, M, G)"),
      ("-mtime -7", "changed in the last 7 days (+30 = older than 30 days)"), ("-maxdepth N", "do not go deeper than N levels"),
      ("-l", "show size and date")],
     [("find *.txt", "every .txt file from here down"), ("find ~ -type f -size +1M", "big files in your home"),
      ("find /var/log -mtime -1", "logs changed today")], ["ls", "grep", "tree"])
page("touch", "create an empty file", ["touch <file>..."], "Creates the file if it does not exist, otherwise updates its time.",
     examples=[("touch todo.txt", "start a new file")], see=["edit", "mkdir"])
page("mkdir", "make a folder", ["mkdir [-p] <name>..."], "Creates folders.", [("-p", "no error if it already exists")],
     [("mkdir projects", "new folder")], ["rm", "cd"])
page("rm", "remove files and folders", ["rm [-f] [-P] <path>..."],
     "Moves files and folders to the trash, so a slip can be fixed: undo brings the last one back and trash lists everything. "
     "Folders (and everything inside) ask first, unless you use -f or turn off the confirm_delete setting. The trash empties itself "
     "after 30 days (settings trash_days); turn it off with settings set use_trash false.",
     [("-f", "do not ask, and ignore missing files"), ("-P", "delete for good, skipping the trash")],
     [("rm old.txt", "remove a file (it goes to the trash)"), ("rm -f temp", "remove a folder without asking"), ("undo", "bring the last one back")],
     ["trash", "undo", "backup", "settings"])
page("trash", "the trash", ["trash [list [--all]]", "trash restore <number|name> [path]", "trash delete <number|name>", "trash empty [--all]"],
     "Everything rm removed waits here. list shows it newest first; restore puts an item back where it was (or at a path you give) and "
     "never overwrites; delete and empty remove for good. You see your own items; admins can add --all.",
     examples=[("trash", "what is in the trash"), ("trash restore 2", "bring back item 2"), ("trash restore notes.txt ~/docs", "restore to another folder")],
     see=["rm", "undo"])
page("undo", "bring back the last removed thing", ["undo [N]"],
     "Restores what rm removed most recently (or the last N things) to where it was. If something is already there it stops instead "
     "of overwriting.", examples=[("rm notes.txt", "oops"), ("undo", "and it is back")], see=["rm", "trash"])
page("cp", "copy a file or folder", ["cp <source> <destination>"], "Copies a file, or a whole folder.",
     examples=[("cp a.txt b.txt", "copy to a new name"), ("cp -r not needed", "folders are copied automatically")], see=["mv"])
page("mv", "move or rename", ["mv <source> <destination>"], "Moves a file or folder, or renames it.",
     examples=[("mv draft.txt final.txt", "rename"), ("mv a.txt docs", "move into docs")], see=["cp"])
page("tree", "show folders as a tree", ["tree [-a] [-d] [-s] [-L depth] [path]"],
     "Draws the folder and everything inside it, folders first, with a count at the end.",
     [("-a", "include hidden files"), ("-d", "folders only"), ("-s", "show file sizes"), ("-L n", "only n levels deep")],
     [("tree -L 2 ~", "two levels of your home")], ["ls", "find"])
page("diff", "compare two files", ["diff [-u] [-q] <file1> <file2>"],
     "Shows what changed between two text files: < is a line only in the first, > only in the second. It succeeds only when the files "
     "are identical, so it works with && and ||.",
     [("-u", "unified format with context"), ("-q", "only say whether they differ")],
     [("diff old.txt new.txt", "what changed"), ("diff -q a b && echo same", "act on the result")], ["grep", "cat"])
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
page("tutorial", "learn PythonOS step by step", ["tutorial", "tutorial list", "tutorial <number>", "tutorial reset"],
     "A guided tour of about thirty short lessons in six groups (basics, files, finding things, pipes, safety nets, everyday tools): you try real "
     "commands and it checks them. It remembers where you stopped and offers to carry on; tutorial list shows every lesson, tutorial 12 jumps "
     "to one (and sets up what it needs). It uses a practice folder in your home that it offers to remove at the end.",
     examples=[("tutorial", "start or carry on"), ("tutorial list", "see every lesson"), ("tutorial 15", "jump to lesson 15")], see=["man", "help"])
page("run", "start a program", ["run <program> [args]"],
     "Programs are bigger applications (the marketplace, the calculator, installed games). Installed packages with a "
     "command name start with run too.", examples=[("run marketplace", "open the store"), ("run calc", "calculator")], see=["pkg", "help"])
page("reload", "re-read commands and programs", ["reload"], "Use after installing a package that added commands.")
page("exit", "leave the shell", ["exit"], "Logs you out.", see=["logout", "shutdown"])
page("clear", "clear the screen", ["clear [-x]"], "Wipes the terminal and its scrollback so old output stops piling up. Use -x to keep the scrollback. "
     "The screen is also cleared before a command when the last one filled it (settings clear_style: off, overflow or always), and tidies itself before a prompt once 300 lines have printed (settings auto_clear_lines, 0 = never), and a full-screen program or menu "
     "starts on a clean screen (settings clear_screens).",
     [("-x", "keep the scrollback")], [("clear", "wipe it all"), ("settings set auto_clear_lines 300", "tidy automatically")], ["settings"])
page("echo", "print text", ["echo <text>"], "Prints its words.", examples=[("echo hello > hi.txt", "write a file")])
page("date", "show the date and time", ["date"], "Prints the current day, date and time.", see=["uptime", "schedule"])
page("history", "show earlier commands", ["history", "history 20", "history <word>", "history -c"],
     "Lists what you typed before, searches it for a word, shows the last N, or clears it (-c). At the prompt, Ctrl+R searches as you type, the up arrow steps back, "
     "the right arrow accepts the grey suggestion, and !! repeats the last command, !n command number n, !-n the n-th from last, !word the last one starting with word.",
     examples=[("history git", "everything you typed that contains git"), ("!!", "run the last command again"), ("!ls", "run the last command that started with ls")], see=["settings", "alias"])
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
page("settings", "themes and options", ["settings", "settings list|get|set|reset|theme|themes", "settings apps", "settings app <app> [get|set|reset]"],
     "Run it alone for a menu. Themes: default, ocean, forest, sunset, mono, contrast. Other options: prompt_style (full/short/minimal), "
     "clock_24h, notifications, update_check, auto_lock_minutes, idle_logout_minutes (log out to the login screen after "
     "that many idle minutes), auto_clear_lines, confirm_delete. auto_lock_minutes and idle_logout_minutes can be set per person: "
     "settings set idle_logout_minutes 5 --user bob (you can set your own; administrators can set anyone's). Installed apps that have "
     "options of their own (a default difficulty, units...) show them here too: settings apps lists them and settings app <app> changes them. "
     "Other options: use_trash, trash_days (the trash), admin_reauth (password prompt before risky admin actions), language (auto, en, es, fr, de: the "
     "system's own messages - boot, shutdown, login, the blue screen - change language; commands and the manual stay in English).",
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
page("taskman", "task manager", ["taskman", "top"], "Shows the tasks running inside PythonOS: init and the kernel, your shell, services "
     "(scheduler, battery and memory watch...), background jobs and whatever is open (the marketplace, the editor, a game). Each has a "
     "PID, a parent, a state, CPU, memory and its command. Memory is shown against the memory PythonOS owns (see free). Stop a job with "
     "kill <pid>; administrators can also stop a service. The system tasks cannot be stopped.", see=["ps", "jobs", "kill", "free"])
page("fm", "the file manager", ["fm [folder]"],
     "A full-screen file manager: two panes, the folder on the left and a preview of what is under the cursor on the right. Enter opens a folder "
     "or edits a file, Space marks several, c / x / p copy, cut and paste (a name that is already there gets (2) added: nothing is overwritten), "
     "d moves to the trash (u brings it back, D deletes for good), r renames, n and N make a file or folder, / filters by name, s sorts, . shows "
     "hidden files, i shows details, ? lists every key. It follows the shell's rules: you cannot leave the filesystem, enter other homes, or "
     "change anything outside your home and /tmp unless you are an administrator. Without a full-screen terminal (the Android app) it lists the folder.",
     examples=[("fm", "open the file manager in the current folder"), ("fm ~/docs", "start in a folder")], see=["ls", "cp", "mv", "rm", "trash", "edit"])
page("limits", "how much an app may use", ["limits", "limits set <app> memory <MB|off>", "limits set <app> cpu <seconds|off>", "limits reset <app>",
                                              "limits default <percent|off>"],
     "Every app runs as a process of its own, so PythonOS can hold it to a limit. By default an app may use a quarter of the memory PythonOS owns "
     "(see free). An app can ask for its own limit, and administrators can set one per app or change the default. An app that goes over its "
     "limit is stopped with a message that says which limit it hit; its limits apply the next time it starts.",
     examples=[("limits set sysmon memory 128", "System Monitor may use 128 MB"), ("limits default 10", "apps may use 10% of PythonOS's memory by default")],
     see=["free", "taskman", "pkg", "settings"])
page("service", "the background services", ["service", "service status <name>", "service start|stop|restart <name>", "service enable|disable <name>"],
     "Lists what runs in the background while you are signed in (scheduler, idle watch, battery monitor, memory guard, update checks, startup "
     "programs) and whether each is running. Administrators can start, stop and restart a service, or disable it so it does not start at "
     "sign-in. The battery monitor, which shuts the system down cleanly when the battery is nearly empty, asks for your password first. "
     "Services also appear in taskman and ps.", examples=[("service stop scheduler", "scheduled tasks stop running until you start it again"),
                                                         ("service disable market-check", "no more daily app update checks")],
     see=["taskman", "ps", "schedule", "settings"])
page("ps", "list tasks", ["ps [-a] [-l]"], "Lists your tasks (a short list), or with -a every task and with -l the full columns.",
     see=["taskman", "jobs", "kill"])
page("logs", "system log", ["logs [N]", "logs --user U --level L --since T --until T --grep W", "logs --summary", "logs --crashes",
                            "logs --admin", "logs --export FILE [--csv]"],
     "Shows the last N lines (20 by default) of the system log: boots, logins, account changes, crashes. Filter by user, by "
     "level (info, warn or error: warn shows warnings and errors), by time (today, yesterday, 2h, 3d, 2026-10-05) or by a word; "
     "--summary counts lines per level and user and shows recent failed logins; --export saves the matching lines to a file "
     "(--csv for a spreadsheet); --admin shows only what administrators did (account, password, role, setting, update and app changes). Before the riskiest ones - deleting an account, changing a role or someone's password, switching user, wiping - an administrator is asked for their password again (turn off with settings set admin_reauth false). Administrators see everything, other users their own lines and system lines.",
     [("--user U", "only this user"), ("--level L", "info, warn or error (and worse)"), ("--since T / --until T", "a time range"),
      ("--grep W", "lines containing W"), ("--summary", "counts and failed logins"), ("--crashes", "saved crash reports (admin)"),
      ("--export FILE", "write the result to a file")],
     [("logs --level warn --since yesterday", "yesterday's problems"), ("logs --user bob --export ~/bob.csv --csv", "bob's activity as a CSV")],
     ["tail", "doctor", "bootlog"])
cmd_page("ping", "check that a host answers, and how fast", ["ping <host>", "ping -c 10 <host>", "ping -p 80 <host>", "ping host:8080"],
     "Times a TCP connection to the host (port 443, then 80) the given number of times and shows the answers and a summary. It needs no special "
     "rights and works on every export. Ctrl+C stops it.", [("ping example.com", "four tries"), ("ping -c 10 -p 22 myserver", "ten tries on port 22")], ["ipinfo", "hwsetup"])
cmd_page("sort", "sort lines", ["sort [-r] [-n] [-u] [-f] [file]"], "Sorts the lines of a file or of piped text. -r reverses, -n sorts by the number at the start of each line, -u drops repeats, -f ignores case.",
     [("cat names.txt | sort -u", "")], ["uniq", "cut"])
cmd_page("uniq", "collapse repeated lines", ["uniq [-c] [-d] [-u] [file]"], "Joins lines that repeat one after another (sort first to find every repeat). -c counts, -d shows only repeated lines, -u only single ones.",
     [("sort words.txt | uniq -c", "")], ["sort"])
cmd_page("cut", "keep parts of each line", ["cut -d, -f1,3 [file]", "cut -c1-5 [file]"], "Keeps chosen fields (split at the -d character) or character positions of every line. Ranges like 2-4 and 3- work.",
     [("cat data.csv | cut -d, -f2", "the second column")], ["sort", "tr"])
cmd_page("tr", "change or delete characters", ["tr set1 set2", "tr -d set"], "Replaces each character of set1 with the one at the same place in set2, or deletes them with -d. Ranges like a-z work. Text comes from a pipe.",
     [("cat a.txt | tr a-z A-Z", "")], ["cut", "rev"])
cmd_page("tee", "show text and save it too", ["tee [-a] <file>"], "Passes piped text on to the screen and writes it to a file as well (-a adds to the file).", [("ls | tee list.txt", "")], ["cat"])
cmd_page("rev", "reverse every line", ["rev [file]"], "Writes each line back to front.", [], ["tac"])
cmd_page("tac", "show the lines last to first", ["tac [file]"], "Writes the lines in reverse order.", [], ["rev", "sort"])
cmd_page("nl", "number the lines", ["nl [file]"], "Puts a line number in front of every line.", [], ["cat"])
cmd_page("seq", "print a run of numbers", ["seq <last>", "seq <first> <last>", "seq <first> <step> <last>"], "Prints whole numbers, one per line (at most 100000).", [("seq 2 2 10", "2 4 6 8 10")], ["xargs"])
cmd_page("basename", "the last part of a path", ["basename <path> [suffix]"], "Prints the file name of a path, optionally without a suffix.", [("basename ~/notes/a.txt .txt", "a")], ["dirname"])
cmd_page("dirname", "the folder part of a path", ["dirname <path>"], "Prints the folder a path is in.", [], ["basename"])
cmd_page("which", "what is this name?", ["which <name>..."], "Says whether a name is a built-in, a command or an app, and how to start it.", [("which ls", "")], ["help"])
cmd_page("du", "how much space folders use", ["du [-s] [-h] [path]"], "Shows the size of a folder and of every folder inside it. -s only the total, -h in K, M, G.", [("du -sh ~", "")], ["df", "stat"])
cmd_page("stat", "details of a file or folder", ["stat <path>..."], "Shows the type, size and dates of files and folders.", [], ["ls", "du"])
cmd_page("cal", "show a calendar", ["cal", "cal <month> <year>", "cal <year>"], "Shows this month, a chosen month, or a whole year.", [("cal 12 2026", "")], ["date"])
cmd_page("env", "who and where you are", ["env"], "Shows the user, role, home folder, host, current folder and the PythonOS settings of this session.", [], ["whoami", "pwd"])
cmd_page("xargs", "run a command with piped words", ["xargs [-n N] <command> [arguments]"], "Takes the words of the piped text and runs the command with them as arguments (N at a time with -n).",
     [("find .txt | xargs wc", "")], ["find", "seq"])
cmd_page("time", "how long did a command take", ["time <command> [arguments]"], "Runs the command and then says how long it took.", [("time find .txt", "")], ["watch"])
cmd_page("watch", "run a command again and again", ["watch [-n seconds] <command>"], "Clears the screen and runs the command every few seconds (2 by default) until Ctrl+C.", [("watch -n 5 free", "")], ["time"])
cmd_page("tracert", "show the route to a host", ["tracert <host>", "tracert -m 15 <host>"],
     "Shows every router between this computer and the host, with three timings each (traceroute is the same command). On Windows it uses the system's own "
     "ICMP service, on Linux and the ISO the kernel's error queue, so no special rights are needed; a * means that router did not answer.",
     [("tracert example.com", "")], ["ping", "nslookup"])
cmd_page("nslookup", "look up a name in the DNS", ["nslookup <name> [type] [server]", "nslookup <address>"],
     "Asks a name server (your system's, or the one you name) for A, AAAA, MX, NS, TXT, CNAME or SOA records, or for the name behind an address. dig and host are the same command.",
     [("nslookup example.com MX", "mail servers"), ("nslookup 1.1.1.1", "the name of an address"), ("nslookup example.com A 8.8.8.8", "ask Google's server")], ["ping", "whois"])
cmd_page("whois", "who registered a domain", ["whois <domain>"], "Shows the registration record of a domain from the registry's whois service.", [("whois example.com", "")], ["nslookup"])
cmd_page("curl", "fetch a web address", ["curl <url>", "curl -I <url>", "curl -o file <url>"],
     "Shows the page at an address, only its headers (-I), or saves it to a file (-o). Answers over 50 MB are refused.", [("curl -I example.com", "")], ["wget", "ping"])
cmd_page("wget", "download a file", ["wget <url> [file]"], "Saves the file at an address into the current folder (named after the address unless you give a name). Up to 500 MB.", [("wget https://example.com/a.zip", "")], ["curl"])
cmd_page("netstat", "list network connections", ["netstat [-l] [-a]"], "Shows the open connections and listening ports of this computer; -l only listening ones, -a also the closing ones. ss is the same command.", [], ["ifconfig", "ping"])
cmd_page("ifconfig", "show the network interfaces", ["ifconfig [name]"], "Lists each interface with its state, addresses, MAC address and speed. ipconfig is the same command.", [], ["netstat", "hwsetup"])
cmd_page("arch", "the processor family", ["arch"], "Prints x86_64, arm64 and so on for this computer.", [], ["lscpu", "uname"])
cmd_page("nproc", "number of cores", ["nproc"], "Prints how many processor cores there are.", [], ["lscpu"])
cmd_page("id", "who you are", ["id"], "Shows your user name and role (admin or user). groups is the same command.", [], ["whoami", "who"])
cmd_page("who", "who is logged in", ["who"], "Lists the people who are logged in. users is the same command.", [], ["id", "last"])
cmd_page("pgrep", "find tasks by name", ["pgrep <word>"], "Lists the PythonOS tasks whose command contains the word, with their ids for kill.", [("pgrep sleep", "")], ["ps", "kill", "taskman"])
cmd_page("lscpu", "show the processor", ["lscpu"], "Shows the processor family, cores, speed and current load.", [], ["arch", "nproc", "sysinfo"])
cmd_page("alias", "give a command a short name", ["alias", "alias name=\"command and arguments\""],
     "Makes a short name for a command with its arguments. The alias is kept for you (in ~/.pyos_aliases) and works at the start of a command. alias alone lists them.",
     [("alias ll=\"ls -l\"", "ll now means ls -l"), ("alias gs=\"updatecheck\"", "")], ["unalias", "export", "source"])
cmd_page("unalias", "remove an alias", ["unalias <name>...", "unalias -a"], "Removes one alias, or every alias with -a.", [], ["alias"])
cmd_page("export", "set a variable", ["export NAME=value", "export"],
     "Sets a variable you can use in later commands as $NAME or ${NAME}, and lists it in env. $USER, $HOME, $HOST, $PWD and $? always exist. NAME=value on its own does the same "
     "without listing it. Variables last for the session; put the lines in ~/.pyosrc to have them at every login.",
     [("export GREETING=hello", ""), ("echo $GREETING world", "hello world")], ["unset", "env", "source"])
cmd_page("unset", "forget a variable", ["unset NAME..."], "Removes variables made with export or NAME=value.", [], ["export"])
cmd_page("source", "run the commands of a file", ["source <file>", ". <file>"],
     "Runs a file one command per line (empty lines and lines starting with # are skipped). The file ~/.pyosrc is run like this at every login: put your aliases and variables in it.",
     [("source ~/setup.txt", "")], ["alias", "export"])
cmd_page("persist", "keep your accounts and files across restarts of the live system", ["persist [status|list|create|resize|migrate]"],
     "On the live ISO and VM images, sets up a data disk (labelled PYOS_DATA, optionally encrypted) so accounts, files and settings survive power-off, and shows its state. "
     "The VM images already come with one. persist create [disk] [--encrypt] makes one from a spare disk or partition.", [("persist status", "is a data disk in use?"), ("persist create --encrypt", "")], ["hwsetup", "backup"])
cmd_page("timesync", "check the clock against the internet", ["timesync"],
     "Asks a time server what time it is, shows the difference and sets the clock when the system allows it (the live ISO and VM images do). A wrong clock breaks secure "
     "connections and updates. The live images also do this by themselves a minute after start.", [], ["date", "ping"])
cmd_page("file", "say what a file is", ["file <path>..."], "Looks at the first bytes of a file and says what it is: an image, a program, an archive, a kind of text, or binary data. "
     "Uses the filetype library when it is installed.", [("file photo.jpg", "image/jpeg (jpg)")], ["cat", "stat", "ls"])
cmd_page("web", "read a web page as text", ["web <url>", "web -l <url>"], "Fetches a page and shows its title, its text and its links, numbered. -l shows only the links. "
     "Pages up to 4 MB; for a file, use wget. Uses beautifulsoup4 when it is installed. browse is the same command.", [("web example.com", ""), ("web -l https://news.ycombinator.com", "just the links")], ["curl", "wget"])
cmd_page("convert", "convert a data file between JSON and YAML", ["convert <file> [--to json|yaml] [-o output]"], "Reads a JSON or YAML file and writes it in the other format, to the screen or to a file. "
     "YAML needs the PyYAML library. yaml is the same command.", [("convert settings.json", "show it as YAML"), ("convert config.yml -o config.json", "")], ["cat", "edit"])
cmd_page("less", "read long text a screen at a time", ["less [file]", "... | less"], "Shows a file or piped text one screen at a time: Enter shows one more line, a space then Enter the next page, q stops. more is the same.",
     [("less readme.txt", ""), ("man pkg | less", "")], ["cat", "head"])
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
page("doctor", "check the installation", ["doctor", "doctor --fix", "doctor --online", "doctor --problems", "doctor --only <checks>", "doctor --json"],
     "Runs about twenty checks (Python and the clock, disk and memory, system files, commands, folders, accounts, permissions, packages, "
     "optional libraries, settings, aliases, the schedule, storage and crash reports) and reports OK, WARN or FAIL for each, with what to do "
     "when it cannot fix the problem itself. It gives a health score out of 100, tells you what is new or fixed since the last run, and where a "
     "fix is safe it offers to apply it, then checks again to show the result. --online also checks the internet and whether a newer PythonOS "
     "exists. Administrators only.",
     [("--fix", "offer every fix without the first question"), ("--yes", "apply every fix without asking"),
      ("--online", "also check the network and the latest release"), ("--problems", "show only what needs attention"),
      ("--only a,b", "run just those checks (doctor --list names them)"), ("--json", "machine-readable output, for scripts"),
      ("--timings", "show how long each check took")],
     [("doctor", "run the checks"), ("doctor --online --problems", "only what is wrong, including the network"), ("doctor --only commands,aliases", "two checks")],
     ["logs", "updatecheck", "bootlog"])
page("bootlog", "how the last boot went", ["bootlog", "bootlog list", "bootlog <number>"],
     "Every start-up runs a list of real steps (configuration, system files, services, dependencies, commands, programs, file "
     "system). Each one is timed and the last ten boots are kept, so you can see what was slow or what failed.",
     see=["settings", "logs"])
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
page("display", "change the screen resolution and text size (live ISO and VMs)",
     ["display", "display list", "display 1280x720", "display font"],
     "Shows the console resolution and the ones the screen offers, and sets one (display 1280x720): the kernel restarts with that video= option (a few seconds, files and accounts kept) and the choice is applied again at every start. "
     "If the firmware does not allow restarting the kernel, resize the VM window or its display setting instead. display font changes the text size.",
     [], ["hwsetup"]),
page("hwsetup", "hardware, audio, network, Bluetooth, display and printer setup",
     ["hwsetup", "hwsetup check|audio|network|keyboard|timezone|bluetooth|display|printer"],
     "On the live ISO (and any Linux system as root): check devices, drivers and firmware; choose and test the sound output "
     "(remembered per sound card, so a USB headset is found again even if the card order changes); connect to a wired or Wi-Fi "
     "network; pick the keyboard layout and time zone; pair Bluetooth devices (they reconnect by themselves); change the text size "
     "and, where the screen allows it, the resolution; add a network printer (driverless IPP printers). Your choices are applied at "
     "every boot and, with persistent storage, survive a power-off.", see=["ping", "persist", "print"])
page("print", "print a file", ["print <file>"],
     "Sends a text file or a PDF to the default printer (set one up with hwsetup printer). Plain text is turned into a PDF first, so "
     "it works with printers that only accept PDF. Files up to 5 MB.", examples=[("print ~/notes/todo.txt", "print a note")],
     see=["hwsetup"])
page("shutdown", "turn off", ["shutdown"],
     "Closes PythonOS the proper way: it stops background jobs (telling you about any that take a while), signs out, writes the log, "
     "flushes the files and marks the session as closed. On the ISO this powers the machine off; in the Android app it closes the app. "
     "If PythonOS is ever stopped any other way (power cut, window closed) the next boot says so - see whathappened.",
     see=["restart", "whathappened"])
page("restart", "restart", ["restart"],
     "Runs the same orderly shutdown, then starts PythonOS again as a fresh program, so updated files are really loaded.", see=["shutdown"])
page("installos", "install PythonOS on a disk", ["installos"],
     "From the live USB (full image): turns a disk of this computer into a PythonOS computer that boots by itself and keeps everything. "
     "You choose a whole disk, see exactly what will happen, and must type its name to confirm - the disk is erased. The installed system has "
     "the same lockdown as the live one (no login or shell on any console, root locked, locked boot menu) and is checked at the end. "
     "Experimental: it is built on Alpine's setup-disk and has been tried in virtual machines, not on every kind of computer. "
     "The minimal image has no installer.", see=["persist", "hwsetup", "diag"])
page("diag", "hardware and boot report", ["diag [--show]"],
     "Writes a report of this computer to a file in your home folder: machine, memory, devices and their drivers, disks, network, firmware "
     "the kernel could not load, recent kernel messages, the battery and how the last boot went. On the live USB you can also press D "
     "during the start for a verbose boot plus this report. Attach the file to a problem report (report) when asking for help.",
     examples=[("diag", "save the report"), ("diag --show", "save it and print it")], see=["hwsetup", "report", "bootlog"])
page("quickstart", "two-minute tour", ["quickstart"],
     "A short tour of what PythonOS offers: finding commands, apps, themes, keeping your data, undo and switching off. The live USB offers it "
     "on the first start. For hands-on lessons that check what you type, use tutorial.", see=["tutorial", "help"])
page("report", "send a problem report", ["report [what went wrong]", "report status [number]"],
     "Collects what a developer needs - versions, the newest crash report, the last log lines - and replaces names, home folders, email "
     "and IP addresses. You read the whole text first, then choose: (g) a GitHub issue under your own account (PythonOS shows a short code and "
     "an address, you approve it on another device such as your phone, and the issue is created; it uses the GitHub CLI, gh, when it is "
     "installed (the ISO has it), and the sign-in is deleted straight afterwards), (d) the "
     "developer's Discord channel, which needs no account, (f) a file, with the short address of the GitHub issue page, since PythonOS "
     "cannot open links, or (s) a relay, if settings report_relay is set. Only the ways that are set up in your copy are offered. Nothing "
     "is ever sent without your choice. report status shows the state and replies of a report you sent, with no sign-in.",
     examples=[("report", "answer a question, then see the report"), ("report the editor froze", "give the description up front")],
     see=["whathappened", "logs", "doctor"])
page("whathappened", "why the last session ended badly", ["whathappened"],
     "After a power cut, a closed window or a crash, the next boot says so and this command tells you more: when that session started, "
     "the crash report (if any) and the last things in the log before it stopped. Nothing is shown when the last shutdown was clean.",
     see=["logs", "doctor", "bootlog"])
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
page("sudo", "run one command as an administrator", ["sudo <command> [arguments]", "sudo -k"],
     "Runs a single command with administrator rights. An administrator confirms with their own password (it is remembered for a few "
     "minutes, and the admin_reauth setting can switch the question off). A standard user gives the name and password of an administrator, "
     "and is a standard user again as soon as the command ends. Every use is recorded in the log (logs --admin). Unlike su it does not "
     "start a shell, and the command still sees the administrator's home folder.",
     [("-k", "forget the remembered password, so the next sudo asks again")],
     [("sudo doctor --fix", "check the installation and repair it"), ("sudo hostname lab", "rename the computer")], ["su", "logs", "passwd"])
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
page("pkg", "package manager", ["pkg search <words>", "pkg install <name>", "pkg remove <name>", "pkg update [name]", "pkg list", "pkg info <name>",
                  "pkg why <name>", "pkg permissions [name]", "pkg notes <name>", "pkg rollback <name>"],
     "The marketplace from the command line (run marketplace opens the interactive store). Packages are checked against checksums "
     "before they are installed. why says which app needs a package, permissions shows what each app may do (network, files, notifications, "
     "schedule, system, exec), notes shows release notes and rollback goes back to the previous version of one app.", examples=[("pkg search game", "find games"), ("pkg install tictactoe", "install one"), ("pkg update", "update everything")],
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
