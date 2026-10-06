// The installer window: a header, one page at a time (welcome, options, progress, done or failed) and the buttons at the bottom.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Threading;
using System.Windows.Forms;

namespace PythonOS.Setup
{
    internal sealed class SetupForm : Form
    {
        [System.Runtime.InteropServices.DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);

        private readonly Palette p = Palette.FromSystem();
        private readonly Options o;
        private readonly Existing existing;
        private readonly CancelToken cancel = new CancelToken();
        private readonly Panel body = new Panel();
        private Label title, sub;
        private ModernButton primary, secondary;
        private readonly List<ModernRadio> choices = new List<ModernRadio>();
        private ModernProgress bar;
        private StepList steps;
        private Label detail;
        private TextBox pathBox;
        private ModernCheck desktop, startMenu, launch, keepData, webview;
        private ComboBox memory;
        private static readonly int[] MemoryChoices = new int[] { 512, 1024, 2048, 4096, 0 };
        private string page = "";
        private bool working;
        private Release finished;
        private string errorText = "";

        public SetupForm(Options options, Existing found)
        {
            o = options; existing = found;
            Strings.Language = Strings.Detect();
            Text = Strings.T("title");
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(660, 470);
            BackColor = p.Bg;
            DoubleBuffered = true;
            Font = new Font("Segoe UI", 10f);
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }

            title = new Label(); title.Font = new Font("Segoe UI Semibold", 20f); title.ForeColor = p.Text; title.BackColor = p.Bg;
            title.SetBounds(32, 22, 600, 40);
            sub = new Label(); sub.Font = new Font("Segoe UI", 10f); sub.ForeColor = p.Muted; sub.BackColor = p.Bg;
            sub.SetBounds(34, 66, 590, 44);
            body.SetBounds(32, 120, 596, 270); body.BackColor = p.Bg;
            primary = new ModernButton(p, "", true); primary.SetBounds(508, 412, 120, 40);
            secondary = new ModernButton(p, "", false); secondary.SetBounds(378, 412, 120, 40);
            Controls.AddRange(new Control[] { title, sub, body, primary, secondary });
            primary.Click += delegate { OnPrimary(); };
            secondary.Click += delegate { OnSecondary(); };
            FormClosing += OnClosing;
            HandleCreated += delegate
            {
                try { int on = p.Light ? 0 : 1; if (DwmSetWindowAttribute(Handle, 20, ref on, 4) != 0) DwmSetWindowAttribute(Handle, 19, ref on, 4); } catch (Exception) { }
            };
            Load += delegate { Start(); };
        }

        // ------------------------------------------------------------- flow
        private void Start()
        {
            if (o.Mode == "uninstall") { ShowUninstall(); return; }
            ShowWelcome();
        }

        private void Reset(string name, string heading, string subheading)
        {
            page = name;
            foreach (Control c in new List<Control>(body.Controls.Cast())) { body.Controls.Remove(c); c.Dispose(); }
            choices.Clear();
            title.Text = heading;
            sub.Text = subheading;
            secondary.Visible = true;
            primary.Enabled = true;
        }

        private void ShowWelcome()
        {
            Reset("welcome", Strings.T("welcome"), Strings.T("welcome.sub"));
            int y = 0;
            Label lang = Small(Strings.T("language")); lang.Top = y; body.Controls.Add(lang);
            y += 26;
            int x = 0;
            for (int i = 0; i < Strings.Codes.Length; i++)
            {
                string code = Strings.Codes[i];
                ModernButton chip = new ModernButton(p, Strings.Names[i], false);
                chip.Toggled = code == Strings.Language;
                chip.SetBounds(x, y, 110, 36);
                chip.Click += delegate { Strings.Language = code; Text = Strings.T("title"); ShowWelcome(); };
                body.Controls.Add(chip);
                x += 120;
            }
            y += 56;
            if (existing != null)
            {
                Label found = Small(Strings.T("found", existing.Version, existing.Directory)); found.SetBounds(0, y, 596, 22); found.ForeColor = p.Text; body.Controls.Add(found);
                y += 30;
                AddChoice("update", Strings.T("opt.update", "latest"), y); y += 46;
                AddChoice("repair", Strings.T("opt.repair"), y); y += 46;
                AddChoice("uninstall", Strings.T("opt.uninstall"), y);
                choices[0].Choose();
                o.Directory = existing.Directory;
                primary.Text = Strings.T("next");
            }
            else
            {
                primary.Text = Strings.T("next");
            }
            secondary.Text = Strings.T("cancel");
            secondary.Visible = true;
        }

        private void AddChoice(string key, string text, int y)
        {
            ModernRadio r = new ModernRadio(p, choices, key, text);
            r.SetBounds(0, y, 596, 40);
            body.Controls.Add(r);
        }

        private void ShowOptions()
        {
            Reset("options", Strings.T("where"), "");
            Label l = Small(Strings.T("where")); l.Top = 0; body.Controls.Add(l);
            pathBox = new TextBox();
            pathBox.BorderStyle = BorderStyle.FixedSingle; pathBox.BackColor = p.Surface; pathBox.ForeColor = p.Text; pathBox.Font = new Font("Segoe UI", 10.5f);
            pathBox.SetBounds(0, 28, 480, 28); pathBox.Text = o.Directory;
            body.Controls.Add(pathBox);
            ModernButton browse = new ModernButton(p, Strings.T("browse"), false); browse.SetBounds(490, 24, 106, 36);
            browse.Click += delegate
            {
                using (FolderBrowserDialog d = new FolderBrowserDialog())
                {
                    d.SelectedPath = pathBox.Text;
                    if (d.ShowDialog(this) == DialogResult.OK) pathBox.Text = Path.Combine(d.SelectedPath, "PythonOS");
                }
            };
            body.Controls.Add(browse);
            startMenu = new ModernCheck(p, Strings.T("startmenu"), o.StartMenuShortcut); startMenu.SetBounds(0, 78, 596, 28); body.Controls.Add(startMenu);
            desktop = new ModernCheck(p, Strings.T("desktop"), o.DesktopShortcut); desktop.SetBounds(0, 110, 596, 28); body.Controls.Add(desktop);
            Label ml = Small(Strings.T("memory")); ml.SetBounds(0, 150, 596, 22); body.Controls.Add(ml);
            memory = new ComboBox();
            memory.DropDownStyle = ComboBoxStyle.DropDownList; memory.FlatStyle = FlatStyle.Flat; memory.BackColor = p.Surface; memory.ForeColor = p.Text;
            memory.Font = new Font("Segoe UI", 10.5f); memory.SetBounds(0, 174, 280, 30);
            foreach (int mb in MemoryChoices) memory.Items.Add(mb == 0 ? Strings.T("memory.all") : (mb >= 1024 ? (mb / 1024) + " GB" : mb + " MB"));
            memory.SelectedIndex = Math.Max(0, Array.IndexOf(MemoryChoices, o.MemoryMb));
            body.Controls.Add(memory);
            int y = 216;
            if (!Core.HasWebView2())
            {
                Label w = Small(Strings.T("webview")); w.SetBounds(0, y, 596, 22); w.ForeColor = p.Text; body.Controls.Add(w);
                webview = new ModernCheck(p, Strings.T("webview.get"), true); webview.SetBounds(0, y + 26, 596, 28); body.Controls.Add(webview);
            }
            primary.Text = Strings.T(o.Mode == "update" ? "update" : "install");
            secondary.Text = Strings.T("back");
        }

        private void ShowProgress()
        {
            string[] keys = new string[] { "check", "find", "download", "verify", "install", "requirements", "shortcuts" };
            string[] names = new string[keys.Length];
            for (int i = 0; i < keys.Length; i++) names[i] = Strings.T("step." + keys[i]);
            Reset("progress", Strings.T(o.Mode == "repair" ? "repair" : o.Mode == "update" ? "update" : "install") + " PythonOS", "");
            steps = new StepList(p); steps.SetBounds(0, 0, 596, 7 * 32 + 4); steps.Set(keys, names); body.Controls.Add(steps);
            bar = new ModernProgress(p); bar.SetBounds(0, 7 * 32 + 22, 596, 10); body.Controls.Add(bar);
            detail = Small(""); detail.SetBounds(0, 7 * 32 + 40, 596, 22); body.Controls.Add(detail);
            primary.Visible = false;
            secondary.Text = Strings.T("cancel");
            Run();
        }

        private void ShowUninstall()
        {
            Reset("uninstall", Strings.T("uninstall") + " PythonOS", Strings.T("uninstall.ask"));
            keepData = new ModernCheck(p, Strings.T("keepdata"), false); keepData.SetBounds(0, 20, 596, 28); body.Controls.Add(keepData);
            primary.Text = Strings.T("uninstall");
            secondary.Text = Strings.T("cancel");
        }

        private void ShowDone(string text)
        {
            Reset("done", text, Strings.T("done.sub"));
            primary.Visible = true;
            if (o.Mode != "uninstall")
            {
                launch = new ModernCheck(p, Strings.T("launch"), true); launch.SetBounds(0, 20, 596, 28); body.Controls.Add(launch);
            }
            primary.Text = Strings.T("close");
            secondary.Text = Strings.T("openlog");
        }

        private void ShowFailed()
        {
            Reset("failed", Strings.T("failed"), Strings.T("failed.sub"));
            primary.Visible = true;
            Label msg = new Label(); msg.Text = errorText; msg.ForeColor = p.Bad; msg.BackColor = p.Bg; msg.Font = new Font("Segoe UI Semibold", 10.5f); msg.SetBounds(0, 0, 596, 80);
            body.Controls.Add(msg);
            Label log = Small(Log.Path_); log.SetBounds(0, 90, 596, 40); body.Controls.Add(log);
            primary.Text = Strings.T("retry");
            secondary.Text = Strings.T("openlog");
        }

        private Label Small(string text)
        {
            Label l = new Label(); l.Text = text; l.ForeColor = p.Muted; l.BackColor = p.Bg; l.Font = new Font("Segoe UI", 10f); l.AutoSize = false; l.Height = 22; l.Width = 596;
            return l;
        }

        // ------------------------------------------------------------- buttons
        private void OnPrimary()
        {
            if (page == "welcome")
            {
                if (existing != null)
                {
                    string pick = "update";
                    foreach (ModernRadio r in choices) if (r.Selected) pick = r.Key;
                    o.Mode = pick;
                    if (pick == "uninstall") { ShowUninstall(); return; }
                    if (pick == "repair") { ShowProgress(); return; }
                    ShowProgress();
                    return;
                }
                ShowOptions();
            }
            else if (page == "options")
            {
                o.Directory = pathBox.Text.Trim();
                o.DesktopShortcut = desktop.Checked;
                o.StartMenuShortcut = startMenu.Checked;
                o.FixWebView2 = webview == null || webview.Checked;
                if (memory != null && memory.SelectedIndex >= 0) o.MemoryMb = MemoryChoices[memory.SelectedIndex];
                if (o.Directory.Length == 0) return;
                ShowProgress();
            }
            else if (page == "uninstall")
            {
                o.DeleteData = keepData.Checked;
                o.Mode = "uninstall";
                ShowProgressUninstall();
            }
            else if (page == "done")
            {
                if (launch != null && launch.Checked) LaunchApp();
                Close();
            }
            else if (page == "failed")
            {
                ShowWelcome();
            }
        }

        private void OnSecondary()
        {
            if (page == "welcome" || page == "uninstall") { Close(); }
            else if (page == "options") ShowWelcome();
            else if (page == "progress") { cancel.Cancel(); secondary.Enabled = false; }
            else if (page == "done" || page == "failed") OpenLog();
        }

        private void OpenLog()
        {
            try { Process.Start("notepad.exe", "\"" + Log.Path_ + "\""); } catch (Exception) { }
        }

        private void LaunchApp()
        {
            try
            {
                string exe = Path.Combine(Path.GetFullPath(o.Directory), "PythonOS.exe");
                if (File.Exists(exe)) Process.Start(new ProcessStartInfo(exe) { WorkingDirectory = Path.GetDirectoryName(exe) });
            }
            catch (Exception ex) { Log.Write("launch failed: " + ex.Message); }
        }

        private void OnClosing(object sender, FormClosingEventArgs e)
        {
            if (working) { cancel.Cancel(); }
        }

        // ------------------------------------------------------------- the work
        private void Report(string step, double fraction, string text)
        {
            if (!IsHandleCreated) return;
            BeginInvoke((MethodInvoker)delegate
            {
                if (steps == null) return;
                steps.Current(step);
                if (bar != null) bar.Value = fraction;
                if (detail != null) detail.Text = text;
            });
        }

        private void Run()
        {
            working = true;
            Thread t = new Thread(delegate ()
            {
                try
                {
                    Core.PrepareNetwork();
                    if (!Core.HasWebView2() && o.FixWebView2)
                    {
                        Report("check", 0.6, Strings.T("webview"));
                        try { Core.InstallWebView2(Report2); } catch (Exception ex) { Log.Write("WebView2 install failed: " + ex.Message); }
                    }
                    Release rel = Core.InstallOrUpdate(o, Report2, cancel);
                    finished = rel;
                    BeginInvoke((MethodInvoker)delegate { working = false; steps.AllDone(); bar.Value = 1; ShowDone(DoneText(rel)); });
                }
                catch (OperationCanceledException)
                {
                    Log.Write("cancelled");
                    BeginInvoke((MethodInvoker)delegate { working = false; Close(); });
                }
                catch (Exception ex)
                {
                    Log.Write("FAILED: " + ex);
                    errorText = ex is SetupException ? ex.Message : ex.GetType().Name + ": " + ex.Message;
                    BeginInvoke((MethodInvoker)delegate { working = false; if (steps != null) steps.Fail(); ShowFailed(); });
                }
            });
            t.IsBackground = true;
            t.Start();
        }

        private void Report2(string step, double fraction, string text) { Report(step, fraction, text); }

        private string DoneText(Release rel)
        {
            if (o.Mode == "update") return Strings.T("done.update", rel.Version);
            if (o.Mode == "repair") return Strings.T("done.repair");
            return Strings.T("done");
        }

        private void ShowProgressUninstall()
        {
            Reset("progress", Strings.T("uninstall") + " PythonOS", "");
            steps = new StepList(p); steps.SetBounds(0, 0, 596, 40); steps.Set(new string[] { "remove" }, new string[] { Strings.T("step.remove") }); body.Controls.Add(steps);
            bar = new ModernProgress(p); bar.SetBounds(0, 60, 596, 10); body.Controls.Add(bar);
            primary.Visible = false; secondary.Visible = false;
            working = true;
            Thread t = new Thread(delegate ()
            {
                try
                {
                    Core.Uninstall(o, Report2);
                    BeginInvoke((MethodInvoker)delegate { working = false; ShowDone(Strings.T("done.uninstall")); });
                }
                catch (Exception ex)
                {
                    Log.Write("FAILED: " + ex);
                    errorText = ex.Message;
                    BeginInvoke((MethodInvoker)delegate { working = false; ShowFailed(); });
                }
            });
            t.IsBackground = true;
            t.Start();
        }
    }

    internal static class Extensions
    {
        public static IEnumerable<Control> Cast(this Control.ControlCollection c)
        {
            foreach (Control x in c) yield return x;
        }
    }
}
