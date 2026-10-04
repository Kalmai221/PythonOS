package com.pythonos.app

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.view.ViewGroup
import android.view.ViewTreeObserver
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File

/** A full-screen terminal: scrolling output on top, an input line and a few keys below. */
class MainActivity : Activity(), TerminalBridge.Listener {

    private lateinit var scroll: ScrollView
    private lateinit var terminal: TextView
    private lateinit var input: EditText

    private val ui = Handler(Looper.getMainLooper())
    private var refreshQueued = false
    private val history = ArrayList<String>()
    private var historyPos = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
        TerminalBridge.listener = this
        render()

        terminal.viewTreeObserver.addOnGlobalLayoutListener(object : ViewTreeObserver.OnGlobalLayoutListener {
            override fun onGlobalLayout() {
                if (terminal.width <= 0 || scroll.height <= 0) return
                terminal.viewTreeObserver.removeOnGlobalLayoutListener(this)
                measureTerminal()
                startPython()
            }
        })
    }

    override fun onDestroy() {
        if (TerminalBridge.listener === this) TerminalBridge.listener = null
        super.onDestroy()
    }

    // ------------------------------------------------------------------ UI
    private fun dp(value: Int) = TypedValue.applyDimension(
        TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), resources.displayMetrics
    ).toInt()

    private fun buildUi() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(AnsiScreen.DEFAULT_BG)
        }

        terminal = TextView(this).apply {
            typeface = Typeface.MONOSPACE
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
            setTextColor(AnsiScreen.DEFAULT_FG)
            setPadding(dp(8), dp(8), dp(8), dp(8))
            setTextIsSelectable(true)
        }
        scroll = ScrollView(this).apply {
            isFillViewport = true
            addView(terminal, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        }
        root.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        val keys = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        keys.addView(keyButton(getString(R.string.key_ctrl_c)) { interrupt() })
        keys.addView(keyButton(getString(R.string.key_up)) { recall(-1) })
        keys.addView(keyButton(getString(R.string.key_down)) { recall(1) })
        keys.addView(keyButton(getString(R.string.key_send)) { submit() })
        root.addView(keys, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))

        input = EditText(this).apply {
            typeface = Typeface.MONOSPACE
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setTextColor(Color.WHITE)
            setHintTextColor(Color.GRAY)
            hint = getString(R.string.input_hint)
            setBackgroundColor(Color.rgb(30, 30, 30))
            setPadding(dp(12), dp(10), dp(12), dp(10))
            setSingleLine(true)
            imeOptions = EditorInfo.IME_ACTION_SEND or EditorInfo.IME_FLAG_NO_EXTRACT_UI
            applyInputType(secret = false)
            setOnEditorActionListener { _, _, _ -> submit(); true }
            setOnKeyListener { _, keyCode, event ->
                if (keyCode == KeyEvent.KEYCODE_ENTER && event.action == KeyEvent.ACTION_DOWN) { submit(); true } else false
            }
        }
        root.addView(input, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))

        setContentView(root)
    }

    private fun keyButton(label: String, action: () -> Unit) = Button(this).apply {
        text = label
        isAllCaps = false
        setTextColor(Color.WHITE)
        setBackgroundColor(Color.rgb(37, 37, 38))
        setOnClickListener { action() }
        layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply {
            setMargins(dp(1), dp(1), dp(1), dp(1))
        }
        gravity = Gravity.CENTER
    }

    private fun EditText.applyInputType(secret: Boolean) {
        inputType = if (secret) {
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        } else {
            // no autocorrect/suggestions: commands are not words
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
        }
        typeface = Typeface.MONOSPACE
    }

    private fun measureTerminal() {
        val charWidth = terminal.paint.measureText("M")
        val usable = terminal.width - terminal.paddingLeft - terminal.paddingRight
        TerminalBridge.columns = (usable / charWidth).toInt().coerceIn(40, 200)
        TerminalBridge.rows = (scroll.height / terminal.lineHeight).coerceIn(10, 100)
    }

    // ------------------------------------------------------------- input
    private fun submit() {
        val text = input.text.toString()
        if (!TerminalBridge.waitingForInput) return
        input.setText("")
        if (TerminalBridge.secretInput) {
            TerminalBridge.write("\n")
        } else {
            TerminalBridge.write(text + "\n")
            if (text.isNotBlank()) { history.add(text); }
            historyPos = history.size
        }
        TerminalBridge.submit(text)
    }

    private fun interrupt() {
        if (!TerminalBridge.waitingForInput) return
        input.setText("")
        TerminalBridge.write("^C\n")
        TerminalBridge.submit("\u0003")
    }

    private fun recall(direction: Int) {
        if (history.isEmpty() || TerminalBridge.secretInput) return
        historyPos = (historyPos + direction).coerceIn(0, history.size)
        input.setText(if (historyPos < history.size) history[historyPos] else "")
        input.setSelection(input.text.length)
    }

    // ------------------------------------------------------------ Python
    private fun startPython() {
        if (started) return
        started = true
        TerminalBridge.reset()
        Thread({
            try {
                // The OS itself is downloaded into here on first launch (see pyos_android.py)
                val dir = File(filesDir, "pythonos").apply { mkdirs() }
                if (!Python.isStarted()) Python.start(AndroidPlatform(applicationContext))
                Python.getInstance().getModule("pyos_android").callAttr("main", dir.absolutePath)
            } catch (e: Throwable) {
                TerminalBridge.write("\u001b[31mPythonOS failed to start: $e\u001b[0m\n")
                TerminalBridge.finished()
            }
        }, "pythonos").start()
    }

    // ----------------------------------------------- TerminalBridge.Listener
    override fun onOutput() {
        if (refreshQueued) return
        refreshQueued = true
        ui.postDelayed({ refreshQueued = false; render() }, 40)
    }

    override fun onPrompt(secret: Boolean) {
        runOnUiThread {
            input.applyInputType(secret)
            input.requestFocus()
            (getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager).showSoftInput(input, InputMethodManager.SHOW_IMPLICIT)
        }
    }

    override fun onFinished() {
        // "shutdown" closes the app; the next launch boots the OS again
        started = false
        ui.postDelayed({ if (!isFinishing) finishAndRemoveTask() }, 1500)
    }

    private fun render() {
        val text = synchronized(TerminalBridge.screen) { TerminalBridge.screen.render() }
        terminal.text = text
        scroll.post { scroll.fullScroll(View.FOCUS_DOWN) }
    }

    companion object {
        @Volatile private var started = false
    }
}
