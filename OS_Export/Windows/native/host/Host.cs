// PythonOS.exe - PythonOS in its own window instead of the default Command Prompt.
//
// The window is a WebView2 (the Microsoft Edge engine that Windows 11 includes) showing xterm.js, a proper terminal emulator:
// full colour, box drawing, selection, clipboard, light and dark themes, resizing. The program inside is the bundled Python running
// start.py, connected through a pseudo console (ConPty.cs), so everything PythonOS prints and reads works exactly as it does in a
// console. Written in C# 5 so it builds with the compiler that ships with Windows (see build-native.ps1).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
using Microsoft.Win32;

namespace PythonOS
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            string dir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
            if (Array.IndexOf(args, "--console") >= 0) return Fallback.RunConsole(dir);
            Application.Run(new TerminalForm(dir));
            return 0;
        }
    }

    /// <summary>The plain console launcher, used when the window cannot start (no WebView2, or Windows older than 10 1809).</summary>
    internal static class Fallback
    {
        public static int RunConsole(string dir)
        {
            string console = Path.Combine(dir, "PythonOS-console.exe");
            if (!File.Exists(console)) return 2;
            ProcessStartInfo psi = new ProcessStartInfo(console);
            psi.WorkingDirectory = dir;
            psi.UseShellExecute = true;
            Process.Start(psi);
            return 0;
        }
    }

    internal sealed class TerminalForm : Form
    {
        [DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);

        private readonly string dir;
        private readonly WebView2 web = new WebView2();
        private ConPtySession pty;
        private readonly List<byte[]> pending = new List<byte[]>();
        private readonly object pendingLock = new object();
        private readonly Timer flush = new Timer();
        private bool started;
        private bool finished;
        private int columns = 80, rows = 24;
        private readonly string settingsFile;

        public TerminalForm(string dir)
        {
            this.dir = dir;
            string data = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PythonOS");
            Directory.CreateDirectory(data);
            settingsFile = Path.Combine(data, "window.txt");

            Text = "PythonOS";
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(1000, 640);
            MinimumSize = new Size(480, 320);
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }
            bool light = IsLightTheme();
            BackColor = light ? Color.FromArgb(250, 250, 250) : Color.FromArgb(12, 12, 12);
            LoadBounds();

            web.Dock = DockStyle.Fill;
            web.DefaultBackgroundColor = BackColor;
            Controls.Add(web);

            flush.Interval = 15;
            flush.Tick += delegate { Flush(); };
            flush.Start();

            Load += delegate { StartWeb(); };
            FormClosing += delegate { SaveBounds(); if (pty != null) { pty.Kill(); pty.Dispose(); } };
            HandleCreated += delegate { UseDarkTitleBar(!light); };
        }

        // ------------------------------------------------------------ appearance
        private static bool IsLightTheme()
        {
            try
            {
                object v = Registry.GetValue(@"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme", 1);
                return !(v is int) || (int)v != 0;
            }
            catch (Exception) { return false; }
        }

        private void UseDarkTitleBar(bool dark)
        {
            try
            {
                int on = dark ? 1 : 0;
                if (DwmSetWindowAttribute(Handle, 20, ref on, 4) != 0) DwmSetWindowAttribute(Handle, 19, ref on, 4);
            }
            catch (Exception) { }
        }

        private void LoadBounds()
        {
            try
            {
                if (!File.Exists(settingsFile)) return;
                string[] p = File.ReadAllText(settingsFile).Trim().Split(',');
                if (p.Length < 5) return;
                Rectangle r = new Rectangle(int.Parse(p[0]), int.Parse(p[1]), int.Parse(p[2]), int.Parse(p[3]));
                bool visible = false;
                foreach (Screen s in Screen.AllScreens) if (s.WorkingArea.IntersectsWith(r)) visible = true;
                if (!visible) return;
                StartPosition = FormStartPosition.Manual;
                Bounds = r;
                if (p[4] == "max") WindowState = FormWindowState.Maximized;
            }
            catch (Exception) { }
        }

        private void SaveBounds()
        {
            try
            {
                Rectangle r = WindowState == FormWindowState.Normal ? Bounds : RestoreBoundsRect();
                File.WriteAllText(settingsFile, r.X + "," + r.Y + "," + r.Width + "," + r.Height + "," + (WindowState == FormWindowState.Maximized ? "max" : "normal"));
            }
            catch (Exception) { }
        }

        private Rectangle RestoreBoundsRect() { return base.RestoreBounds; }

        // ------------------------------------------------------------ the web view
        private async void StartWeb()
        {
            try
            {
                if (!ConPtySession.IsSupported()) throw new InvalidOperationException("Windows 10 version 1809 or newer is needed.");
                string cache = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PythonOS", "WebView2");
                CoreWebView2Environment env = await CoreWebView2Environment.CreateAsync(null, cache);
                await web.EnsureCoreWebView2Async(env);
            }
            catch (Exception ex)
            {
                CannotStart(ex);
                return;
            }
            CoreWebView2 core = web.CoreWebView2;
            core.Settings.AreDevToolsEnabled = false;
            core.Settings.AreDefaultContextMenusEnabled = false;
            core.Settings.IsZoomControlEnabled = false;
            core.Settings.IsStatusBarEnabled = false;
            core.SetVirtualHostNameToFolderMapping("pythonos.app", Path.Combine(dir, "web"), CoreWebView2HostResourceAccessKind.Allow);
            core.WebMessageReceived += OnMessage;
            core.NewWindowRequested += delegate (object s, CoreWebView2NewWindowRequestedEventArgs e) { e.Handled = true; };
            core.Navigate("https://pythonos.app/terminal.html");
        }

        private void CannotStart(Exception ex)
        {
            string console = Path.Combine(dir, "PythonOS-console.exe");
            string text = "PythonOS could not open its window:\n\n" + ex.Message +
                "\n\nIt needs the Microsoft WebView2 Runtime (included with Windows 11 and with current Microsoft Edge on Windows 10).";
            if (File.Exists(console))
            {
                text += "\n\nStart PythonOS in the plain console window instead?";
                if (MessageBox.Show(this, text, "PythonOS", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) == DialogResult.Yes) Fallback.RunConsole(dir);
            }
            else
            {
                MessageBox.Show(this, text, "PythonOS", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            finished = true;
            Close();
        }

        private void OnMessage(object sender, CoreWebView2WebMessageReceivedEventArgs e)
        {
            string m;
            try { m = e.TryGetWebMessageAsString(); } catch (Exception) { return; }
            if (string.IsNullOrEmpty(m)) return;
            if (m.StartsWith("i:"))
            {
                if (finished) { Close(); return; }            // any key closes the window after PythonOS has stopped
                if (pty != null) pty.Write(m.Substring(2));
            }
            else if (m.StartsWith("r:"))
            {
                string[] p = m.Substring(2).Split(',');
                int c, r;
                if (p.Length == 2 && int.TryParse(p[0], out c) && int.TryParse(p[1], out r) && c > 0 && r > 0)
                {
                    columns = c;
                    rows = r;
                    if (pty != null) pty.Resize(c, r);
                    else if (!started) { started = true; StartPython(); }
                }
            }
        }

        // ------------------------------------------------------------ the program
        private void StartPython()
        {
            string python = Path.Combine(dir, "python", "python.exe");
            string start = Path.Combine(dir, "start.py");
            if (!File.Exists(python) || !File.Exists(start))
            {
                Send("PythonOS cannot start: python\\python.exe or start.py is missing.\r\nRe-install PythonOS.\r\n");
                finished = true;
                return;
            }
            Environment.SetEnvironmentVariable("PYTHONUTF8", "1");
            Environment.SetEnvironmentVariable("PYTHONIOENCODING", "utf-8");
            Environment.SetEnvironmentVariable("TERM", "xterm-256color");
            Environment.SetEnvironmentVariable("COLORTERM", "truecolor");
            Environment.SetEnvironmentVariable("NO_COLOR", null);       // this window shows colour; PythonOS has its own mono theme if you want none
            Environment.SetEnvironmentVariable("PYOS_EXPORT_INFO", Path.Combine(dir, "export.json"));
            pty = new ConPtySession();
            pty.Output += delegate (byte[] bytes, int count) { lock (pendingLock) { pending.Add(bytes); } };
            pty.Exited += OnExited;
            try
            {
                pty.Start("\"" + python + "\" \"" + start + "\"", dir, columns, rows);
            }
            catch (Exception ex)
            {
                Send("PythonOS could not be started: " + ex.Message + "\r\n");
                finished = true;
            }
        }

        private void OnExited(int code)
        {
            try
            {
                BeginInvoke((MethodInvoker)delegate
                {
                    Flush();
                    if (code == 0) { finished = true; Close(); return; }
                    finished = true;
                    Send("\r\n\x1b[31mPythonOS stopped (exit code " + code + ").\x1b[0m Press any key to close this window.\r\n");
                });
            }
            catch (Exception) { }
        }

        private void Send(string text)
        {
            lock (pendingLock) { pending.Add(Encoding.UTF8.GetBytes(text)); }
        }

        /// <summary>Hand what the program printed to the page, a few times per second at most (one message for a whole burst).</summary>
        private void Flush()
        {
            if (web.CoreWebView2 == null) return;
            byte[] all;
            lock (pendingLock)
            {
                if (pending.Count == 0) return;
                int total = 0;
                foreach (byte[] b in pending) total += b.Length;
                all = new byte[total];
                int at = 0;
                foreach (byte[] b in pending) { Buffer.BlockCopy(b, 0, all, at, b.Length); at += b.Length; }
                pending.Clear();
            }
            web.CoreWebView2.PostWebMessageAsString("o:" + Convert.ToBase64String(all));
        }
    }
}
