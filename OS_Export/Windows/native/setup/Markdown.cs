// Turns the Markdown of a release's "What's new" into RTF for a RichTextBox: headings, bullets, numbered lists, **bold**, `code`, quotes,
// code blocks and rules. Links show their text only. Anything it does not know is shown as written, so unusual text never disappears.
// (C# 5, like the rest of the installer: it is built with the compiler that ships with Windows.)
using System;
using System.Drawing;
using System.Text;
using System.Text.RegularExpressions;

namespace PythonOS.Setup
{
    internal static class Markdown
    {
        private static readonly Regex Heading = new Regex(@"^(#{1,6})\s+(.*)$");
        private static readonly Regex Bullet = new Regex(@"^[-*+]\s+(.*)$");
        private static readonly Regex Numbered = new Regex(@"^(\d+)[.)]\s+(.*)$");
        private static readonly Regex Quote = new Regex(@"^>\s?(.*)$");
        private static readonly Regex Rule = new Regex(@"^(-{3,}|\*{3,}|_{3,})$");
        private static readonly Regex Link = new Regex(@"\[([^\]]+)\]\([^)]*\)");

        private static string ColorEntry(Color c)
        {
            return @"\red" + c.R + @"\green" + c.G + @"\blue" + c.B + ";";
        }

        private static string Escape(char c)
        {
            if (c == '\\') return @"\\";
            if (c == '{') return @"\{";
            if (c == '}') return @"\}";
            if (c > 126) return @"\u" + ((short)c).ToString() + "?";
            return c.ToString();
        }

        private static string EscapeAll(string text)
        {
            StringBuilder o = new StringBuilder();
            foreach (char c in text) o.Append(Escape(c));
            return o.ToString();
        }

        /// <summary>One line of text with **bold** and `code` applied.</summary>
        private static string Inline(string text)
        {
            text = Link.Replace(text, "$1");
            StringBuilder o = new StringBuilder();
            bool bold = false;
            bool code = false;
            for (int i = 0; i < text.Length; i++)
            {
                char c = text[i];
                if (!code && c == '*' && i + 1 < text.Length && text[i + 1] == '*')
                {
                    bold = !bold;
                    o.Append(bold ? @"\b " : @"\b0 ");
                    i++;
                    continue;
                }
                if (c == '`')
                {
                    code = !code;
                    o.Append(code ? @"{\f1\fs18\cf2 " : "}");
                    continue;
                }
                o.Append(Escape(c));
            }
            if (code) o.Append("}");
            if (bold) o.Append(@"\b0 ");
            return o.ToString();
        }

        /// <summary>The RTF for [source]. [text] is the colour of the words, [code] the colour of `code`.</summary>
        public static string ToRtf(string source, Color text, Color code)
        {
            StringBuilder rtf = new StringBuilder();
            rtf.Append(@"{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0\fnil\fcharset0 Segoe UI;}{\f1\fnil\fcharset0 Consolas;}}");
            rtf.Append(@"{\colortbl ;" + ColorEntry(text) + ColorEntry(code) + "}");
            rtf.Append(@"\viewkind4\uc1 ");
            bool fence = false;
            foreach (string raw in (source ?? "").Replace("\r\n", "\n").Split('\n'))
            {
                string line = raw.TrimEnd();
                string trimmed = line.TrimStart();
                if (trimmed.StartsWith("```"))
                {
                    fence = !fence;
                    continue;
                }
                if (fence)
                {
                    rtf.Append(@"\pard\li240\sa0\f1\fs18\cf2 " + EscapeAll(line) + @"\par");
                    continue;
                }
                if (trimmed.Length == 0)
                {
                    rtf.Append(@"\pard\sa0\f0\fs12\cf1 \par");
                    continue;
                }
                int indent = (line.Length - trimmed.Length) / 2 * 360;
                Match heading = Heading.Match(trimmed);
                Match bullet = Bullet.Match(trimmed);
                Match numbered = Numbered.Match(trimmed);
                Match quote = Quote.Match(trimmed);
                if (heading.Success)
                {
                    int level = heading.Groups[1].Value.Length;
                    int size = level == 1 ? 32 : level == 2 ? 28 : level == 3 ? 23 : 20;
                    rtf.Append(@"\pard\sb120\sa60\f0\fs" + size + @"\cf1\b " + Inline(heading.Groups[2].Value) + @"\b0\par");
                }
                else if (bullet.Success)
                {
                    rtf.Append(@"\pard\tx" + (indent + 300) + @"\li" + (indent + 300) + @"\fi-300\sa40\f0\fs20\cf1 \bullet\tab " + Inline(bullet.Groups[1].Value) + @"\par");
                }
                else if (numbered.Success)
                {
                    rtf.Append(@"\pard\tx" + (indent + 340) + @"\li" + (indent + 340) + @"\fi-340\sa40\f0\fs20\cf1 " + numbered.Groups[1].Value + @".\tab " + Inline(numbered.Groups[2].Value) + @"\par");
                }
                else if (quote.Success)
                {
                    rtf.Append(@"\pard\li240\sa40\f0\fs20\cf1\i " + Inline(quote.Groups[1].Value) + @"\i0\par");
                }
                else if (Rule.IsMatch(trimmed))
                {
                    rtf.Append(@"\pard\sa40\f0\fs20\cf1 " + new StringBuilder().Insert(0, ((char)92) + "u9472?", 24).ToString() + @"\par");
                }
                else
                {
                    rtf.Append(@"\pard\sa60\f0\fs20\cf1 " + Inline(trimmed) + @"\par");
                }
            }
            rtf.Append("}");
            return rtf.ToString();
        }

        /// <summary>The text of a release under its "What's new" heading (up to 80 lines), still Markdown.</summary>
        public static string WhatsNew(string body)
        {
            if (string.IsNullOrEmpty(body)) return "";
            string[] lines = body.Replace("\r\n", "\n").Split('\n');
            int start = -1;
            for (int i = 0; i < lines.Length; i++)
            {
                string t = lines[i].Trim();
                if (t.StartsWith("## ") && t.IndexOf("What", StringComparison.OrdinalIgnoreCase) >= 0) { start = i; break; }
            }
            StringBuilder o = new StringBuilder();
            int count = 0;
            for (int i = start + 1; i < lines.Length; i++)
            {
                string line = lines[i].TrimEnd();
                if (start >= 0 && line.Trim().StartsWith("## ")) break;
                o.Append(line).Append('\n');
                if (++count >= 80) break;
            }
            return o.ToString().Trim();
        }
    }
}
