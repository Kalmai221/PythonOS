// What the installer does, without any window: find the release, download it, check it, put it in place, make shortcuts, register
// the uninstaller, remove it again. The window (Ui.cs) and the silent mode (Program.cs) both call this.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using Microsoft.Win32;

namespace PythonOS.Setup
{
    internal sealed class SetupException : Exception
    {
        public SetupException(string message) : base(message) { }
    }

    /// <summary>The log: %LOCALAPPDATA%\PythonOS\Setup\install-log.txt. Every step and every error is written here.</summary>
    internal static class Log
    {
        public static readonly string Folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PythonOS", "Setup");
        public static readonly string Path_ = Path.Combine(Folder, "install-log.txt");
        private static readonly object gate = new object();

        public static void Write(string text)
        {
            try
            {
                lock (gate)
                {
                    Directory.CreateDirectory(Folder);
                    FileInfo info = new FileInfo(Path_);
                    if (info.Exists && info.Length > 512 * 1024) File.Move(Path_, Path_ + ".old");
                    File.AppendAllText(Path_, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + text + Environment.NewLine, Encoding.UTF8);
                }
            }
            catch (Exception) { /* a log that cannot be written must never stop the install */ }
        }
    }

    internal sealed class Options
    {
        public string Directory = DefaultDirectory();
        public bool DesktopShortcut;
        public bool StartMenuShortcut = true;
        public bool Silent;
        public bool Launch = true;
        public string Mode = "install";           // install | update | repair | uninstall
        public bool DeleteData;
        public bool FixWebView2 = true;           // install Microsoft's WebView2 runtime when it is missing
        public int MemoryMb = 1024;                // the memory PythonOS owns (setting memory_limit_mb); 0 = all of it; written only on a fresh install
        public string ManifestUrl = "";            // developer override: a JSON file shaped like GitHub's "latest release" answer

        public static string DefaultDirectory()
        {
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "PythonOS");
        }
    }

    internal sealed class Existing
    {
        public string Version;
        public string Directory;
        public string Source;          // web | inno | folder
    }

    internal sealed class Release
    {
        public string Tag;
        public string Version;
        public string PackageName;
        public string PackageUrl;
        public long PackageSize;
        public string SumsUrl;
    }

    internal static class Core
    {
        public const string Repo = "Kalmai221/PythonOS";
        public const string UninstallKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\PythonOS";
        public const string AppName = "PythonOS";
        public const long NeedBytes = 450L * 1024 * 1024;
        // user data that a repair or an update never touches
        private static readonly string[] KeepNames = new string[] { "files", ".OSData", "users.json", "current_user.json", "current_directory.txt", "config.json" };
        // the OS itself (downloaded by the app, not part of this package); a repair removes it so the app fetches a fresh copy.
        // Anything NOT named here or in the package is left alone: an update must never delete files the installer does not own.
        private static readonly string[] CoreNames = new string[] { "commands", "core", "programs", "pyos", "main.py", "shell.py", "users.py", "VERSION",
                                                                    "boot-requirements.txt", "requirements.txt", "readme.md", "__pycache__" };

        public delegate void Progress(string step, double fraction, string detail);

        public static void PrepareNetwork()
        {
            ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072 | (SecurityProtocolType)768;     // TLS 1.2 and 1.1
            ServicePointManager.DefaultConnectionLimit = 8;
        }

        // ----------------------------------------------------------------- what is already here
        // The Inno Setup installer (the offline PythonOS-<version>-setup.exe, and every version before the web installer) registers
        // itself under this key, per user or for the machine. The web installer must recognise those installs and update them in place.
        public const string InnoKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\{6B0B3A63-5B6E-4C3E-9C47-7C1D2F6A9E11}_is1";

        private static string FolderVersion(string dir)
        {
            foreach (string name in new string[] { "VERSION", "export.json" })
            {
                try
                {
                    string path = Path.Combine(dir, name);
                    if (!File.Exists(path)) continue;
                    string text = File.ReadAllText(path).Trim();
                    if (name == "VERSION") return text.Length > 0 ? text : "?";
                    System.Text.RegularExpressions.Match m = System.Text.RegularExpressions.Regex.Match(text, "\"version\"\\s*:\\s*\"([^\"]+)\"");
                    if (m.Success) return m.Groups[1].Value;
                }
                catch (Exception) { }
            }
            return "?";
        }

        private static bool LooksLikePythonOS(string dir)
        {
            return Directory.Exists(dir) && (File.Exists(Path.Combine(dir, "PythonOS.exe")) || File.Exists(Path.Combine(dir, "main.py")) ||
                                             Directory.Exists(Path.Combine(dir, "python")));
        }

        private static Existing FromKey(RegistryKey root, string subKey, string source)
        {
            try
            {
                using (RegistryKey key = root.OpenSubKey(subKey))
                {
                    if (key == null) return null;
                    string dir = key.GetValue("InstallLocation") as string;
                    if (string.IsNullOrEmpty(dir)) dir = key.GetValue("Inno Setup: App Path") as string;
                    if (string.IsNullOrEmpty(dir) || !LooksLikePythonOS(dir)) return null;
                    Existing e = new Existing();
                    e.Directory = dir.TrimEnd('\\');
                    e.Version = key.GetValue("DisplayVersion") as string ?? FolderVersion(e.Directory);
                    e.Source = source;
                    return e;
                }
            }
            catch (Exception) { return null; }
        }

        public static Existing FindExisting()
        {
            Existing e = FromKey(Registry.CurrentUser, UninstallKey, "web");
            if (e != null) return e;
            e = FromKey(Registry.CurrentUser, InnoKey, "inno");
            if (e != null) return e;
            e = FromKey(Registry.LocalMachine, InnoKey, "inno");
            if (e != null) return e;
            // No uninstall entry (a portable copy, or an install whose entry was removed): look where PythonOS usually lives
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            foreach (string dir in new string[] { Path.Combine(local, "PythonOS"), Path.Combine(local, "Programs", "PythonOS") })
            {
                if (!LooksLikePythonOS(dir)) continue;
                Existing f = new Existing();
                f.Directory = dir;
                f.Version = FolderVersion(dir);
                f.Source = "folder";
                return f;
            }
            return null;
        }

        // ----------------------------------------------------------------- requirements
        public static void CheckRequirements(Options o)
        {
            Version v = RealWindowsVersion();
            if (v.Major < 10 || (v.Major == 10 && v.Build < 17763)) throw new SetupException(Strings.T("err.windows"));
            string root = Path.GetPathRoot(Path.GetFullPath(o.Directory));
            try
            {
                DriveInfo drive = new DriveInfo(root);
                if (drive.AvailableFreeSpace < NeedBytes) throw new SetupException(Strings.T("err.space", NeedBytes / (1024 * 1024)));
            }
            catch (SetupException) { throw; }
            catch (Exception ex) { Log.Write("free space check skipped: " + ex.Message); }
        }

        [System.Runtime.InteropServices.DllImport("ntdll.dll")]
        private static extern int RtlGetVersion(ref OsVersion info);

        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        private struct OsVersion
        {
            public int Size, Major, Minor, Build, Platform;
            [System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.ByValTStr, SizeConst = 128)]
            public string Csd;
        }

        public static Version RealWindowsVersion()
        {
            try
            {
                OsVersion info = new OsVersion();
                info.Size = System.Runtime.InteropServices.Marshal.SizeOf(typeof(OsVersion));
                if (RtlGetVersion(ref info) == 0) return new Version(info.Major, info.Minor, info.Build);
            }
            catch (Exception) { }
            return new Version(10, 0, 19041);
        }

        public static bool HasWebView2()
        {
            string guid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}";
            string[] keys = new string[] {
                @"HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\" + guid,
                @"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\EdgeUpdate\Clients\" + guid,
                @"HKEY_CURRENT_USER\Software\Microsoft\EdgeUpdate\Clients\" + guid };
            foreach (string k in keys)
            {
                try
                {
                    string pv = Registry.GetValue(k, "pv", null) as string;
                    if (!string.IsNullOrEmpty(pv) && pv != "0.0.0.0") return true;
                }
                catch (Exception) { }
            }
            return false;
        }

        /// <summary>Download Microsoft's WebView2 bootstrapper, check that Microsoft signed it, and run it quietly.</summary>
        public static void InstallWebView2(Progress progress)
        {
            string file = Path.Combine(Path.GetTempPath(), "MicrosoftEdgeWebview2Setup.exe");
            using (WebClient web = new WebClient())
            {
                web.Headers["User-Agent"] = "PythonOS-Setup";
                progress("webview", 0.2, "");
                web.DownloadFile("https://go.microsoft.com/fwlink/p/?LinkId=2124703", file);
            }
            if (!SignedByMicrosoft(file)) throw new SetupException("The WebView2 installer is not signed by Microsoft; it was not run.");
            Log.Write("running the WebView2 bootstrapper");
            ProcessStartInfo psi = new ProcessStartInfo(file, "/silent /install");
            psi.UseShellExecute = false;
            Process p = Process.Start(psi);
            p.WaitForExit(5 * 60 * 1000);
            Log.Write("WebView2 installer exit code " + (p.HasExited ? p.ExitCode.ToString() : "(still running)"));
        }

        private static bool SignedByMicrosoft(string file)
        {
            try
            {
                X509Certificate cert = X509Certificate.CreateFromSignedFile(file);
                return cert.Subject.IndexOf("Microsoft Corporation", StringComparison.OrdinalIgnoreCase) >= 0;
            }
            catch (Exception) { return false; }
        }

        // ----------------------------------------------------------------- the release
        private static string Get(string url, string accept)
        {
            HttpWebRequest r = (HttpWebRequest)WebRequest.Create(url);
            r.UserAgent = "PythonOS-Setup";
            r.Accept = accept;
            r.Timeout = 30000;
            using (WebResponse resp = r.GetResponse())
            using (StreamReader reader = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                return reader.ReadToEnd();
        }

        public static Release FindRelease(Options o)
        {
            string url = string.IsNullOrEmpty(o.ManifestUrl) ? "https://api.github.com/repos/" + Repo + "/releases/latest" : o.ManifestUrl;
            string json;
            try { json = Get(url, "application/vnd.github+json"); }
            catch (Exception ex) { Log.Write("release lookup failed: " + ex.Message); throw new SetupException(Strings.T("err.release")); }
            JavaScriptSerializer js = new JavaScriptSerializer();
            Dictionary<string, object> root = js.Deserialize<Dictionary<string, object>>(json);
            Release rel = new Release();
            rel.Tag = Convert.ToString(root["tag_name"]);
            rel.Version = rel.Tag.TrimStart('v');
            foreach (object item in (System.Collections.ArrayList)root["assets"])
            {
                Dictionary<string, object> a = (Dictionary<string, object>)item;
                string name = Convert.ToString(a["name"]);
                string link = Convert.ToString(a["browser_download_url"]);
                bool arm = IsArm64();
                bool exact = name.EndsWith(arm ? "-windows-arm64-portable.zip" : "-windows-portable.zip", StringComparison.OrdinalIgnoreCase);
                // a Windows-on-ARM PC with a release that has no ARM64 package falls back to the x64 one (Windows runs it emulated)
                bool fallback = arm && rel.PackageName == null && name.EndsWith("-windows-portable.zip", StringComparison.OrdinalIgnoreCase);
                if (exact || fallback)
                {
                    rel.PackageName = name;
                    rel.PackageUrl = link;
                    rel.PackageSize = a.ContainsKey("size") ? Convert.ToInt64(a["size"]) : 0;
                }
                else if (name == "SHA256SUMS") rel.SumsUrl = link;
            }
            Log.Write("latest release " + rel.Tag + ", package " + rel.PackageName);
            if (rel.PackageUrl == null) throw new SetupException(Strings.T("err.file"));
            if (rel.SumsUrl == null) throw new SetupException(Strings.T("err.nosums"));
            return rel;
        }

        [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool IsWow64Process2(IntPtr process, out ushort processMachine, out ushort nativeMachine);

        [System.Runtime.InteropServices.DllImport("kernel32.dll")]
        private static extern IntPtr GetCurrentProcess();

        /// <summary>True on a Windows-on-ARM PC, also when this installer itself runs emulated (an x64 program asks Windows, not itself).</summary>
        public static bool IsArm64()
        {
            try
            {
                ushort process, native;
                if (IsWow64Process2(GetCurrentProcess(), out process, out native) && native != 0) return native == 0xAA64;   // IMAGE_FILE_MACHINE_ARM64
            }
            catch (Exception) { }                                          // an older Windows without IsWow64Process2: use the environment
            string a = Environment.GetEnvironmentVariable("PROCESSOR_ARCHITEW6432") ?? Environment.GetEnvironmentVariable("PROCESSOR_ARCHITECTURE") ?? "";
            return a.Equals("ARM64", StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>The expected SHA-256 of `fileName` from the release's SHA256SUMS text, or null.</summary>
        public static string ExpectedHash(string sums, string fileName)
        {
            foreach (string raw in sums.Split('\n'))
            {
                string line = raw.Trim();
                if (line.Length < 66) continue;
                string hash = line.Substring(0, 64);
                string name = line.Substring(64).Trim().TrimStart('*');
                if (string.Equals(name, fileName, StringComparison.OrdinalIgnoreCase)) return hash.ToLowerInvariant();
            }
            return null;
        }

        // ----------------------------------------------------------------- downloading (resumable)
        public static string Download(Release rel, Progress progress, CancelToken cancel)
        {
            string folder = Path.Combine(Path.GetTempPath(), "PythonOS-Setup");
            Directory.CreateDirectory(folder);
            string file = Path.Combine(folder, rel.PackageName);
            string part = file + ".part";
            long have = File.Exists(part) ? new FileInfo(part).Length : 0;
            if (rel.PackageSize > 0 && have > rel.PackageSize) { File.Delete(part); have = 0; }
            if (rel.PackageSize > 0 && have == rel.PackageSize) { if (File.Exists(file)) File.Delete(file); File.Move(part, file); return file; }

            HttpWebRequest r = (HttpWebRequest)WebRequest.Create(rel.PackageUrl);
            r.UserAgent = "PythonOS-Setup";
            r.AllowAutoRedirect = true;
            r.Timeout = 30000;
            r.ReadWriteTimeout = 30000;
            if (have > 0) r.AddRange(have);
            Log.Write("downloading " + rel.PackageUrl + (have > 0 ? " (resuming at " + have + ")" : ""));
            using (HttpWebResponse resp = (HttpWebResponse)r.GetResponse())
            {
                bool resumed = resp.StatusCode == HttpStatusCode.PartialContent;
                if (!resumed) have = 0;
                long total = (resumed ? have : 0) + resp.ContentLength;
                if (total <= 0) total = rel.PackageSize;
                using (Stream src = resp.GetResponseStream())
                using (FileStream dst = new FileStream(part, resumed ? FileMode.Append : FileMode.Create, FileAccess.Write))
                {
                    byte[] buffer = new byte[64 * 1024];
                    long done = have;
                    Stopwatch clock = Stopwatch.StartNew();
                    long startBytes = done;
                    int n;
                    while ((n = src.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        if (cancel.Cancelled) throw new OperationCanceledException();
                        dst.Write(buffer, 0, n);
                        done += n;
                        double seconds = Math.Max(0.2, clock.Elapsed.TotalSeconds);
                        double speed = (done - startBytes) / seconds;
                        string left = total > done && speed > 1 ? Strings.T("eta", Duration((total - done) / speed)) : "";
                        progress("download", total > 0 ? (double)done / total : 0, Strings.T("speed", Size(done), Size(total), Size((long)speed)) + left);
                    }
                }
            }
            if (File.Exists(file)) File.Delete(file);
            File.Move(part, file);
            return file;
        }

        /// <summary>A time in words for the "about ... left" text: 45 s, 3 min 20 s, 1 h 5 min.</summary>
        public static string Duration(double seconds)
        {
            int s = (int)Math.Max(1, Math.Round(seconds));
            if (s < 60) return s + " s";
            if (s < 3600) return (s / 60) + " min " + (s % 60) + " s";
            return (s / 3600) + " h " + ((s % 3600) / 60) + " min";
        }

        public static string Size(long bytes)
        {
            if (bytes >= 1024L * 1024 * 1024) return (bytes / 1073741824.0).ToString("0.0") + " GB";
            if (bytes >= 1024L * 1024) return (bytes / 1048576.0).ToString("0.0") + " MB";
            return (bytes / 1024.0).ToString("0") + " KB";
        }

        public static string Sha256(string file)
        {
            using (SHA256 sha = SHA256.Create())
            using (FileStream f = File.OpenRead(file))
            {
                byte[] hash = sha.ComputeHash(f);
                StringBuilder sb = new StringBuilder();
                foreach (byte b in hash) sb.Append(b.ToString("x2"));
                return sb.ToString();
            }
        }

        public static void Verify(string file, Release rel)
        {
            string sums = Get(rel.SumsUrl, "text/plain");
            string want = ExpectedHash(sums, rel.PackageName);
            if (want == null) throw new SetupException(Strings.T("err.nosums"));
            string got = Sha256(file);
            Log.Write("sha256 expected " + want + " got " + got);
            if (got != want)
            {
                try { File.Delete(file); } catch (Exception) { }
                throw new SetupException(Strings.T("err.sum"));
            }
        }

        // ----------------------------------------------------------------- putting it in place
        public static void StopRunning(string dir, bool askOrForce)
        {
            string exe = Path.Combine(dir, "PythonOS.exe").ToLowerInvariant();
            foreach (Process p in Process.GetProcessesByName("PythonOS"))
            {
                try
                {
                    string path = p.MainModule.FileName.ToLowerInvariant();
                    if (path != exe) continue;
                    Log.Write("closing the running PythonOS (" + p.Id + ")");
                    p.CloseMainWindow();
                    if (!p.WaitForExit(6000))
                    {
                        if (!askOrForce) throw new SetupException(Strings.T("err.running"));
                        p.Kill();
                        p.WaitForExit(4000);
                    }
                }
                catch (SetupException) { throw; }
                catch (Exception ex) { Log.Write("could not inspect process: " + ex.Message); }
            }
        }

        public static bool IsRunning(string dir)
        {
            string exe = Path.Combine(dir, "PythonOS.exe").ToLowerInvariant();
            foreach (Process p in Process.GetProcessesByName("PythonOS"))
            {
                try { if (p.MainModule.FileName.ToLowerInvariant() == exe) return true; } catch (Exception) { }
            }
            return false;
        }

        public static void InstallPackage(string zip, Options o, Release rel, Progress progress)
        {
            string target = Path.GetFullPath(o.Directory);
            string stage = target + ".new";
            if (Directory.Exists(stage)) Directory.Delete(stage, true);
            Directory.CreateDirectory(stage);
            Log.Write("extracting to " + stage);
            progress("install", 0.1, "");
            ExtractZip(zip, stage);
            // the package holds one folder, PythonOS, with everything inside
            string inner = Path.Combine(stage, "PythonOS");
            string source = Directory.Exists(inner) ? inner : stage;
            progress("install", 0.6, "");

            Directory.CreateDirectory(target);
            bool repair = o.Mode == "repair";
            // Remove only what this package brings (it is about to be replaced) and, for a repair, the OS files (the app fetches them again).
            List<string> owned = new List<string>();
            foreach (string entry in Directory.GetFileSystemEntries(source)) owned.Add(Path.GetFileName(entry).ToLowerInvariant());
            foreach (string entry in Directory.GetFileSystemEntries(target))
            {
                string name = Path.GetFileName(entry);
                if (Array.IndexOf(KeepNames, name) >= 0) continue;                       // your data stays
                if (string.Equals(name, "Uninstall.exe", StringComparison.OrdinalIgnoreCase)) continue;
                bool replaced = owned.Contains(name.ToLowerInvariant());
                bool core = repair && Array.IndexOf(CoreNames, name) >= 0;
                if (!replaced && !core) continue;                                        // not ours: leave it
                try { DeletePath(entry); }
                catch (Exception ex) { throw new SetupException("could not replace " + name + ": " + ex.Message); }
            }
            foreach (string entry in Directory.GetFileSystemEntries(source))
            {
                string name = Path.GetFileName(entry);
                string dest = Path.Combine(target, name);
                if (Array.IndexOf(KeepNames, name) >= 0 && (File.Exists(dest) || Directory.Exists(dest))) continue;
                if (Directory.Exists(entry)) CopyDirectory(entry, dest); else File.Copy(entry, dest, true);
            }
            SyncConfigVersion(Path.Combine(source, "config.json"), Path.Combine(target, "config.json"));
            Directory.Delete(stage, true);
            progress("install", 1.0, "");

            // this installer stays behind as the uninstaller
            string self = Assembly.GetExecutingAssembly().Location;
            string uninstaller = Path.Combine(target, "Uninstall.exe");
            if (!string.Equals(Path.GetFullPath(self), Path.GetFullPath(uninstaller), StringComparison.OrdinalIgnoreCase)) File.Copy(self, uninstaller, true);
            Register(target, rel.Version, uninstaller);
        }

        // config.json is kept (it holds the settings), but its version belongs to the package: bring it up to date so the OS reports the new version.
        private static void SyncConfigVersion(string packaged, string installed)
        {
            try
            {
                if (!File.Exists(packaged) || !File.Exists(installed)) return;
                string pattern = @"""version""\s*:\s*""([^""]*)""";
                System.Text.RegularExpressions.Match m = System.Text.RegularExpressions.Regex.Match(File.ReadAllText(packaged), pattern);
                if (!m.Success) return;
                string text = File.ReadAllText(installed);
                string fixedText = System.Text.RegularExpressions.Regex.Replace(text, pattern, "\"version\": \"" + m.Groups[1].Value + "\"");
                if (fixedText != text) File.WriteAllText(installed, fixedText);
            }
            catch (Exception ex) { Log.Write("could not update the version in config.json: " + ex.Message); }
        }

        private static void ExtractZip(string zip, string dest)
        {
            string root = Path.GetFullPath(dest) + Path.DirectorySeparatorChar;
            using (ZipArchive archive = ZipFile.OpenRead(zip))
            {
                foreach (ZipArchiveEntry e in archive.Entries)
                {
                    // some zip tools write backslashes; treat them as folder separators
                    string name = e.FullName.Replace('\\', '/');
                    string path = Path.GetFullPath(Path.Combine(dest, name));
                    if (!path.StartsWith(root, StringComparison.OrdinalIgnoreCase)) throw new SetupException("unsafe path in the package: " + e.FullName);   // zip slip
                    if (name.EndsWith("/")) { Directory.CreateDirectory(path); continue; }
                    Directory.CreateDirectory(Path.GetDirectoryName(path));
                    e.ExtractToFile(path, true);
                }
            }
        }

        private static void DeletePath(string path)
        {
            if (Directory.Exists(path)) Directory.Delete(path, true); else File.Delete(path);
        }

        private static void CopyDirectory(string from, string to)
        {
            Directory.CreateDirectory(to);
            foreach (string f in Directory.GetFiles(from)) File.Copy(f, Path.Combine(to, Path.GetFileName(f)), true);
            foreach (string d in Directory.GetDirectories(from)) CopyDirectory(d, Path.Combine(to, Path.GetFileName(d)));
        }

        // PythonOS owns a fixed amount of memory (see pyos/resources.py). A fresh install stores the choice; an update or repair never
        // touches the user's settings, and a settings file that already says something about memory is left alone.
        public static void WriteMemorySetting(Options o)
        {
            if (o.Mode != "install") return;
            try
            {
                string folder = Path.Combine(Path.GetFullPath(o.Directory), ".OSData");
                string file = Path.Combine(folder, "settings.json");
                if (File.Exists(file)) return;
                Directory.CreateDirectory(folder);
                File.WriteAllText(file, "{\"memory_limit_mb\": " + o.MemoryMb + "}\n", new System.Text.UTF8Encoding(false));
                Log.Write("memory " + o.MemoryMb + " MB");
            }
            catch (Exception e) { Log.Write("could not store the memory choice: " + e.Message); }
        }

        // ----------------------------------------------------------------- shortcuts and the uninstall entry
        private static string StartMenuFolder()
        {
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), AppName);
        }

        public static void MakeShortcuts(Options o)
        {
            string target = Path.Combine(Path.GetFullPath(o.Directory), "PythonOS.exe");
            string startLink = Path.Combine(StartMenuFolder(), "PythonOS.lnk");
            if (o.StartMenuShortcut)
            {
                Directory.CreateDirectory(StartMenuFolder());
                Shortcut(startLink, target, Path.GetFullPath(o.Directory));
            }
            else if (File.Exists(startLink)) { try { File.Delete(startLink); } catch (Exception) { } }
            string desktop = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "PythonOS.lnk");
            if (o.DesktopShortcut) Shortcut(desktop, target, Path.GetFullPath(o.Directory));
            else if (File.Exists(desktop)) { try { File.Delete(desktop); } catch (Exception) { } }
        }

        private static void Shortcut(string lnk, string target, string workDir)
        {
            Type shell = Type.GetTypeFromProgID("WScript.Shell");
            object sh = Activator.CreateInstance(shell);
            object link = shell.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, sh, new object[] { lnk });
            Type lt = link.GetType();
            lt.InvokeMember("TargetPath", BindingFlags.SetProperty, null, link, new object[] { target });
            lt.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, link, new object[] { workDir });
            lt.InvokeMember("Description", BindingFlags.SetProperty, null, link, new object[] { "PythonOS" });
            lt.InvokeMember("Save", BindingFlags.InvokeMethod, null, link, null);
        }

        private static void Register(string dir, string version, string uninstaller)
        {
            try { Registry.CurrentUser.DeleteSubKeyTree(InnoKey, false); } catch (Exception) { }     // replaces an older installer's entry
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(UninstallKey))
            {
                key.SetValue("DisplayName", "PythonOS");
                key.SetValue("DisplayVersion", version);
                key.SetValue("Publisher", "PythonOS");
                key.SetValue("InstallLocation", dir);
                key.SetValue("DisplayIcon", Path.Combine(dir, "PythonOS.exe"));
                key.SetValue("UninstallString", "\"" + uninstaller + "\" /uninstall");
                key.SetValue("QuietUninstallString", "\"" + uninstaller + "\" /uninstall /silent");
                key.SetValue("URLInfoAbout", "https://github.com/" + Repo);
                key.SetValue("NoModify", 1, RegistryValueKind.DWord);
                key.SetValue("NoRepair", 0, RegistryValueKind.DWord);
                key.SetValue("EstimatedSize", 400000, RegistryValueKind.DWord);
            }
        }

        // ----------------------------------------------------------------- removing
        public static void Uninstall(Options o, Progress progress)
        {
            Existing e = FindExisting();
            string dir = e != null ? e.Directory : o.Directory;
            progress("remove", 0.1, "");
            StopRunning(dir, true);
            try { File.Delete(Path.Combine(StartMenuFolder(), "PythonOS.lnk")); if (Directory.Exists(StartMenuFolder())) Directory.Delete(StartMenuFolder(), false); } catch (Exception ex) { Log.Write("start menu: " + ex.Message); }
            try { File.Delete(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "PythonOS.lnk")); } catch (Exception) { }
            progress("remove", 0.4, "");
            try { Registry.CurrentUser.DeleteSubKeyTree(UninstallKey, false); } catch (Exception ex) { Log.Write("registry: " + ex.Message); }

            if (Directory.Exists(dir))
            {
                foreach (string entry in Directory.GetFileSystemEntries(dir))
                {
                    string name = Path.GetFileName(entry);
                    if (!o.DeleteData && Array.IndexOf(KeepNames, name) >= 0) continue;
                    if (string.Equals(name, "Uninstall.exe", StringComparison.OrdinalIgnoreCase)) continue;      // we are running from it
                    try { DeletePath(entry); } catch (Exception ex) { Log.Write("could not remove " + name + ": " + ex.Message); }
                }
                progress("remove", 0.8, "");
                // the running Uninstall.exe cannot delete itself: a hidden command does it a moment after we exit
                bool empty = o.DeleteData;
                string cmd = empty
                    ? "/c ping -n 3 127.0.0.1 >nul & rmdir /s /q \"" + dir + "\""
                    : "/c ping -n 3 127.0.0.1 >nul & del /q \"" + Path.Combine(dir, "Uninstall.exe") + "\"";
                ProcessStartInfo psi = new ProcessStartInfo("cmd.exe", cmd);
                psi.CreateNoWindow = true;
                psi.UseShellExecute = false;
                Process.Start(psi);
            }
            progress("remove", 1.0, "");
            Log.Write("uninstalled" + (o.DeleteData ? " (data deleted)" : " (data kept)"));
        }

        // ----------------------------------------------------------------- requirements: the OS files and the Python libraries
        private static int RunPython(string dir, string arguments, out string output)
        {
            ProcessStartInfo psi = new ProcessStartInfo(Path.Combine(dir, "python", "python.exe"), arguments);
            psi.WorkingDirectory = dir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.EnvironmentVariables["PYTHONUTF8"] = "1";
            using (Process p = Process.Start(psi))
            {
                StringBuilder sb = new StringBuilder();
                p.OutputDataReceived += delegate (object s, DataReceivedEventArgs e) { if (e.Data != null) sb.AppendLine(e.Data); };
                p.ErrorDataReceived += delegate (object s, DataReceivedEventArgs e) { if (e.Data != null) sb.AppendLine(e.Data); };
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                p.WaitForExit();
                output = sb.ToString();
                return p.ExitCode;
            }
        }

        private static bool LibrariesImport(string dir)
        {
            string output;
            try { return RunPython(dir, "-c \"import rich, psutil, requests, yaspin, ping3, prompt_toolkit, pygments\"", out output) == 0; }
            catch (Exception) { return false; }
        }

        /// <summary>Check that everything PythonOS needs is there and download what is not: the system files (main.py, commands, ...)
        /// and the Python libraries. Needs the internet only when something is missing.</summary>
        public static void EnsureRequirements(Options o, Progress progress)
        {
            string dir = Path.GetFullPath(o.Directory);
            string[] files = new string[] { "main.py", "shell.py", "users.py", "VERSION", "requirements.txt", "boot-requirements.txt" };
            string[] folders = new string[] { "commands", "core", "programs", "pyos" };
            List<string> gone = new List<string>();
            foreach (string f in files) if (!File.Exists(Path.Combine(dir, f))) gone.Add(f);
            foreach (string f in folders) if (!Directory.Exists(Path.Combine(dir, f))) gone.Add(f);
            if (!File.Exists(Path.Combine(dir, "python", "python.exe"))) throw new SetupException("python\\python.exe is missing from the package");

            progress("requirements", 0.1, "");
            if (gone.Count > 0)
            {
                Log.Write("missing: " + string.Join(", ", gone.ToArray()) + " - downloading the PythonOS system");
                progress("requirements", 0.2, Strings.T("req.system"));
                string output;
                int code = RunPython(dir, "\"" + Path.Combine(dir, "bootstrap.py") + "\" --dest \"" + dir + "\"", out output);
                Log.Write("bootstrap exit " + code + ": " + output.Trim());
                if (code != 0) throw new SetupException(Strings.T("err.system"));
            }
            progress("requirements", 0.6, "");
            if (!LibrariesImport(dir))
            {
                Log.Write("Python libraries missing - installing them");
                progress("requirements", 0.7, Strings.T("req.libraries"));
                string output;
                string args = "-m pip install --quiet --no-warn-script-location";
                foreach (string r in new string[] { "requirements.txt", "boot-requirements.txt" })
                    if (File.Exists(Path.Combine(dir, r))) args += " -r \"" + Path.Combine(dir, r) + "\"";
                int code = RunPython(dir, args, out output);
                Log.Write("pip exit " + code + ": " + output.Trim());
                if (code != 0 || !LibrariesImport(dir)) throw new SetupException(Strings.T("err.libraries"));
            }
            progress("requirements", 1.0, "");
        }

        // ----------------------------------------------------------------- one run, start to end
        public static Release InstallOrUpdate(Options o, Progress progress, CancelToken cancel)
        {
            progress("check", 0.2, "");
            Log.Write("mode " + o.Mode + ", directory " + o.Directory);
            CheckRequirements(o);
            progress("check", 1.0, "");
            if (o.Mode != "install" && IsRunning(Path.GetFullPath(o.Directory)))
            {
                StopRunning(Path.GetFullPath(o.Directory), o.Silent);
            }
            progress("find", 0.3, "");
            Release rel = FindRelease(o);
            progress("find", 1.0, "");
            string file = Download(rel, progress, cancel);
            progress("verify", 0.3, "");
            Verify(file, rel);
            progress("verify", 1.0, "");
            InstallPackage(file, o, rel, progress);
            EnsureRequirements(o, progress);
            WriteMemorySetting(o);
            progress("shortcuts", 0.5, "");
            MakeShortcuts(o);
            progress("shortcuts", 1.0, "");
            try { File.Delete(file); } catch (Exception) { }
            Log.Write("installed " + rel.Version);
            return rel;
        }
    }

    internal sealed class CancelToken
    {
        private volatile bool cancelled;
        public bool Cancelled { get { return cancelled; } }
        public void Cancel() { cancelled = true; }
    }
}
