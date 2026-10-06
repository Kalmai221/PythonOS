// PythonOS-Setup.exe - a small installer (about 100 KB): it downloads PythonOS from GitHub, checks it against the release's
// checksums, installs it for the current user (no administrator needed), makes shortcuts and registers an uninstaller.
//
//   PythonOS-Setup.exe                      the window
//   PythonOS-Setup.exe /silent              no window: install (or update if installed) and start nothing
//   PythonOS-Setup.exe /update /silent      update an existing install (PythonOS itself runs this when it needs a new app package)
//   PythonOS-Setup.exe /repair /silent      reinstall the program files, keep the data
//   PythonOS-Setup.exe /uninstall [/silent] [/deletedata]
//   options: /dir=PATH  /lang=en|es|fr|de  /nolaunch  /desktop  /nostartmenu  /nowebview2  /manifest=URL (developers: a stand-in for GitHub's "latest release" JSON)
//
// It is also the uninstaller: after installing, a copy named Uninstall.exe stays in the install folder. Written in C# 5 so it builds
// with the compiler that ships with Windows (see build-native.ps1). Log: %LOCALAPPDATA%\PythonOS\Setup\install-log.txt
using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Windows.Forms;

namespace PythonOS.Setup
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            Options o = new Options();
            string lang = null;
            bool dirGiven = false;
            foreach (string raw in args)
            {
                string a = raw.Trim();
                string low = a.ToLowerInvariant();
                if (low == "/silent" || low == "/verysilent" || low == "-silent") o.Silent = true;
                else if (low == "/update") o.Mode = "update";
                else if (low == "/repair") o.Mode = "repair";
                else if (low == "/uninstall") o.Mode = "uninstall";
                else if (low == "/nolaunch") o.Launch = false;
                else if (low == "/desktop") o.DesktopShortcut = true;
                else if (low == "/nostartmenu") o.StartMenuShortcut = false;
                else if (low == "/deletedata") o.DeleteData = true;
                else if (low == "/nowebview2") o.FixWebView2 = false;
                else if (low.StartsWith("/memory="))
                {
                    string m = low.Substring(8);
                    int mb;
                    if (m == "all") o.MemoryMb = 0; else if (int.TryParse(m, out mb) && mb >= 256) o.MemoryMb = mb;
                }
                else if (low.StartsWith("/dir=")) { o.Directory = a.Substring(5).Trim('"'); dirGiven = true; }
                else if (low.StartsWith("/lang=")) lang = low.Substring(6);
                else if (low.StartsWith("/manifest=")) o.ManifestUrl = a.Substring(10);
            }
            Log.Write("---- PythonOS Setup " + string.Join(" ", args));
            Existing existing = Core.FindExisting();
            if (existing != null && !dirGiven) { o.Directory = existing.Directory; }          // an update or repair always goes where PythonOS already is
            if (existing == null && (o.Mode == "update" || o.Mode == "repair")) o.Mode = "install";
            if (existing != null && o.Silent && o.Mode == "install") o.Mode = "update";
            if (lang != null && Array.IndexOf(Strings.Codes, lang) >= 0) Strings.Language = lang;
            else Strings.Language = Strings.Detect();

            if (o.Silent) return RunSilent(o);

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            SetupForm form = new SetupForm(o, existing);
            if (lang != null) Strings.Language = lang;
            Application.Run(form);
            return 0;
        }

        private static int RunSilent(Options o)
        {
            try
            {
                Core.PrepareNetwork();
                if (o.Mode == "uninstall")
                {
                    Core.Uninstall(o, delegate (string s, double f, string d) { });
                    return 0;
                }
                if (!Core.HasWebView2() && o.FixWebView2)
                {
                    try { Core.InstallWebView2(delegate (string s, double f, string d) { }); } catch (Exception ex) { Log.Write("WebView2 install failed: " + ex.Message); }
                }
                CancelToken cancel = new CancelToken();
                Release rel = Core.InstallOrUpdate(o, delegate (string s, double f, string d) { }, cancel);
                if (o.Launch)
                {
                    string exe = Path.Combine(Path.GetFullPath(o.Directory), "PythonOS.exe");
                    if (File.Exists(exe)) Process.Start(new ProcessStartInfo(exe) { WorkingDirectory = Path.GetDirectoryName(exe) });
                }
                return 0;
            }
            catch (Exception ex)
            {
                Log.Write("FAILED: " + ex);
                Console.Error.WriteLine(ex.Message);
                return 1;
            }
        }
    }
}
