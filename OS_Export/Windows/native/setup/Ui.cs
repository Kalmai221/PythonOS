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
        [System.Runtime.InteropServices.DllImport("uxtheme.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
        private static extern int SetWindowTheme(IntPtr hwnd, string subAppName, string subIdList);

        [System.Runtime.InteropServices.DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);

        private readonly Palette p = Palette.FromSystem();
        private readonly Options o;
        private readonly Existing existing;
        private readonly CancelToken cancel = new CancelToken();
        private readonly Panel body = new Panel();
        private Label title, sub;
        private ModernButton primary, secondary, tertiary;
        private readonly List<ModernRadio> choices = new List<ModernRadio>();
        private ModernProgress bar;
        private StepList steps;
        private Label detail;
        private ModernInput pathBox;
        private ModernCheck desktop, startMenu, launch, keepData, webview;
        private ModernDropdown memory;
        private readonly List<ModernCheck> extraChecks = new List<ModernCheck>();
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
            ClientSize = new Size(660, 510);
            BackColor = p.Bg;
            DoubleBuffered = true;
            Font = new Font("Segoe UI", 10f);
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }

            title = new Label(); title.Font = new Font("Segoe UI Semibold", 20f); title.ForeColor = p.Text; title.BackColor = p.Bg;
            title.SetBounds(86, 24, 440, 40);
            sub = new Label(); sub.Font = new Font("Segoe UI", 10f); sub.ForeColor = p.Muted; sub.BackColor = p.Bg;
            sub.SetBounds(34, 74, 590, 40);
            body.SetBounds(32, 118, 596, 320); body.BackColor = p.Bg;
            primary = new ModernButton(p, "", true); primary.SetBounds(508, 452, 120, 40);
            secondary = new ModernButton(p, "", false); secondary.SetBounds(378, 452, 120, 40);
            tertiary = new ModernButton(p, "", false); tertiary.SetBounds(32, 452, 160, 40); tertiary.Visible = false;
            Controls.AddRange(new Control[] { title, sub, body, primary, secondary, tertiary });
            primary.Click += delegate { OnPrimary(); };
            secondary.Click += delegate { OnSecondary(); };
            tertiary.Click += delegate { OnTertiary(); };
            FormClosing += OnClosing;
            KeyPreview = true;
            KeyDown += OnKey;
            HandleCreated += delegate
            {
                try { int on = p.Light ? 0 : 1; if (DwmSetWindowAttribute(Handle, 20, ref on, 4) != 0) DwmSetWindowAttribute(Handle, 19, ref on, 4); } catch (Exception) { }
                // Windows 11: rounded corners, and a title bar in the page's own colour so the window looks like one piece (ignored where unsupported)
                try
                {
                    int round = 2; DwmSetWindowAttribute(Handle, 33, ref round, 4);
                    int caption = p.Bg.R | (p.Bg.G << 8) | (p.Bg.B << 16); DwmSetWindowAttribute(Handle, 35, ref caption, 4);
                    int border = p.Border.R | (p.Border.G << 8) | (p.Border.B << 16); DwmSetWindowAttribute(Handle, 34, ref border, 4);
                    int text = p.Text.R | (p.Text.G << 8) | (p.Text.B << 16); DwmSetWindowAttribute(Handle, 36, ref text, 4);
                }
                catch (Exception) { }
            };
            Load += delegate { Start(); };
        }

        // ------------------------------------------------------------- flow
        private void Start()
        {
            if (o.Preview.Length > 0) { Preview(); return; }
            if (o.Mode == "uninstall") { ShowUninstall(); return; }
            ShowWelcome();
        }

        /// <summary>For developers: a page with sample data, so it can be looked at (and photographed) without installing anything.</summary>
        private void Preview()
        {
            Release sample = new Release();
            sample.Version = "1.0.13"; sample.InstalledVersion = "1.0.13"; sample.Notes = "## PythonOS\n\n- A new `extras` command chooses the optional libraries.\n- Six new libraries and eighteen new commands.\n- The marketplace speaks your language.\n\n## Exports\n\n- The installer asks which libraries you want.";
            if (o.Preview == "options") ShowOptions();
            else if (o.Preview == "extras") ShowExtras();
            else if (o.Preview == "done") ShowDone(Strings.T("done"), sample);
            else if (o.Preview == "failed") { errorText = "Unable to connect to the remote server"; ShowFailed(); }
            else if (o.Preview == "progress")
            {
                ShowProgress();
                steps.Current("download"); bar.Value = 0.42; detail.Text = Strings.T("speed", "12.3 MB", "29.0 MB", "3.1 MB") + Strings.T("eta", "5 s");
            }
            else ShowWelcome();
        }

        // The steps of a journey as dots at the top right: for a new install welcome, options (folder, shortcuts), the optional libraries, working, done;
        // for an update or a repair only welcome, working, done.
        private string[] Journey()
        {
            if (existing != null) return new string[] { "welcome", "progress", "done" };
            if (o.Mode == "install" && ExtrasList.Items.Length > 0) return new string[] { "welcome", "options", "extras", "progress", "done" };
            return new string[] { "welcome", "options", "progress", "done" };
        }

        /// <summary>The mark: a rounded square in the accent colour with the prompt ">_" in it, the same as the Android installer.</summary>
        private void DrawMark(Graphics g)
        {
            Rectangle r = new Rectangle(32, 24, 40, 40);
            Draw.Fill(g, r, 10, p.Accent, null);
            using (Font f = new Font("Consolas", 15f, FontStyle.Bold))
                TextRenderer.DrawText(g, ">_", f, r, p.AccentText, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            Graphics g = e.Graphics;
            g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            using (SolidBrush bar = new SolidBrush(p.Accent)) g.FillRectangle(bar, 0, 0, ClientSize.Width, 4);          // a thin accent line along the top
            DrawMark(g);
            string[] journey = Journey();
            int current = page == "failed" ? journey.Length - 2 : page == "uninstall" ? 1 : Array.IndexOf(journey, page);
            if (current < 0) return;
            int x = ClientSize.Width - 34 - (journey.Length - 1) * 18;
            for (int i = 0; i < journey.Length; i++)
            {
                Rectangle dot = new Rectangle(x + i * 18, 40, 10, 10);
                if (i <= current) { using (SolidBrush b = new SolidBrush(page == "failed" && i == current ? p.Bad : p.Accent)) g.FillEllipse(b, dot); }
                else { using (Pen pen = new Pen(p.Muted, 1.5f)) g.DrawEllipse(pen, dot); }
            }
        }

        private void Reset(string name, string heading, string subheading)
        {
            page = name;
            Invalidate();
            foreach (Control c in new List<Control>(body.Controls.Cast())) { body.Controls.Remove(c); c.Dispose(); }
            choices.Clear();
            title.Text = heading;
            sub.Text = subheading;
            secondary.Visible = true;
            tertiary.Visible = false;
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
            pathBox = new ModernInput(p, o.Directory);
            pathBox.SetBounds(0, 26, 480, 38);
            body.Controls.Add(pathBox);
            ModernButton browse = new ModernButton(p, Strings.T("browse"), false); browse.SetBounds(490, 26, 106, 38);
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
            memory = new ModernDropdown(p);
            List<string> memoryNames = new List<string>();
            foreach (int mb in MemoryChoices) memoryNames.Add(mb == 0 ? Strings.T("memory.all") : (mb >= 1024 ? (mb / 1024) + " GB" : mb + " MB"));
            memory.Items = memoryNames.ToArray();
            memory.SelectedIndex = Math.Max(0, Array.IndexOf(MemoryChoices, o.MemoryMb));
            memory.SetBounds(0, 174, 300, 38);
            body.Controls.Add(memory);
            int y = 226;
            if (!Core.HasWebView2())
            {
                Label w = Small(Strings.T("webview")); w.SetBounds(0, y, 596, 22); w.ForeColor = p.Text; body.Controls.Add(w);
                webview = new ModernCheck(p, Strings.T("webview.get"), true); webview.SetBounds(0, y + 26, 596, 28); body.Controls.Add(webview);
            }
            primary.Text = Strings.T(o.Mode == "update" ? "update" : "install");
            secondary.Text = Strings.T("back");
        }

        // The optional libraries: one tick each (all ticked to begin with), so a person can leave out what they do not want.
        private void ShowExtras()
        {
            Reset("extras", Strings.T("extras"), Strings.T("extras.sub"));
            extraChecks.Clear();
            int count = ExtrasList.Items.Length;
            int rows = (count + 1) / 2;
            Label what = new Label();
            what.Text = Strings.T("extras.hover"); what.ForeColor = p.Muted; what.BackColor = p.Bg; what.Font = new Font("Segoe UI", 10f); what.AutoSize = false;
            what.SetBounds(0, rows * 32 + 6, 596, 40);
            for (int i = 0; i < count; i++)
            {
                string name = ExtrasList.Items[i][0];
                string description = ExtrasList.Items[i][1];
                ModernCheck check = new ModernCheck(p, name, true);
                check.SetBounds((i / rows) * 300, (i % rows) * 32, 290, 28);
                EventHandler show = delegate { what.Text = description.Length > 0 ? description : name; what.ForeColor = p.Text; };
                check.MouseEnter += show;
                check.GotFocus += show;
                body.Controls.Add(check);
                extraChecks.Add(check);
            }
            body.Controls.Add(what);
            ModernButton all = new ModernButton(p, Strings.T("extras.all"), false); all.SetBounds(0, rows * 32 + 46, 96, 34);
            all.Click += delegate { foreach (ModernCheck c in extraChecks) { c.Checked = true; c.Invalidate(); } };
            ModernButton none = new ModernButton(p, Strings.T("extras.none"), false); none.SetBounds(104, rows * 32 + 46, 96, 34);
            none.Click += delegate { foreach (ModernCheck c in extraChecks) { c.Checked = false; c.Invalidate(); } };
            body.Controls.Add(all); body.Controls.Add(none);
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
            bar = new ModernProgress(p); bar.SetBounds(0, 7 * 32 + 18, 596, 10); body.Controls.Add(bar);
            detail = Small(""); detail.SetBounds(0, 7 * 32 + 36, 596, 44); detail.AutoEllipsis = true; body.Controls.Add(detail);
            primary.Visible = false;
            secondary.Text = Strings.T("cancel");
            if (o.Preview.Length == 0) Run();
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
            ShowDone(text, null);
        }

        private void ShowDone(string text, Release rel)
        {
            Reset("done", text, Strings.T("done.sub"));
            primary.Visible = true;
            if (o.Mode != "uninstall")
            {
                body.Controls.Add(SummaryCard(rel));
                launch = new ModernCheck(p, Strings.T("launch"), true); launch.SetBounds(0, 96, 596, 28); body.Controls.Add(launch);
                if (rel != null && !string.IsNullOrEmpty(rel.Notes))
                {
                    Control notes = NotesBox(rel);
                    notes.SetBounds(0, 132, 596, 188);
                    body.Controls.Add(notes);
                }
                tertiary.Text = Strings.T("openfolder"); tertiary.Visible = true;
            }
            primary.Text = Strings.T("close");
            secondary.Text = Strings.T("openlog");
        }

        /// <summary>What was installed, in a card: the version, the folder and the shortcuts.</summary>
        private Control SummaryCard(Release rel)
        {
            Panel card = new Panel(); card.SetBounds(0, 4, 596, 80); card.BackColor = p.Surface;
            card.Paint += delegate (object s, PaintEventArgs e) { Draw.Fill(e.Graphics, new Rectangle(0, 0, card.Width - 1, card.Height - 1), 12, p.Surface, p.Border); };
            string version = rel != null ? (!string.IsNullOrEmpty(rel.InstalledVersion) && rel.InstalledVersion != "?" ? rel.InstalledVersion : rel.Version) : "";
            List<string> links = new List<string>();
            if (o.StartMenuShortcut) links.Add(Strings.T("summary.startmenu"));
            if (o.DesktopShortcut) links.Add(Strings.T("summary.desktop"));
            string[][] rows = new string[][]
            {
                new string[] { Strings.T("summary.version"), version },
                new string[] { Strings.T("summary.folder"), Path.GetFullPath(o.Directory) },
                new string[] { Strings.T("summary.shortcuts"), links.Count > 0 ? string.Join(", ", links.ToArray()) : Strings.T("summary.none") }
            };
            for (int i = 0; i < rows.Length; i++)
            {
                Label k = new Label(); k.Text = rows[i][0]; k.ForeColor = p.Muted; k.BackColor = p.Surface; k.Font = new Font("Segoe UI", 9.5f); k.SetBounds(16, 10 + i * 22, 120, 20);
                Label v = new Label(); v.Text = rows[i][1]; v.ForeColor = p.Text; v.BackColor = p.Surface; v.Font = new Font("Segoe UI Semibold", 9.5f); v.AutoEllipsis = true; v.SetBounds(140, 10 + i * 22, 440, 20);
                card.Controls.Add(k); card.Controls.Add(v);
            }
            return card;
        }

        /// <summary>A sentence that helps for the commonest reasons an install fails, found in the error's text; empty when nothing fits.</summary>
        private static string Hint(string error)
        {
            string e = (error ?? "").ToLowerInvariant();
            if (e.Contains("remote name") || e.Contains("unable to connect") || e.Contains("timed out") || e.Contains("timeout") || e.Contains("no such host") || e.Contains("could not be resolved") || e.Contains("internet") || e.Contains("proxy")) return Strings.T("hint.net");
            if (e.Contains("space") || e.Contains("disk full") || e.Contains("not enough")) return Strings.T("hint.disk");
            if (e.Contains("denied") || e.Contains("access to the path") || e.Contains("unauthorized") || e.Contains("not permitted")) return Strings.T("hint.access");
            if (e.Contains("checksum") || e.Contains("sha256") || e.Contains("hash") || e.Contains("verify")) return Strings.T("hint.hash");
            return "";
        }

        private void ShowFailed()
        {
            Reset("failed", Strings.T("failed"), Strings.T("failed.sub"));
            primary.Visible = true;
            Panel card = new Panel(); card.SetBounds(0, 0, 596, 128); card.BackColor = p.Surface;
            card.Paint += delegate (object s, PaintEventArgs e) { Draw.Fill(e.Graphics, new Rectangle(0, 0, card.Width - 1, card.Height - 1), 12, p.Surface, p.Bad); };
            Label msg = new Label(); msg.Text = errorText; msg.ForeColor = p.Bad; msg.BackColor = p.Surface; msg.Font = new Font("Segoe UI Semibold", 10.5f); msg.SetBounds(16, 12, 564, 62);
            card.Controls.Add(msg);
            string hint = Hint(errorText);
            Label help = new Label(); help.Text = hint; help.ForeColor = p.Text; help.BackColor = p.Surface; help.Font = new Font("Segoe UI", 9.5f); help.SetBounds(16, 76, 564, 44);
            card.Controls.Add(help);
            body.Controls.Add(card);
            Label log = Small(Log.Path_); log.SetBounds(0, 140, 596, 40); body.Controls.Add(log);
            primary.Text = Strings.T("retry");
            secondary.Text = Strings.T("openlog");
            tertiary.Text = Strings.T("copydetails"); tertiary.Visible = true;
        }

        /// <summary>The release's "What's new", styled (headings, bullets, bold, code), in a box that scrolls.</summary>
        private Control NotesBox(Release rel)
        {
            RichTextBox box = new RichTextBox();
            box.ReadOnly = true;
            box.BorderStyle = BorderStyle.None;
            box.BackColor = p.Surface;
            box.ForeColor = p.Text;
            box.DetectUrls = false;
            box.TabStop = false;
            box.ScrollBars = RichTextBoxScrollBars.Vertical;
            box.HandleCreated += delegate { if (!p.Light) { try { SetWindowTheme(box.Handle, "DarkMode_Explorer", null); } catch (Exception) { } } };       // dark scroll bars
            box.SetBounds(0, 64, 596, 250);
            try { box.Rtf = Markdown.ToRtf("## " + Strings.T("whatsnew", rel.Version) + "\n\n" + rel.Notes, p.Text, p.Accent); }
            catch (Exception ex) { Log.Write("could not show the notes: " + ex.Message); box.Text = rel.Notes; }
            return box;
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
                if (o.Mode == "install" && ExtrasList.Items.Length > 0) ShowExtras(); else ShowProgress();
            }
            else if (page == "extras")
            {
                List<string> picked = new List<string>();
                for (int i = 0; i < extraChecks.Count; i++) if (extraChecks[i].Checked) picked.Add(ExtrasList.Items[i][0]);
                o.Extras = picked.Count == ExtrasList.Items.Length ? "all" : picked.Count == 0 ? "none" : string.Join(",", picked.ToArray());
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

        private void OnTertiary()
        {
            if (page == "done")
            {
                try { Process.Start("explorer.exe", "\"" + Path.GetFullPath(o.Directory) + "\""); } catch (Exception) { }
            }
            else if (page == "failed")
            {
                try
                {
                    Clipboard.SetText("PythonOS Setup failed\r\n" + errorText + "\r\n\r\nLog: " + Log.Path_);
                    tertiary.Text = Strings.T("copied");
                }
                catch (Exception) { }
            }
        }

        private void OnKey(object sender, KeyEventArgs e)
        {
            if (working) return;
            if (e.KeyCode == Keys.Enter && !(ActiveControl is TextBox) && !(ActiveControl is ModernButton) && primary.Visible && primary.Enabled)
            {
                e.Handled = true; e.SuppressKeyPress = true; OnPrimary();
            }
            else if (e.KeyCode == Keys.Escape && secondary.Visible && (page == "welcome" || page == "options" || page == "extras" || page == "uninstall"))
            {
                e.Handled = true; e.SuppressKeyPress = true; OnSecondary();
            }
        }

        private void OnSecondary()
        {
            if (page == "welcome" || page == "uninstall") { Close(); }
            else if (page == "options") ShowWelcome();
            else if (page == "extras") ShowOptions();
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
                    BeginInvoke((MethodInvoker)delegate { working = false; steps.AllDone(); bar.Value = 1; ShowDone(DoneText(rel), rel); });
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
            if (o.Mode == "update")
            {
                string got = rel.InstalledVersion;
                if (got != null && got != "?" && got != rel.Version) return Strings.T("done.partial", got, rel.Version);
                return Strings.T("done.update", rel.Version);
            }
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
