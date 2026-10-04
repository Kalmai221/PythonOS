package com.pythonos.app

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.text.InputType
import android.util.TypedValue
import android.view.GestureDetector
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import android.view.View
import android.view.inputmethod.BaseInputConnection
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputConnection
import android.view.inputmethod.InputMethodManager
import android.widget.OverScroller

/**
 * The terminal. This view draws the screen AND is what you type into: the on-screen keyboard (and a
 * hardware keyboard) talks straight to it, the line you are typing appears right after the prompt with
 * a blinking cursor, and Enter hands it to PythonOS - like a normal terminal, not a separate text box.
 *
 * It always shows the bottom of the screen: new output and typing snap back to it. You can drag up to
 * read older output; a "Latest" button appears to jump back down.
 */
class TerminalView(context: Context) : View(context) {

    interface Listener {
        /** The view is now `cols` x `rows` characters (first layout, rotation, keyboard, zoom). */
        fun onResize(cols: Int, rows: Int)
        /** Tab was pressed: complete the last word of this text. */
        fun onComplete(textBeforeCursor: String)
        /** Ctrl+C. */
        fun onInterrupt()
        fun onLongPress()
        fun onTextSizeChanged(sp: Float)
    }

    var listener: Listener? = null

    // ------------------------------------------------------------- drawing
    private val density = resources.displayMetrics.density
    private val padX = 8f * density
    private val padY = 4f * density
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val fill = Paint()
    private val tfNormal: Typeface = Typeface.MONOSPACE
    private val tfBold: Typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
    private val tfItalic: Typeface = Typeface.create(Typeface.MONOSPACE, Typeface.ITALIC)
    private val tfBoldItalic: Typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD_ITALIC)

    var textSizeSp = 13f
        private set
    private var textSizePx = 0f
    private var charW = 1f
    private var charH = 1f
    private var baseline = 0f

    var cols = 0
        private set
    var rows = 0
        private set

    private var cachedFrame: Frame? = null
    private var cacheKey = ""

    private var cursorOn = true
    private val blink = object : Runnable {
        override fun run() {
            cursorOn = !cursorOn
            invalidate()
            postDelayed(this, 530)
        }
    }

    // ------------------------------------------------------------ scrolling
    /** How far above the bottom the user has scrolled, in pixels. 0 = at the bottom (where we always return to). */
    @Volatile private var offset = 0f
    private var maxOffset = 0f
    private val scroller = OverScroller(context)
    private val pill = RectF()

    // --------------------------------------------------------------- input
    private val input = StringBuilder()
    private var cursor = 0
    private var secret = false
    val history = ArrayList<String>()
    private var historyPos = -1
    private var draft = ""

    init {
        isFocusable = true
        isFocusableInTouchMode = true
        setTextSizeSp(13f)
    }

    // ---------------------------------------------------------------- sizing
    fun setTextSizeSp(sp: Float) {
        textSizeSp = sp.coerceIn(8f, 30f)
        textSizePx = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, textSizeSp, resources.displayMetrics)
        paint.typeface = tfNormal
        paint.textSize = textSizePx
        charW = paint.measureText("M")
        val fm = paint.fontMetrics
        val glyphH = fm.descent - fm.ascent
        charH = glyphH * 1.1f
        baseline = -fm.ascent + (charH - glyphH) / 2f
        cacheKey = ""
        recalculate()
        invalidate()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        offset = 0f              // the keyboard opening or a rotation must never leave us scrolled away from the prompt
        recalculate()
    }

    private fun recalculate() {
        if (width <= 0 || height <= 0) return
        val c = ((width - 2 * padX) / charW).toInt().coerceAtLeast(20)
        val r = ((height - 2 * padY) / charH).toInt().coerceAtLeast(5)
        if (c != cols || r != rows) {
            cols = c
            rows = r
            TerminalBridge.columns = c
            TerminalBridge.rows = r
            cacheKey = ""
            listener?.onResize(c, r)
        }
    }

    // ------------------------------------------------------------ rendering
    private fun currentFrame(): Frame {
        val showInput = TerminalBridge.waitingForInput
        val shown = if (secret) "" else input.toString()
        val key = "${TerminalBridge.screen.version}|$cols|$showInput|$shown|$cursor"
        val cached = cachedFrame
        if (cached != null && key == cacheKey) return cached
        val built = synchronized(TerminalBridge.screen) {
            TerminalBridge.screen.frame(cols, shown, if (secret) 0 else cursor, showInput)
        }
        cachedFrame = built
        cacheKey = key
        return built
    }

    override fun onDraw(canvas: Canvas) {
        canvas.drawColor(AnsiScreen.DEFAULT_BG)
        if (cols == 0) return
        val frame = currentFrame()
        val total = frame.rows.size
        val viewH = height - 2 * padY
        val contentH = total * charH
        maxOffset = maxOf(0f, contentH - viewH)
        if (offset > maxOffset) offset = maxOffset
        if (offset < 0f) offset = 0f
        val viewTop = maxOf(0f, contentH - viewH) - offset

        val first = (viewTop / charH).toInt().coerceAtLeast(0)
        val last = (((viewTop + viewH) / charH).toInt() + 1).coerceAtMost(total)
        for (r in first until last) {
            drawRow(canvas, frame.rows[r], padY + r * charH - viewTop)
        }

        if (frame.cursorRow in first until last && (cursorOn || !hasFocus())) {
            val x = padX + frame.cursorCol * charW
            val y = padY + frame.cursorRow * charH - viewTop
            fill.color = 0xFFE6E6E6.toInt()
            canvas.drawRect(x, y, x + charW, y + charH, fill)
            val rowCells = frame.rows[frame.cursorRow]
            if (frame.cursorCol < rowCells.size) {       // keep the character under the cursor readable
                paint.typeface = tfNormal
                paint.isUnderlineText = false
                paint.color = AnsiScreen.DEFAULT_BG
                canvas.drawText(rowCells[frame.cursorCol].ch.toString(), x, y + baseline, paint)
            }
        }

        if (offset > 1f) drawLatestPill(canvas)
    }

    private fun drawLatestPill(canvas: Canvas) {
        val label = "↓ Latest"
        paint.typeface = tfBold
        paint.isUnderlineText = false
        paint.textSize = 13f * density
        val w = paint.measureText(label) + 28f * density
        val h = 34f * density
        pill.set(width - w - 12f * density, height - h - 12f * density, width - 12f * density, height - 12f * density)
        fill.color = 0xE62B3A55.toInt()
        canvas.drawRoundRect(pill, h / 2, h / 2, fill)
        paint.color = 0xFFFFFFFF.toInt()
        canvas.drawText(label, pill.left + 14f * density, pill.centerY() + paint.textSize * 0.35f, paint)
        paint.textSize = textSizePx
    }

    private fun gridSafe(c: Char): Boolean = c.code < 0x300 || c.code in 0x2500..0x259F

    private fun sameStyle(a: Cell, b: Cell) =
        a.fg == b.fg && a.bg == b.bg && a.bold == b.bold && a.italic == b.italic &&
            a.underline == b.underline && a.reverse == b.reverse

    private fun drawRow(canvas: Canvas, cells: List<Cell>, y: Float) {
        var i = 0
        while (i < cells.size) {
            val c = cells[i]
            var j = i + 1
            while (j < cells.size && sameStyle(c, cells[j])) j++

            var fg = if (c.fg == AnsiScreen.DEFAULT) AnsiScreen.DEFAULT_FG else c.fg
            var bg = if (c.bg == AnsiScreen.DEFAULT) AnsiScreen.DEFAULT_BG else c.bg
            if (c.reverse) { val t = fg; fg = bg; bg = t }

            val x = padX + i * charW
            if (bg != AnsiScreen.DEFAULT_BG) {
                fill.color = bg
                canvas.drawRect(x, y, x + (j - i) * charW, y + charH, fill)
            }
            paint.typeface = when {
                c.bold && c.italic -> tfBoldItalic
                c.bold -> tfBold
                c.italic -> tfItalic
                else -> tfNormal
            }
            paint.isUnderlineText = c.underline
            paint.color = fg

            // draw runs of ordinary characters in one call; anything that might not be one cell wide on its own
            var k = i
            while (k < j) {
                if (gridSafe(cells[k].ch)) {
                    var e = k
                    val sb = StringBuilder()
                    while (e < j && gridSafe(cells[e].ch)) { sb.append(cells[e].ch); e++ }
                    canvas.drawText(sb.toString(), padX + k * charW, y + baseline, paint)
                    k = e
                } else {
                    canvas.drawText(cells[k].ch.toString(), padX + k * charW, y + baseline, paint)
                    k++
                }
            }
            i = j
        }
        paint.isUnderlineText = false
    }

    // -------------------------------------------------------------- scrolling
    private fun snapToBottom() {
        scroller.forceFinished(true)
        offset = 0f
    }

    /** New output arrived (any thread): always show the bottom. */
    fun onOutput() {
        offset = 0f
        postInvalidateOnAnimation()
    }

    override fun computeScroll() {
        if (scroller.computeScrollOffset()) {
            offset = scroller.currY.toFloat().coerceIn(0f, maxOffset)
            postInvalidateOnAnimation()
        }
    }

    private val gestures = GestureDetector(context, object : GestureDetector.SimpleOnGestureListener() {
        override fun onDown(e: MotionEvent): Boolean {
            scroller.forceFinished(true)
            return true
        }

        override fun onSingleTapUp(e: MotionEvent): Boolean {
            if (offset > 1f && pill.contains(e.x, e.y)) {
                snapToBottom()
                invalidate()
            } else {
                showKeyboard()
            }
            return true
        }

        override fun onScroll(e1: MotionEvent?, e2: MotionEvent, distanceX: Float, distanceY: Float): Boolean {
            offset = (offset - distanceY).coerceIn(0f, maxOffset)
            invalidate()
            return true
        }

        override fun onFling(e1: MotionEvent?, e2: MotionEvent, velocityX: Float, velocityY: Float): Boolean {
            scroller.fling(0, offset.toInt(), 0, velocityY.toInt(), 0, 0, 0, maxOffset.toInt())
            postInvalidateOnAnimation()
            return true
        }

        override fun onLongPress(e: MotionEvent) {
            listener?.onLongPress()
        }
    })

    private val scaler = ScaleGestureDetector(context, object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
        override fun onScale(detector: ScaleGestureDetector): Boolean {
            val before = textSizeSp
            setTextSizeSp(textSizeSp * detector.scaleFactor)
            if (textSizeSp != before) listener?.onTextSizeChanged(textSizeSp)
            return true
        }
    })

    override fun onTouchEvent(event: MotionEvent): Boolean {
        scaler.onTouchEvent(event)
        if (!scaler.isInProgress) gestures.onTouchEvent(event)
        return true
    }

    // ----------------------------------------------------------- the keyboard
    fun showKeyboard() {
        requestFocus()
        (context.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).showSoftInput(this, InputMethodManager.SHOW_IMPLICIT)
    }

    fun setSecret(value: Boolean) {
        if (secret == value) return
        secret = value
        (context.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).restartInput(this)
        invalidate()
    }

    override fun onCheckIsTextEditor() = true

    override fun onCreateInputConnection(outAttrs: EditorInfo): InputConnection {
        // "visible password" turns off autocorrect, suggestions and word composing: commands are not words
        outAttrs.inputType = if (secret) {
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        } else {
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
        }
        outAttrs.imeOptions = EditorInfo.IME_FLAG_NO_FULLSCREEN or EditorInfo.IME_FLAG_NO_EXTRACT_UI or EditorInfo.IME_ACTION_NONE
        return TermInputConnection()
    }

    private inner class TermInputConnection : BaseInputConnection(this@TerminalView, false) {
        private var composing = 0

        private fun dropComposing() {
            if (composing > 0) {
                val n = minOf(composing, cursor)
                input.delete(cursor - n, cursor)
                cursor -= n
                composing = 0
            }
        }

        override fun commitText(text: CharSequence, newCursorPosition: Int): Boolean {
            dropComposing()
            typeText(text.toString())
            return true
        }

        override fun setComposingText(text: CharSequence, newCursorPosition: Int): Boolean {
            dropComposing()
            val s = text.toString().replace("\n", "")
            input.insert(cursor, s)
            cursor += s.length
            composing = s.length
            changed()
            return true
        }

        override fun finishComposingText(): Boolean {
            composing = 0
            return true
        }

        override fun deleteSurroundingText(beforeLength: Int, afterLength: Int): Boolean {
            composing = 0
            repeat(beforeLength) { if (cursor > 0) { input.deleteCharAt(cursor - 1); cursor-- } }
            repeat(afterLength) { if (cursor < input.length) input.deleteCharAt(cursor) }
            changed()
            return true
        }

        override fun sendKeyEvent(event: KeyEvent): Boolean {
            if (event.action == KeyEvent.ACTION_DOWN) handleKey(event.keyCode, event)
            return true
        }

        override fun performEditorAction(actionCode: Int): Boolean {
            submit()
            return true
        }

        override fun setSelection(start: Int, end: Int): Boolean {
            cursor = start.coerceIn(0, input.length)
            changed()
            return true
        }

        override fun getTextBeforeCursor(n: Int, flags: Int): CharSequence = input.substring(maxOf(0, cursor - n), cursor)
        override fun getTextAfterCursor(n: Int, flags: Int): CharSequence = input.substring(cursor, minOf(input.length, cursor + n))
        override fun getSelectedText(flags: Int): CharSequence? = null
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean =
        if (handleKey(keyCode, event)) true else super.onKeyDown(keyCode, event)

    /** A key from the on-screen keyboard's key events, a hardware keyboard, or the extra-keys row. */
    fun handleKey(keyCode: Int, event: KeyEvent): Boolean {
        when (keyCode) {
            KeyEvent.KEYCODE_DEL -> { backspace(); return true }
            KeyEvent.KEYCODE_FORWARD_DEL -> { deleteForward(); return true }
            KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_NUMPAD_ENTER -> { submit(); return true }
            KeyEvent.KEYCODE_DPAD_LEFT -> { moveCursor(-1); return true }
            KeyEvent.KEYCODE_DPAD_RIGHT -> { moveCursor(1); return true }
            KeyEvent.KEYCODE_DPAD_UP -> { recall(-1); return true }
            KeyEvent.KEYCODE_DPAD_DOWN -> { recall(1); return true }
            KeyEvent.KEYCODE_MOVE_HOME -> { cursor = 0; changed(); return true }
            KeyEvent.KEYCODE_MOVE_END -> { cursor = input.length; changed(); return true }
            KeyEvent.KEYCODE_TAB -> { requestCompletion(); return true }
            KeyEvent.KEYCODE_ESCAPE -> return true
        }
        if (event.isCtrlPressed) {
            when (keyCode) {
                KeyEvent.KEYCODE_C -> { interrupt(); return true }
                KeyEvent.KEYCODE_U -> { setInput(""); return true }
                KeyEvent.KEYCODE_A -> { cursor = 0; changed(); return true }
                KeyEvent.KEYCODE_E -> { cursor = input.length; changed(); return true }
                KeyEvent.KEYCODE_L -> { typeText("clear\n"); return true }
            }
            return false
        }
        val u = event.unicodeChar
        if (u != 0 && (u and COMBINING_ACCENT) == 0 && !event.isAltPressed) {
            typeText(String(Character.toChars(u)))
            return true
        }
        return false
    }

    // ------------------------------------------------------------ line editing
    private fun changed() {
        snapToBottom()
        cursorOn = true
        invalidate()
    }

    /** Type text at the cursor. A line break submits the line, so a pasted block runs line by line. */
    fun typeText(raw: String) {
        val text = raw.replace("\r\n", "\n").replace('\r', '\n').replace("\t", "    ")
        for (ch in text) {
            if (ch == '\n') {
                submit()
            } else if (ch >= ' ') {
                input.insert(cursor, ch)
                cursor++
            }
        }
        historyPos = -1
        changed()
    }

    private fun backspace() {
        if (cursor > 0) { input.deleteCharAt(cursor - 1); cursor-- }
        historyPos = -1
        changed()
    }

    private fun deleteForward() {
        if (cursor < input.length) input.deleteCharAt(cursor)
        changed()
    }

    private fun moveCursor(by: Int) {
        cursor = (cursor + by).coerceIn(0, input.length)
        changed()
    }

    private fun setInput(text: String) {
        input.setLength(0)
        input.append(text)
        cursor = input.length
        changed()
    }

    private fun recall(direction: Int) {
        if (secret || history.isEmpty()) return
        if (direction < 0) {
            if (historyPos == -1) { draft = input.toString(); historyPos = history.size - 1 }
            else if (historyPos > 0) historyPos--
            setInput(history[historyPos])
        } else if (historyPos != -1) {
            if (historyPos < history.size - 1) { historyPos++; setInput(history[historyPos]) }
            else { historyPos = -1; setInput(draft) }
        }
    }

    /** Enter. If PythonOS is not asking for input yet, the text stays in the line (type-ahead). */
    fun submit() {
        if (!TerminalBridge.waitingForInput) return
        val text = input.toString()
        TerminalBridge.write(if (secret) "\n" else text + "\n")
        if (!secret && text.isNotBlank() && (history.isEmpty() || history.last() != text)) {
            history.add(text)
            if (history.size > 300) history.removeAt(0)
        }
        input.setLength(0)
        cursor = 0
        historyPos = -1
        changed()
        TerminalBridge.submit(text)
    }

    /** Ctrl+C: drop the line being typed and interrupt whatever PythonOS is doing. */
    fun interrupt() {
        input.setLength(0)
        cursor = 0
        changed()
        listener?.onInterrupt()
    }

    private fun requestCompletion() {
        if (secret || !TerminalBridge.waitingForInput) return
        listener?.onComplete(input.substring(0, cursor))
    }

    /** The result of a Tab press (called on the UI thread). */
    fun applyCompletions(before: String, options: List<String>) {
        if (options.isEmpty() || input.substring(0, cursor) != before) return
        val wordStart = before.lastIndexOf(' ') + 1
        val word = before.substring(wordStart)
        if (options.size == 1) {
            val chosen = options[0] + (if (options[0].endsWith("/")) "" else " ")
            replaceRange(wordStart, cursor, chosen)
            return
        }
        var common = options[0]
        for (o in options) {
            var n = 0
            while (n < common.length && n < o.length && common[n] == o[n]) n++
            common = common.substring(0, n)
        }
        if (common.length > word.length) {
            replaceRange(wordStart, cursor, common)
        } else {
            // like a shell: keep the line, list the choices below it, then draw the prompt and line again
            val width = (options.maxOf { it.length } + 2).coerceAtLeast(4)
            val perRow = maxOf(1, cols / width)
            val sb = StringBuilder(input.toString()).append('\n')
            options.forEachIndexed { index, option ->
                sb.append(option.padEnd(width))
                if ((index + 1) % perRow == 0 || index == options.lastIndex) sb.append('\n')
            }
            sb.append(TerminalBridge.lastPrompt)
            TerminalBridge.write(sb.toString())
        }
    }

    private fun replaceRange(start: Int, end: Int, text: String) {
        input.replace(start, end, text)
        cursor = start + text.length
        historyPos = -1
        changed()
    }

    // --------------------------------------------------------------- lifecycle
    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        postDelayed(blink, 530)
    }

    override fun onDetachedFromWindow() {
        removeCallbacks(blink)
        super.onDetachedFromWindow()
    }

    /** The whole screen as text, for Copy. */
    fun screenText(): String = synchronized(TerminalBridge.screen) { TerminalBridge.screen.plainText() }

    private companion object {
        /** Set on a key's unicode value when it is a dead accent key rather than a character. */
        const val COMBINING_ACCENT = Int.MIN_VALUE
    }
}
