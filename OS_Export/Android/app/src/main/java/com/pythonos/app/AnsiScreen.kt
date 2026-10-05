package com.pythonos.app

import android.graphics.Color

/** One character cell with its style. Colour 0 (DEFAULT) means "the terminal's own colour". */
class Cell(
    val ch: Char,
    val fg: Int,
    val bg: Int,
    val bold: Boolean,
    val italic: Boolean,
    val underline: Boolean,
    val reverse: Boolean,
)

/** What to draw: wrapped rows of cells and where the cursor is (cursorRow -1 = no cursor). */
class Frame(val rows: List<List<Cell>>, val cursorRow: Int, val cursorCol: Int)

/**
 * A small terminal emulator: turns the text PythonOS prints (including the ANSI colour and cursor codes
 * used by rich and yaspin) into lines of styled cells. It keeps scrollback and a cursor, which is enough
 * for colours, carriage-return spinners, "clear" and in-place progress bars. The line being typed is not
 * part of it: the view passes that in when it asks for a frame, so editing never touches the scrollback.
 */
class AnsiScreen(private val maxLines: Int = 3000) {

    private val lines = ArrayList<ArrayList<Cell>>()
    private var row = 0
    private var col = 0

    /** Changes whenever the visible content changes, so views can cache what they built. */
    @Volatile var version = 0L
        private set

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
        version++
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
        version++
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

    // ------------------------------------------------------------------ output
    /**
     * Rows to draw, `cols` cells wide. While the user is typing (`showInput`), the line being edited is
     * placed after the prompt on the cursor's line and the cursor row/column are returned.
     */
    fun frame(cols: Int, input: String, cursorIndex: Int, showInput: Boolean): Frame {
        val width = maxOf(1, cols)
        val out = ArrayList<List<Cell>>()
        var cursorRow = -1
        var cursorCol = 0
        val first = maxOf(0, lines.size - MAX_FRAME_LINES)
        for (index in first until lines.size) {
            val line = lines[index]
            val onCursorLine = showInput && index == row
            val cells: List<Cell> = if (onCursorLine) {
                val combined = ArrayList<Cell>(line.take(col))
                while (combined.size < col) combined.add(blank())
                for (ch in input) combined.add(Cell(ch, DEFAULT, DEFAULT, false, false, false, false))
                combined
            } else line
            val start = out.size
            if (cells.isEmpty()) {
                out.add(emptyList())
            } else {
                var i = 0
                while (i < cells.size) {
                    out.add(ArrayList(cells.subList(i, minOf(i + width, cells.size))))
                    i += width
                }
            }
            if (onCursorLine) {
                val at = col + cursorIndex.coerceIn(0, input.length)
                cursorRow = start + at / width
                cursorCol = at % width
                while (out.size <= cursorRow) out.add(emptyList())
            }
        }
        return Frame(out, cursorRow, cursorCol)
    }

    /** The whole scrollback as plain text (for "copy"). */
    fun plainText(): String = lines.joinToString("\n") { line -> String(CharArray(line.size) { line[it].ch }).trimEnd() }.trimEnd()

    companion object {
        const val DEFAULT = 0                       // "terminal default" marker (never a real ARGB colour)
        private const val MAX_FRAME_LINES = 1500
        // the colour scheme: MainActivity sets these (a palette chosen in Appearance) before the terminal is drawn
        @Volatile var DEFAULT_FG: Int = Color.rgb(204, 204, 204)
        @Volatile var DEFAULT_BG: Int = Color.rgb(12, 12, 12)

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
