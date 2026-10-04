package com.pythonos.app

import java.util.concurrent.LinkedBlockingQueue

/**
 * Connects the Python side (pyos_android.py) to the UI.
 * Python calls the @JvmStatic functions below; the terminal view listens for changes.
 */
object TerminalBridge {
    interface Listener {
        fun onOutput()
        fun onPrompt(secret: Boolean)
        fun onFinished()
    }

    val screen = AnsiScreen()

    @Volatile var listener: Listener? = null
    @Volatile var columns = 80
    @Volatile var rows = 24
    @Volatile var waitingForInput = false
    @Volatile var secretInput = false
    @Volatile var done = false

    /** The prompt text PythonOS last asked with, so the screen can redraw it after listing completions. */
    @Volatile var lastPrompt = ""

    private val lines = LinkedBlockingQueue<String>()

    /** Terminal output from Python (may contain ANSI escape sequences). */
    @JvmStatic
    fun write(text: String) {
        synchronized(screen) { screen.feed(text) }
        listener?.onOutput()
    }

    /** Blocks the Python thread until the user submits a line. */
    @JvmStatic
    fun readLine(prompt: String, secret: Boolean): String {
        if (prompt.isNotEmpty()) {
            lastPrompt = prompt
            write(prompt)
        }
        secretInput = secret
        waitingForInput = true
        listener?.onPrompt(secret)
        try {
            return lines.take()
        } finally {
            waitingForInput = false
        }
    }

    @JvmStatic fun termColumns(): Int = columns
    @JvmStatic fun termRows(): Int = rows

    @JvmStatic
    fun finished() {
        done = true
        listener?.onFinished()
    }

    fun submit(line: String) {
        lines.offer(line)
    }

    fun reset() {
        synchronized(screen) { screen.clear() }
        lines.clear()
        waitingForInput = false
        done = false
        lastPrompt = ""
    }
}
