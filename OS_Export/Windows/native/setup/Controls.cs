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

        public static Palette FromSystem()
        {
            bool light = true;
            try
            {
                object v = Registry.GetValue(@"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme", 1);
                light = !(v is int) || (int)v != 0;
            }
            catch (Exception) { }
            return light ? Make(true) : Make(false);
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
    internal sealed class StepList : Control
    {
        private readonly Palette p;
        private readonly List<string> keys = new List<string>();
        private readonly List<string> names = new List<string>();
        private int current = -1;
        private bool failed;
        public StepList(Palette palette)
        {
            p = palette;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
            Font = new Font("Segoe UI", 10.5f);
        }
        public void Set(string[] stepKeys, string[] stepNames) { keys.Clear(); names.Clear(); keys.AddRange(stepKeys); names.AddRange(stepNames); current = -1; failed = false; Invalidate(); }
        public void Current(string key) { int i = keys.IndexOf(key); if (i >= 0) { current = i; Invalidate(); } }
        public void Fail() { failed = true; Invalidate(); }
        public void AllDone() { current = keys.Count; Invalidate(); }
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
                else if (now) { Draw.Fill(e.Graphics, marker, 10, p.Surface, color); Draw.Fill(e.Graphics, new Rectangle(marker.X + 5, marker.Y + 5, 10, 10), 5, color, null); }
                else Draw.Fill(e.Graphics, marker, 10, p.Surface, p.Border);
                Draw.Text(e.Graphics, names[i], Font, new Rectangle(34, y, Width - 34, rowHeight), done || now ? p.Text : p.Muted, TextFormatFlags.VerticalCenter);
            }
        }
    }
}
