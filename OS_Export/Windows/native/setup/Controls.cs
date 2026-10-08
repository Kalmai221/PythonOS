// The installer's own controls: flat, rounded, light/dark. Drawn by hand with GDI+ so they look the same on every Windows 10/11 machine.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;
using Microsoft.Win32;

namespace PythonOS.Setup
{
    internal sealed class Palette
    {
        public bool Light;
        public Color Bg, Surface, Text, Muted, Accent, AccentText, Border, Ok, Bad, Track;

        /// <summary>"light" or "dark" forces a theme (/theme=dark); anything else follows Windows.</summary>
        public static string Forced = "";

        public static Palette FromSystem()
        {
            bool light = true;
            try
            {
                object v = Registry.GetValue(@"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme", 1);
                light = !(v is int) || (int)v != 0;
            }
            catch (Exception) { }
            if (Forced == "light") light = true; else if (Forced == "dark") light = false;
            Palette p = Make(light);
            try
            {
                // the accent colour the person chose in Windows (stored as 0xAABBGGRR); used when it reads well on this background
                object a = Registry.GetValue(@"HKEY_CURRENT_USER\Software\Microsoft\Windows\DWM", "AccentColor", null);
                if (a is int)
                {
                    int v = (int)a;
                    Color chosen = Color.FromArgb(v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF);
                    Color tuned = Tune(chosen, light);
                    if (tuned != Color.Empty) { p.Accent = tuned; }
                }
            }
            catch (Exception) { }
            return p;
        }

        private static double Luma(Color c) { return (0.2126 * c.R + 0.7152 * c.G + 0.0722 * c.B) / 255.0; }

        /// <summary>The accent made readable: not too dark on the dark theme, not too pale on the light one; very grey colours are left out.</summary>
        private static Color Tune(Color c, bool light)
        {
            int max = Math.Max(c.R, Math.Max(c.G, c.B)), min = Math.Min(c.R, Math.Min(c.G, c.B));
            if (max - min < 40) return Color.Empty;
            for (int i = 0; i < 12; i++)
            {
                double l = Luma(c);
                if (light && l > 0.42) c = Color.FromArgb((int)(c.R * 0.88), (int)(c.G * 0.88), (int)(c.B * 0.88));
                else if (!light && l < 0.50) c = Color.FromArgb(Math.Min(255, (int)(c.R + (255 - c.R) * 0.18)), Math.Min(255, (int)(c.G + (255 - c.G) * 0.18)), Math.Min(255, (int)(c.B + (255 - c.B) * 0.18)));
                else break;
            }
            return c;
        }

        public static Palette Make(bool light)
        {
            Palette p = new Palette();
            p.Light = light;
            if (light)
            {
                p.Bg = Color.FromArgb(246, 247, 251); p.Surface = Color.White; p.Text = Color.FromArgb(22, 27, 36);
                p.Muted = Color.FromArgb(88, 97, 116); p.Accent = Color.FromArgb(47, 91, 216); p.Border = Color.FromArgb(218, 222, 232);
                p.Ok = Color.FromArgb(23, 120, 61); p.Bad = Color.FromArgb(198, 40, 40); p.Track = Color.FromArgb(228, 232, 241);
            }
            else
            {
                p.Bg = Color.FromArgb(14, 17, 23); p.Surface = Color.FromArgb(22, 27, 36); p.Text = Color.FromArgb(230, 233, 239);
                p.Muted = Color.FromArgb(154, 164, 181); p.Accent = Color.FromArgb(122, 162, 247); p.Border = Color.FromArgb(38, 45, 58);
                p.Ok = Color.FromArgb(126, 224, 161); p.Bad = Color.FromArgb(255, 123, 114); p.Track = Color.FromArgb(38, 45, 58);
            }
            p.AccentText = light ? Color.White : Color.FromArgb(14, 17, 23);
            return p;
        }
    }

    internal static class Draw
    {
        public static GraphicsPath Round(Rectangle r, int radius)
        {
            GraphicsPath path = new GraphicsPath();
            int d = radius * 2;
            if (d > r.Height) d = r.Height;
            if (d > r.Width) d = r.Width;
            if (d <= 0) { path.AddRectangle(r); return path; }
            path.AddArc(r.X, r.Y, d, d, 180, 90);
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }

        public static void Fill(Graphics g, Rectangle r, int radius, Color fill, Color? border)
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using (GraphicsPath path = Round(r, radius))
            {
                using (SolidBrush b = new SolidBrush(fill)) g.FillPath(b, path);
                if (border.HasValue) using (Pen pen = new Pen(border.Value)) g.DrawPath(pen, path);
            }
        }

        public static void Text(Graphics g, string text, Font font, Rectangle r, Color color, TextFormatFlags flags)
        {
            TextRenderer.DrawText(g, text, font, r, color, flags | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis);
        }
    }

    /// <summary>A rounded button. Primary buttons are filled with the accent colour; others have an outline.</summary>
    internal class ModernButton : Control
    {
        private readonly Palette p;
        private bool hover, down;
        public bool Primary;
        public bool Toggled;       // used by the language chips
        public ModernButton(Palette palette, string text, bool primary)
        {
            p = palette; Text = text; Primary = primary;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.Selectable | ControlStyles.ResizeRedraw, true);
            Font = new Font("Segoe UI Semibold", 10f);
            Cursor = Cursors.Hand;
            Size = new Size(110, 38);
            TabStop = true;
        }
        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; down = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnMouseDown(MouseEventArgs e) { down = true; Focus(); Invalidate(); base.OnMouseDown(e); }
        protected override void OnMouseUp(MouseEventArgs e) { down = false; Invalidate(); base.OnMouseUp(e); }
        protected override bool IsInputKey(Keys k) { return k == Keys.Enter || k == Keys.Space || base.IsInputKey(k); }
        protected override void OnKeyDown(KeyEventArgs e) { if (e.KeyCode == Keys.Enter || e.KeyCode == Keys.Space) { OnClick(EventArgs.Empty); e.Handled = true; } base.OnKeyDown(e); }
        protected override void OnEnabledChanged(EventArgs e) { Invalidate(); base.OnEnabledChanged(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.Clear(Parent != null ? Parent.BackColor : p.Bg);
            Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);
            Color fill, border, text;
            if (Primary || Toggled)
            {
                fill = down ? Shade(p.Accent, -0.15f) : hover ? Shade(p.Accent, 0.08f) : p.Accent;
                border = fill; text = p.AccentText;
            }
            else
            {
                fill = hover ? (p.Light ? Color.FromArgb(238, 241, 248) : Color.FromArgb(30, 37, 50)) : p.Surface;
                border = p.Border; text = p.Text;
            }
            if (!Enabled) { fill = p.Track; border = p.Track; text = p.Muted; }
            Draw.Fill(e.Graphics, r, 10, fill, border);
            if (Focused && Enabled) using (Pen pen = new Pen(Color.FromArgb(120, p.Accent), 2f)) { e.Graphics.SmoothingMode = SmoothingMode.AntiAlias; using (GraphicsPath gp = Draw.Round(new Rectangle(2, 2, Width - 5, Height - 5), 8)) e.Graphics.DrawPath(pen, gp); }
            Draw.Text(e.Graphics, Text, Font, ClientRectangle, text, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
        }
        private static Color Shade(Color c, float amount)
        {
            int r = c.R + (int)((amount > 0 ? 255 - c.R : c.R) * amount);
            int g = c.G + (int)((amount > 0 ? 255 - c.G : c.G) * amount);
            int b = c.B + (int)((amount > 0 ? 255 - c.B : c.B) * amount);
            return Color.FromArgb(Math.Max(0, Math.Min(255, r)), Math.Max(0, Math.Min(255, g)), Math.Max(0, Math.Min(255, b)));
        }
    }

    /// <summary>A rounded progress bar.</summary>
    internal sealed class ModernProgress : Control
    {
        private readonly Palette p;
        private double value;
        public ModernProgress(Palette palette)
        {
            p = palette;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
            Height = 10;
        }
        public double Value { get { return value; } set { this.value = Math.Max(0, Math.Min(1, value)); Invalidate(); } }
        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.Clear(Parent != null ? Parent.BackColor : p.Bg);
            Rectangle track = new Rectangle(0, 0, Width - 1, Height - 1);
            Draw.Fill(e.Graphics, track, Height / 2, p.Track, null);
            int w = (int)(track.Width * value);
            if (w > Height / 2) Draw.Fill(e.Graphics, new Rectangle(0, 0, w, Height - 1), Height / 2, p.Accent, null);
        }
    }

    /// <summary>A checkbox with a rounded box.</summary>
    internal sealed class ModernCheck : Control
    {
        private readonly Palette p;
        public bool Checked;
        public event EventHandler Changed;
        public ModernCheck(Palette palette, string text, bool isChecked)
        {
            p = palette; Text = text; Checked = isChecked;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.Selectable, true);
            Font = new Font("Segoe UI", 10f); Cursor = Cursors.Hand; Height = 28; TabStop = true;
        }
        protected override bool IsInputKey(Keys k) { return k == Keys.Space || base.IsInputKey(k); }
        protected override void OnKeyDown(KeyEventArgs e) { if (e.KeyCode == Keys.Space) { Toggle(); e.Handled = true; } base.OnKeyDown(e); }
        protected override void OnClick(EventArgs e) { Focus(); Toggle(); base.OnClick(e); }
        private void Toggle() { Checked = !Checked; Invalidate(); if (Changed != null) Changed(this, EventArgs.Empty); }
        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.Clear(Parent != null ? Parent.BackColor : p.Bg);
            Rectangle box = new Rectangle(1, (Height - 20) / 2, 20, 20);
            Draw.Fill(e.Graphics, box, 6, Checked ? p.Accent : p.Surface, Checked ? p.Accent : p.Border);
            if (Checked)
            {
                e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
                using (Pen pen = new Pen(p.AccentText, 2.2f) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round })
                    e.Graphics.DrawLines(pen, new Point[] { new Point(box.X + 5, box.Y + 10), new Point(box.X + 9, box.Y + 14), new Point(box.X + 15, box.Y + 6) });
            }
            Draw.Text(e.Graphics, Text, Font, new Rectangle(30, 0, Width - 30, Height), p.Text, TextFormatFlags.VerticalCenter);
        }
    }

    /// <summary>A choice among several (a round marker and a label). Rows with the same group list act as one set.</summary>
    internal sealed class ModernRadio : Control
    {
        private readonly Palette p;
        private readonly List<ModernRadio> group;
        public bool Selected;
        public string Key;
        public ModernRadio(Palette palette, List<ModernRadio> group, string key, string text)
        {
            p = palette; this.group = group; Key = key; Text = text; group.Add(this);
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.Selectable, true);
            Font = new Font("Segoe UI", 10.5f); Cursor = Cursors.Hand; Height = 40; TabStop = true;
        }
        public void Choose() { foreach (ModernRadio r in group) { r.Selected = r == this; r.Invalidate(); } }
        protected override bool IsInputKey(Keys k) { return k == Keys.Space || base.IsInputKey(k); }
        protected override void OnKeyDown(KeyEventArgs e) { if (e.KeyCode == Keys.Space) { Choose(); e.Handled = true; } base.OnKeyDown(e); }
        protected override void OnClick(EventArgs e) { Focus(); Choose(); base.OnClick(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.Clear(Parent != null ? Parent.BackColor : p.Bg);
            Rectangle card = new Rectangle(0, 0, Width - 1, Height - 1);
            Draw.Fill(e.Graphics, card, 10, p.Surface, Selected ? p.Accent : p.Border);
            Rectangle dot = new Rectangle(14, (Height - 18) / 2, 18, 18);
            Draw.Fill(e.Graphics, dot, 9, p.Surface, Selected ? p.Accent : p.Muted);
            if (Selected) Draw.Fill(e.Graphics, new Rectangle(dot.X + 4, dot.Y + 4, 10, 10), 5, p.Accent, null);
            Draw.Text(e.Graphics, Text, Font, new Rectangle(44, 0, Width - 54, Height), p.Text, TextFormatFlags.VerticalCenter);
        }
    }

    /// <summary>The list of steps with a marker for done, current and waiting.</summary>

    /// <summary>A text box that looks like the rest: a rounded field with a thin border that turns to the accent colour while you type, and a borderless
    /// text box inside it. Text, SelectAll and the Changed event are passed through.</summary>
    internal sealed class ModernInput : Control
    {
        private readonly Palette p;
        private readonly TextBox box = new TextBox();
        public event EventHandler TextChangedInside;
        public ModernInput(Palette palette, string text)
        {
            p = palette;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
            Height = 38;
            box.BorderStyle = BorderStyle.None;
            box.BackColor = p.Surface;
            box.ForeColor = p.Text;
            box.Font = new Font("Segoe UI", 10.5f);
            box.Text = text;
            box.GotFocus += delegate { Invalidate(); };
            box.LostFocus += delegate { Invalidate(); };
            box.TextChanged += delegate { if (TextChangedInside != null) TextChangedInside(this, EventArgs.Empty); };
            Controls.Add(box);
            box.SelectionStart = box.TextLength; box.SelectionLength = 0;
        }
        public override string Text { get { return box.Text; } set { box.Text = value; } }
        protected override void OnLayout(LayoutEventArgs e)
        {
            base.OnLayout(e);
            box.SetBounds(12, (Height - box.PreferredHeight) / 2, Math.Max(10, Width - 24), box.PreferredHeight);
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.Clear(Parent != null ? Parent.BackColor : p.Bg);
            Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);
            bool focus = box.Focused;
            Draw.Fill(e.Graphics, r, 10, p.Surface, focus ? p.Accent : p.Border);
            if (focus) using (Pen pen = new Pen(Color.FromArgb(70, p.Accent), 3f)) { e.Graphics.SmoothingMode = SmoothingMode.AntiAlias; using (GraphicsPath gp = Draw.Round(new Rectangle(-1, -1, Width + 1, Height + 1), 11)) e.Graphics.DrawPath(pen, gp); }
        }
        protected override void OnClick(EventArgs e) { box.Focus(); base.OnClick(e); }
    }

    /// <summary>A drop-down list in the installer's own style: a rounded field with a chevron, and a list that opens under it (also with the keyboard:
    /// Space or Enter opens it, the arrow keys change the choice).</summary>
    internal sealed class ModernDropdown : Control
    {
        private readonly Palette p;
        private bool hover, open;
        private DropdownPopup popup;
        public string[] Items = new string[0];
        public int SelectedIndex;
        public event EventHandler Changed;
        public ModernDropdown(Palette palette)
        {
            p = palette;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.Selectable | ControlStyles.ResizeRedraw, true);
            Font = new Font("Segoe UI", 10.5f);
            Cursor = Cursors.Hand;
            Height = 38; TabStop = true;
        }
        public string SelectedText { get { return SelectedIndex >= 0 && SelectedIndex < Items.Length ? Items[SelectedIndex] : ""; } }
        public void Choose(int index)
        {
            if (index < 0 || index >= Items.Length || index == SelectedIndex) return;
            SelectedIndex = index; Invalidate();
            if (Changed != null) Changed(this, EventArgs.Empty);
        }
        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnClick(EventArgs e) { Focus(); Toggle(); base.OnClick(e); }
        protected override bool IsInputKey(Keys k) { return k == Keys.Up || k == Keys.Down || k == Keys.Enter || k == Keys.Space || base.IsInputKey(k); }
        protected override void OnKeyDown(KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Space || e.KeyCode == Keys.Enter) { Toggle(); e.Handled = true; }
            else if (e.KeyCode == Keys.Down) { Choose(SelectedIndex + 1); e.Handled = true; }
            else if (e.KeyCode == Keys.Up) { Choose(SelectedIndex - 1); e.Handled = true; }
            base.OnKeyDown(e);
        }
        protected override void OnLostFocus(EventArgs e) { Invalidate(); base.OnLostFocus(e); }
        protected override void OnGotFocus(EventArgs e) { Invalidate(); base.OnGotFocus(e); }
        private void Toggle()
        {
            if (open && popup != null) { popup.Close(); return; }
            if (Items.Length == 0) return;
            open = true; Invalidate();
            popup = new DropdownPopup(p, Items, SelectedIndex, Font, Width);
            Point at = PointToScreen(new Point(0, Height + 4));
            popup.Location = at;
            popup.Picked += delegate (int index) { Choose(index); };
            popup.FormClosed += delegate { open = false; popup = null; Invalidate(); };
            popup.Show(FindForm());
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.Clear(Parent != null ? Parent.BackColor : p.Bg);
            Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);
            Color fill = hover || open ? (p.Light ? Color.FromArgb(244, 246, 251) : Color.FromArgb(28, 34, 46)) : p.Surface;
            Draw.Fill(e.Graphics, r, 10, fill, open || Focused ? p.Accent : p.Border);
            if (Focused && !open) using (Pen pen = new Pen(Color.FromArgb(70, p.Accent), 3f)) { e.Graphics.SmoothingMode = SmoothingMode.AntiAlias; using (GraphicsPath gp = Draw.Round(new Rectangle(-1, -1, Width + 1, Height + 1), 11)) e.Graphics.DrawPath(pen, gp); }
            Draw.Text(e.Graphics, SelectedText, Font, new Rectangle(14, 0, Width - 48, Height), p.Text, TextFormatFlags.VerticalCenter);
            // the chevron
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            int cx = Width - 24, cy = Height / 2;
            using (Pen pen = new Pen(p.Muted, 2f) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round })
                e.Graphics.DrawLines(pen, open
                    ? new Point[] { new Point(cx - 5, cy + 2), new Point(cx, cy - 3), new Point(cx + 5, cy + 2) }
                    : new Point[] { new Point(cx - 5, cy - 2), new Point(cx, cy + 3), new Point(cx + 5, cy - 2) });
        }
    }

    /// <summary>The list that opens under a ModernDropdown: rounded, one row per choice, the current one ticked, the one under the mouse or the arrow keys lit.</summary>
    internal sealed class DropdownPopup : Form
    {
        private readonly Palette p;
        private readonly string[] items;
        private int selected, hot;
        private const int Row = 36;
        public delegate void PickHandler(int index);
        public event PickHandler Picked;
        public DropdownPopup(Palette palette, string[] choices, int current, Font font, int width)
        {
            p = palette; items = choices; selected = current; hot = current;
            FormBorderStyle = FormBorderStyle.None; ShowInTaskbar = false; StartPosition = FormStartPosition.Manual; KeyPreview = true;
            BackColor = p.Surface; Font = font; DoubleBuffered = true;
            ClientSize = new Size(width, items.Length * Row + 12);
            Region = new Region(Draw.Round(new Rectangle(0, 0, Width, Height), 12));
            Deactivate += delegate { Close(); };
        }
        protected override bool ShowWithoutActivation { get { return false; } }
        protected override void OnMouseMove(MouseEventArgs e) { int i = Math.Min(items.Length - 1, Math.Max(0, (e.Y - 6) / Row)); if (i != hot) { hot = i; Invalidate(); } base.OnMouseMove(e); }
        protected override void OnMouseUp(MouseEventArgs e)
        {
            int i = (e.Y - 6) / Row;
            if (e.Y >= 6 && i >= 0 && i < items.Length) { if (Picked != null) Picked(i); Close(); }
            base.OnMouseUp(e);
        }
        protected override void OnKeyDown(KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Escape) Close();
            else if (e.KeyCode == Keys.Down) { hot = Math.Min(items.Length - 1, hot + 1); Invalidate(); }
            else if (e.KeyCode == Keys.Up) { hot = Math.Max(0, hot - 1); Invalidate(); }
            else if (e.KeyCode == Keys.Enter || e.KeyCode == Keys.Space) { if (Picked != null) Picked(hot); Close(); }
            base.OnKeyDown(e);
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.Clear(p.Surface);
            g.SmoothingMode = SmoothingMode.AntiAlias;
            Draw.Fill(g, new Rectangle(0, 0, Width - 1, Height - 1), 12, p.Surface, p.Border);
            for (int i = 0; i < items.Length; i++)
            {
                Rectangle row = new Rectangle(6, 6 + i * Row, Width - 13, Row - 2);
                if (i == hot) Draw.Fill(g, row, 8, p.Light ? Color.FromArgb(232, 238, 252) : Color.FromArgb(34, 42, 58), null);
                Draw.Text(g, items[i], Font, new Rectangle(row.X + 12, row.Y, row.Width - 44, row.Height), p.Text, TextFormatFlags.VerticalCenter);
                if (i == selected)
                    using (Pen pen = new Pen(p.Accent, 2f) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round })
                        g.DrawLines(pen, new Point[] { new Point(row.Right - 28, row.Y + Row / 2 - 1), new Point(row.Right - 22, row.Y + Row / 2 + 5), new Point(row.Right - 12, row.Y + Row / 2 - 6) });
            }
        }
    }

    internal sealed class StepList : Control
    {
        private readonly Palette p;
        private readonly List<string> keys = new List<string>();
        private readonly List<string> names = new List<string>();
        private int current = -1;
        private bool failed;
        private int angle;
        private readonly Timer spin = new Timer();
        public StepList(Palette palette)
        {
            p = palette;
            spin.Interval = 40;
            spin.Tick += delegate { angle = (angle + 14) % 360; if (current >= 0 && current < keys.Count && !failed) Invalidate(); };
            spin.Start();
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
            Font = new Font("Segoe UI", 10.5f);
        }
        public void Set(string[] stepKeys, string[] stepNames) { keys.Clear(); names.Clear(); keys.AddRange(stepKeys); names.AddRange(stepNames); current = -1; failed = false; Invalidate(); }
        public void Current(string key) { int i = keys.IndexOf(key); if (i >= 0) { current = i; Invalidate(); } }
        public void Fail() { failed = true; Invalidate(); }
        public void AllDone() { current = keys.Count; Invalidate(); }
        protected override void Dispose(bool disposing) { if (disposing) spin.Dispose(); base.Dispose(disposing); }
        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.Clear(Parent != null ? Parent.BackColor : p.Bg);
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            int rowHeight = 32;
            for (int i = 0; i < names.Count; i++)
            {
                int y = i * rowHeight;
                Rectangle marker = new Rectangle(2, y + 6, 20, 20);
                bool done = i < current;
                bool now = i == current;
                Color color = done ? p.Ok : (now ? (failed ? p.Bad : p.Accent) : p.Muted);
                if (done)
                {
                    Draw.Fill(e.Graphics, marker, 10, color, null);
                    using (Pen pen = new Pen(p.AccentText, 2f) { StartCap = LineCap.Round, EndCap = LineCap.Round })
                        e.Graphics.DrawLines(pen, new Point[] { new Point(marker.X + 5, marker.Y + 10), new Point(marker.X + 9, marker.Y + 14), new Point(marker.X + 15, marker.Y + 6) });
                }
                else if (now)
                {
                    Draw.Fill(e.Graphics, marker, 10, p.Surface, failed ? color : p.Border);
                    if (failed) Draw.Fill(e.Graphics, new Rectangle(marker.X + 5, marker.Y + 5, 10, 10), 5, color, null);
                    else using (Pen arc = new Pen(color, 2.4f) { StartCap = LineCap.Round, EndCap = LineCap.Round })      // a turning arc: it is working
                        e.Graphics.DrawArc(arc, new Rectangle(marker.X + 1, marker.Y + 1, 18, 18), angle, 110);
                }
                else Draw.Fill(e.Graphics, marker, 10, p.Surface, p.Border);
                Draw.Text(e.Graphics, names[i], Font, new Rectangle(34, y, Width - 34, rowHeight), done || now ? p.Text : p.Muted, TextFormatFlags.VerticalCenter);
            }
        }
    }
}
