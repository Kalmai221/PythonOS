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

    /** Set by the activity so PythonOS can ask for things only an Android app can do (installing a newer version of the app). */
    @Volatile var appContext: android.content.Context? = null

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

    /**
     * Downloads the new APK, checks it against [sha256] and gives it to Android's installer (which asks you to confirm).
     * Returns "" when the installer was started, otherwise what went wrong. Called by PythonOS (updatecheck); blocks until the APK is handed over.
     */
    @JvmStatic
    fun installUpdate(url: String, sha256: String): String {
        val context = appContext ?: return "the app is not ready yet"
        return try {
            write("Downloading the new app...\n")
            var shown = -10
            val apk = ApkInstaller.download(context, url, sha256) { percent ->
                if (percent >= shown + 10) { shown = percent; write("  $percent%\n") }
            }
            write("The download is genuine. Android will now ask you to confirm the update.\n")
            ApkInstaller.install(context, apk)
            ""
        } catch (e: Exception) {
            e.message ?: e.toString()
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
