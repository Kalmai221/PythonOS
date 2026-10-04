package com.pythonos.app

import android.graphics.Color
import android.graphics.Typeface
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.BackgroundColorSpan
import android.text.style.ForegroundColorSpan
import android.text.style.StyleSpan
import android.text.style.UnderlineSpan

/**
 * A small terminal emulator: turns the text PythonOS prints (including the ANSI colour and
 * cursor codes used by rich and yaspin) into styled text. It keeps scrollback lines and a cursor,
 * which is enough for colours, carriage-return spinners, "clear" and in-place progress bars.
 */
class AnsiScreen(private val maxLines: Int = 3000) {

    private class Cell(
        var ch: Char,
        val fg: Int,
        val bg: Int,
        val bold: Boolean,
        val italic: Boolean,
        val underline: Boolean,
        val reverse: Boolean,
    )

    private data class Style(
        val fg: Int, val bg: Int, val bold: Boolean, val italic: Boolean,
        val underline: Boolean, val reverse: Boolean,
    )

    private val lines = ArrayList<ArrayList<Cell>>()
    private var row = 0
    private var col = 0

    // current drawing style (0 = terminal default colour)
    private var fg = DEFAULT
    private var bg = DEFAULT
    private var bold = false
    private var italic = false
    private var underline = false
    private var reverse = false

    private enum class Mode { NORMAL, ESC, CSI, OSC, OSC_ESC, SKIP_ONE }
    private var mode = Mode.NORMAL
    private val params = StringBuilder()

    init { clear() }

    fun clear() {
        lines.clear()
        lines.add(ArrayList())
        row = 0
        col = 0
        resetStyle()
        mode = Mode.NORMAL
    }

    fun feed(text: String) {
        for (ch in text) {
            when (mode) {
                Mode.NORMAL -> normal(ch)
                Mode.ESC -> when (ch) {
                    '[' -> { mode = Mode.CSI; params.setLength(0) }
                    ']' -> mode = Mode.OSC
                    '(', ')' -> mode = Mode.SKIP_ONE
                    else -> mode = Mode.NORMAL
                }
                Mode.SKIP_ONE -> mode = Mode.NORMAL
                Mode.CSI -> if (ch in '0'..'9' || ch == ';' || ch == '?' || ch == '>' || ch == '!' || ch == ' ') {
                    params.append(ch)
                } else {
                    csi(ch, params.toString())
                    mode = Mode.NORMAL
                }
                Mode.OSC -> when (ch) {
                    '\u0007' -> mode = Mode.NORMAL
                    '\u001b' -> mode = Mode.OSC_ESC
                }
                Mode.OSC_ESC -> mode = Mode.NORMAL
            }
        }
    }

    private fun normal(ch: Char) {
        when (ch) {
            '\u001b' -> mode = Mode.ESC
            '\n' -> newline()
            '\r' -> col = 0
            '\b' -> if (col > 0) col--
            '\t' -> { val next = (col / 8 + 1) * 8; while (col < next) put(' ') }
            else -> if (ch >= ' ') put(ch)
        }
    }

    private fun put(ch: Char) {
        val line = lines[row]
        while (line.size < col) line.add(blank())
        val cell = Cell(ch, fg, bg, bold, italic, underline, reverse)
        if (col < line.size) line[col] = cell else line.add(cell)
        col++
    }

    private fun blank() = Cell(' ', DEFAULT, DEFAULT, false, false, false, false)

    private fun newline() {
        row++
        col = 0
        while (row >= lines.size) lines.add(ArrayList())
        if (lines.size > maxLines) {
            val drop = lines.size - maxLines
            repeat(drop) { lines.removeAt(0) }
            row -= drop
        }
    }

    private fun csi(final: Char, raw: String) {
        val nums = raw.trimStart('?', '>', '!').trim().split(';').map { it.trim().toIntOrNull() }
        val n = nums.getOrNull(0)
        when (final) {
            'm' -> sgr(nums)
            'K' -> eraseInLine(n ?: 0)
            'J' -> if (n == 2 || n == 3) clear() else if (n == null || n == 0) eraseBelow()
            'A' -> row = maxOf(0, row - (n ?: 1))
            'B' -> { row += (n ?: 1); while (row >= lines.size) lines.add(ArrayList()) }
            'C' -> col += (n ?: 1)
            'D' -> col = maxOf(0, col - (n ?: 1))
            'G' -> col = maxOf(0, (n ?: 1) - 1)
            'H', 'f' -> col = maxOf(0, (nums.getOrNull(1) ?: 1) - 1)
            // cursor visibility, modes, scrolling regions, etc. are ignored
        }
    }

    private fun eraseInLine(mode: Int) {
        val line = lines[row]
        when (mode) {
            0 -> while (line.size > col) line.removeAt(line.size - 1)
            1 -> for (i in 0 until minOf(col + 1, line.size)) line[i] = blank()
            2 -> line.clear()
        }
    }

    private fun eraseBelow() {
        eraseInLine(0)
        while (lines.size > row + 1) lines.removeAt(lines.size - 1)
    }

    private fun resetStyle() {
        fg = DEFAULT; bg = DEFAULT
        bold = false; italic = false; underline = false; reverse = false
    }

    private fun sgr(nums: List<Int?>) {
        if (nums.isEmpty() || nums.all { it == null }) { resetStyle(); return }
        var i = 0
        while (i < nums.size) {
            when (val code = nums[i] ?: 0) {
                0 -> resetStyle()
                1 -> bold = true
                3 -> italic = true
                4 -> underline = true
                7 -> reverse = true
                22 -> bold = false
                23 -> italic = false
                24 -> underline = false
                27 -> reverse = false
                in 30..37 -> fg = PALETTE[code - 30]
                39 -> fg = DEFAULT
                in 40..47 -> bg = PALETTE[code - 40]
                49 -> bg = DEFAULT
                in 90..97 -> fg = PALETTE[code - 90 + 8]
                in 100..107 -> bg = PALETTE[code - 100 + 8]
                38, 48 -> {
                    val color: Int?
                    when (nums.getOrNull(i + 1)) {
                        5 -> { color = xterm256(nums.getOrNull(i + 2) ?: 0); i += 2 }
                        2 -> {
                            color = Color.rgb(nums.getOrNull(i + 2) ?: 0, nums.getOrNull(i + 3) ?: 0, nums.getOrNull(i + 4) ?: 0)
                            i += 4
                        }
                        else -> color = null
                    }
                    if (color != null) { if (code == 38) fg = color else bg = color }
                }
            }
            i++
        }
    }

    /** Styled text for the whole screen. */
    fun render(): SpannableStringBuilder {
        val out = SpannableStringBuilder()
        for ((index, line) in lines.withIndex()) {
            var i = 0
            while (i < line.size) {
                val first = line[i]
                val style = Style(first.fg, first.bg, first.bold, first.italic, first.underline, first.reverse)
                var j = i
                val run = StringBuilder()
                while (j < line.size) {
                    val c = line[j]
                    if (Style(c.fg, c.bg, c.bold, c.italic, c.underline, c.reverse) != style) break
                    run.append(c.ch)
                    j++
                }
                val start = out.length
                out.append(run)
                applyStyle(out, start, out.length, style)
                i = j
            }
            if (index < lines.size - 1) out.append('\n')
        }
        return out
    }

    private fun applyStyle(out: SpannableStringBuilder, start: Int, end: Int, s: Style) {
        var fgc = if (s.fg == DEFAULT) DEFAULT_FG else s.fg
        var bgc = s.bg
        if (s.reverse) {
            val realBg = if (bgc == DEFAULT) DEFAULT_BG else bgc
            bgc = fgc
            fgc = realBg
        }
        val flags = Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
        if (fgc != DEFAULT_FG) out.setSpan(ForegroundColorSpan(fgc), start, end, flags)
        if (bgc != DEFAULT) out.setSpan(BackgroundColorSpan(bgc), start, end, flags)
        if (s.bold && s.italic) out.setSpan(StyleSpan(Typeface.BOLD_ITALIC), start, end, flags)
        else if (s.bold) out.setSpan(StyleSpan(Typeface.BOLD), start, end, flags)
        else if (s.italic) out.setSpan(StyleSpan(Typeface.ITALIC), start, end, flags)
        if (s.underline) out.setSpan(UnderlineSpan(), start, end, flags)
    }

    companion object {
        const val DEFAULT = 0                       // "terminal default" marker (never a real ARGB colour)
        val DEFAULT_FG: Int = Color.rgb(204, 204, 204)
        val DEFAULT_BG: Int = Color.rgb(12, 12, 12)

        private val PALETTE = intArrayOf(
            Color.rgb(30, 30, 30), Color.rgb(205, 49, 49), Color.rgb(13, 188, 121), Color.rgb(229, 229, 16),
            Color.rgb(36, 114, 200), Color.rgb(188, 63, 188), Color.rgb(17, 168, 205), Color.rgb(229, 229, 229),
            Color.rgb(102, 102, 102), Color.rgb(241, 76, 76), Color.rgb(35, 209, 139), Color.rgb(245, 245, 67),
            Color.rgb(59, 142, 234), Color.rgb(214, 112, 214), Color.rgb(41, 184, 219), Color.rgb(255, 255, 255),
        )

        private fun xterm256(n: Int): Int {
            if (n < 16) return PALETTE[n.coerceAtLeast(0)]
            if (n < 232) {
                val levels = intArrayOf(0, 95, 135, 175, 215, 255)
                val v = n - 16
                return Color.rgb(levels[v / 36], levels[(v / 6) % 6], levels[v % 6])
            }
            val gray = (8 + (n - 232).coerceAtMost(23) * 10)
            return Color.rgb(gray, gray, gray)
        }
    }
}
