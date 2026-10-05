package com.pythonos.app

import android.app.Activity
import android.app.AlertDialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.net.Uri
import android.os.Bundle
import android.util.TypedValue
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.KeyEvent
import android.view.Menu
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.PopupMenu
import android.widget.TextView
import android.widget.Toast
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors

/**
 * PythonOS on Android: the terminal fills the screen and is the input (see TerminalView). Around it:
 * an app bar with an actions menu, a banner when a newer APK exists (the app cannot update itself), and a
 * row of the keys phone keyboards make awkward - Tab, Ctrl+C, arrows and symbols like / ~ | > &.
 */
class MainActivity : Activity(), TerminalBridge.Listener, TerminalView.Listener {

    private lateinit var terminal: TerminalView
    private lateinit var banner: TextView
    private val density by lazy { resources.displayMetrics.density }
    private val worker = Executors.newSingleThreadExecutor()
    private val prefs by lazy { getSharedPreferences("terminal", Context.MODE_PRIVATE) }
    private var updateUrl: String? = null

    private lateinit var sizeLabel: TextView

    // colour scheme (chosen under "Appearance", kept in prefs): terminal background, bar, key chips, accent, terminal text
    private class Palette(val name: String, val bg: Int, val bar: Int, val chip: Int, val accent: Int, val fg: Int)
    private val palettes = listOf(
        Palette("Midnight", Color.rgb(12, 12, 12), Color.rgb(22, 22, 28), Color.rgb(40, 42, 50), Color.rgb(122, 162, 247), Color.rgb(204, 204, 204)),
        Palette("Slate", Color.rgb(26, 30, 38), Color.rgb(35, 40, 52), Color.rgb(52, 59, 76), Color.rgb(137, 220, 180), Color.rgb(214, 220, 232)),
        Palette("Ocean", Color.rgb(8, 24, 36), Color.rgb(14, 36, 54), Color.rgb(28, 58, 82), Color.rgb(100, 210, 255), Color.rgb(206, 228, 240)),
    )
    private var bg = Color.rgb(12, 12, 12)
    private var bar = Color.rgb(22, 22, 28)
    private var chipColor = Color.rgb(40, 42, 50)
    private var accent = Color.rgb(122, 162, 247)

    private fun applyPalette() {
        val p = palettes.getOrNull(prefs.getInt("palette", 0)) ?: palettes[0]
        bg = p.bg; bar = p.bar; chipColor = p.chip; accent = p.accent
        AnsiScreen.DEFAULT_FG = p.fg
        AnsiScreen.DEFAULT_BG = p.bg
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        applyPalette()
        setContentView(buildUi())
        TerminalBridge.listener = this
        window.statusBarColor = bar
        window.navigationBarColor = bg
        if (prefs.getBoolean("keep_awake", false)) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        terminal.setTextSizeSp(prefs.getFloat("text_size", 13f))
        try {
            val saved = JSONArray(prefs.getString("history", "[]"))
            for (i in 0 until saved.length()) terminal.history.add(saved.getString(i))
        } catch (e: Exception) {
            // history is a convenience; ignore a damaged copy
        }
        terminal.requestFocus()
    }

    override fun onPause() {
        prefs.edit().putString("history", JSONArray(terminal.history).toString()).apply()
        super.onPause()
    }

    override fun onDestroy() {
        if (TerminalBridge.listener === this) TerminalBridge.listener = null
        super.onDestroy()
    }

    // ------------------------------------------------------------------- UI
    private fun dp(value: Int) = (value * density).toInt()

    private fun rounded(color: Int, radiusDp: Float): GradientDrawable =
        GradientDrawable().apply {
            setColor(color)
            cornerRadius = radiusDp * density
        }

    private fun withRipple(content: Drawable): Drawable =
        RippleDrawable(ColorStateList.valueOf(Color.argb(60, 255, 255, 255)), content, null)

    private fun buildUi(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(bg)
        }

        // --- app bar
        val appBar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setBackgroundColor(bar)
            setPadding(dp(16), 0, dp(4), 0)
            elevation = 4f * density
        }
        val titles = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        titles.addView(TextView(this).apply {
            text = "PythonOS"
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 19f)
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        })
        sizeLabel = TextView(this).apply {
            text = "terminal"
            setTextColor(Color.rgb(140, 145, 155))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
            compoundDrawablePadding = dp(6)
            // a small status dot in the accent colour
            setCompoundDrawablesWithIntrinsicBounds(
                GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(accent); setSize(dp(8), dp(8)) }, null, null, null)
            gravity = Gravity.CENTER_VERTICAL
        }
        titles.addView(sizeLabel)
        appBar.addView(titles, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val menuButton = TextView(this).apply {
            text = "⋮"
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 26f)
            background = withRipple(rounded(Color.TRANSPARENT, 24f))
            isClickable = true
            contentDescription = "More options"
            setOnClickListener { showMenu(this) }
        }
        appBar.addView(menuButton, LinearLayout.LayoutParams(dp(48), dp(48)))
        root.addView(appBar, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(56)))

        // --- "newer app available" banner (hidden until the check finds one)
        banner = TextView(this).apply {
            visibility = View.GONE
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            setPadding(dp(16), dp(10), dp(16), dp(10))
            background = rounded(Color.rgb(36, 52, 88), 14f)
            isClickable = true
            setOnClickListener { showUpdateDialog(null) }
        }
        root.addView(banner, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            .apply { setMargins(dp(10), dp(8), dp(10), 0) })

        // --- the terminal
        terminal = TerminalView(this)
        terminal.listener = this
        root.addView(terminal, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        // --- extra keys
        val keys = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(4), dp(4), dp(4), dp(4))
        }
        fun key(label: String, description: String, action: () -> Unit) {
            keys.addView(TextView(this).apply {
                text = label
                gravity = Gravity.CENTER
                typeface = Typeface.MONOSPACE
                setTextColor(Color.rgb(230, 232, 236))
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
                minWidth = dp(44)
                setPadding(dp(12), 0, dp(12), 0)
                background = withRipple(rounded(chipColor, 10f))
                isClickable = true
                contentDescription = description
                setOnClickListener {
                    performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                    action()
                }
            }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(40)).apply { setMargins(dp(3), 0, dp(3), 0) })
        }
        fun special(code: Int) = terminal.handleKey(code, KeyEvent(KeyEvent.ACTION_DOWN, code))
        key("Tab", "Complete") { special(KeyEvent.KEYCODE_TAB) }
        key("Ctrl+C", "Interrupt") { terminal.interrupt() }
        key("↑", "History up") { special(KeyEvent.KEYCODE_DPAD_UP) }
        key("↓", "History down") { special(KeyEvent.KEYCODE_DPAD_DOWN) }
        key("←", "Cursor left") { special(KeyEvent.KEYCODE_DPAD_LEFT) }
        key("→", "Cursor right") { special(KeyEvent.KEYCODE_DPAD_RIGHT) }
        for (symbol in listOf("/", "~", "-", "_", "|", ">", "&", "$", ".", ":", ";", "*", "\"", "'", "=")) {
            key(symbol, "Type $symbol") { terminal.typeText(symbol) }
        }
        val keyRow = HorizontalScrollView(this).apply {
            isHorizontalScrollBarEnabled = false
            background = rounded(bar, 22f)
            isFocusable = false
            addView(keys)
        }
        root.addView(keyRow, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            .apply { setMargins(dp(8), dp(4), dp(8), dp(8)) })
        return root
    }

    private fun showMenu(anchor: View) {
        val menu = PopupMenu(this, anchor)
        menu.menu.add(Menu.NONE, 1, 1, "Paste")
        menu.menu.add(Menu.NONE, 2, 2, "Copy screen text")
        menu.menu.add(Menu.NONE, 3, 3, "Larger text")
        menu.menu.add(Menu.NONE, 4, 4, "Smaller text")
        menu.menu.add(Menu.NONE, 5, 5, "Keep screen on").apply {
            isCheckable = true
            isChecked = prefs.getBoolean("keep_awake", false)
        }
        menu.menu.add(Menu.NONE, 6, 6, "Check for app update")
        menu.menu.add(Menu.NONE, 7, 7, "About")
        menu.menu.add(Menu.NONE, 8, 8, "Appearance: " + palettes[prefs.getInt("palette", 0).coerceIn(0, palettes.size - 1)].name)
        menu.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                1 -> paste()
                2 -> copyScreen()
                3 -> resizeText(1f)
                4 -> resizeText(-1f)
                5 -> setKeepAwake(!prefs.getBoolean("keep_awake", false))
                6 -> checkAppUpdate(manual = true)
                7 -> showAbout()
                8 -> {
                    // next colour scheme; the activity is rebuilt so every colour (and the terminal) picks it up
                    prefs.edit().putInt("palette", (prefs.getInt("palette", 0) + 1) % palettes.size).apply()
                    recreate()
                }
            }
            true
        }
        menu.show()
    }

    private fun paste() {
        val clip = (getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).primaryClip
        val text = clip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this)?.toString()
        if (text.isNullOrEmpty()) Toast.makeText(this, "Nothing to paste", Toast.LENGTH_SHORT).show()
        else terminal.typeText(text)
    }

    private fun copyScreen() {
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("PythonOS", terminal.screenText()))
        Toast.makeText(this, "Screen text copied", Toast.LENGTH_SHORT).show()
    }

    private fun resizeText(delta: Float) {
        terminal.setTextSizeSp(terminal.textSizeSp + delta)
        onTextSizeChanged(terminal.textSizeSp)
    }

    private fun setKeepAwake(on: Boolean) {
        prefs.edit().putBoolean("keep_awake", on).apply()
        if (on) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    private fun showAbout() {
        val version = try {
            packageManager.getPackageInfo(packageName, 0).versionName
        } catch (e: Exception) {
            "?"
        }
        AlertDialog.Builder(this, android.R.style.Theme_Material_Dialog_Alert)
            .setTitle("PythonOS")
            .setMessage("App version $version\n\nThe terminal runs PythonOS. PythonOS updates itself; this app is a separate " +
                "package, so a new version of the app has to be downloaded and installed by hand (see \"Check for app update\").")
            .setPositiveButton("OK", null)
            .show()
    }

    // ------------------------------------------------------------ app updates
    /** The APK can't update itself: ask PythonOS whether a newer one exists and say so, with the download link. */
    private fun checkAppUpdate(manual: Boolean) {
        if (!Python.isStarted()) {
            if (manual) Toast.makeText(this, "PythonOS is still starting - try again in a moment", Toast.LENGTH_SHORT).show()
            return
        }
        worker.execute {
            val json = try {
                Python.getInstance().getModule("pyos_android").callAttr("app_update").toString()
            } catch (e: Throwable) {
                ""
            }
            runOnUiThread {
                if (json.isBlank()) {
                    if (manual) Toast.makeText(this, "No newer app found (or you're offline)", Toast.LENGTH_LONG).show()
                } else {
                    val info = JSONObject(json)
                    updateUrl = info.getString("url")
                    banner.text = "New app version ${info.getString("remote")} available — tap for details"
                    banner.visibility = View.VISIBLE
                    if (manual) showUpdateDialog(info)
                }
            }
        }
    }

    private fun showUpdateDialog(info: JSONObject?) {
        val url = updateUrl ?: return
        val title = if (info?.optString("state") == "incompatible") "Install the new app" else "App update available"
        val notes = info?.optString("notes").orEmpty()
        val message = (if (info != null) "${info.optString("title")}: ${info.optString("local")} → ${info.optString("remote")}\n\n" else "") +
            (if (notes.isNotEmpty()) "$notes\n\n" else "") +
            "This is a change to the app itself, so PythonOS can't update it for you. PythonOS itself keeps updating on its own.\n\n" +
            "Download the new APK and open it to install. If Android won't install it over this one, uninstall this app first " +
            "(use the backup command beforehand to keep your files)."
        AlertDialog.Builder(this, android.R.style.Theme_Material_Dialog_Alert)
            .setTitle(title)
            .setMessage(message)
            .setPositiveButton("Download") { _, _ -> startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
            .setNegativeButton("Later", null)
            .show()
    }

    // ----------------------------------------------------------------- Python
    private fun startPython() {
        if (started) return
        started = true
        TerminalBridge.reset()
        Thread({
            try {
                // The OS itself is downloaded into here on first launch (see pyos_android.py)
                val dir = File(filesDir, "pythonos").apply { mkdirs() }
                if (!Python.isStarted()) Python.start(AndroidPlatform(applicationContext))
                runOnUiThread { terminal.postDelayed({ checkAppUpdate(manual = false) }, 12000) }
                Python.getInstance().getModule("pyos_android").callAttr("main", dir.absolutePath)
            } catch (e: Throwable) {
                TerminalBridge.write("\u001b[31mPythonOS failed to start: $e\u001b[0m\n")
                TerminalBridge.finished()
            }
        }, "pythonos").start()
    }

    private fun callPython(name: String, vararg args: Any) {
        if (!Python.isStarted()) return
        worker.execute {
            try {
                Python.getInstance().getModule("pyos_android").callAttr(name, *args)
            } catch (e: Throwable) {
                // best effort
            }
        }
    }

    // ----------------------------------------------- TerminalView.Listener
    override fun onResize(cols: Int, rows: Int) {
        runOnUiThread { sizeLabel.text = "terminal  $cols x $rows" }
        callPython("set_size", cols, rows)
        startPython()
    }

    override fun onComplete(textBeforeCursor: String) {
        if (!Python.isStarted()) return
        worker.execute {
            val options = try {
                Python.getInstance().getModule("pyos_android").callAttr("complete", textBeforeCursor).asList().map { it.toString() }
            } catch (e: Throwable) {
                emptyList()
            }
            runOnUiThread { terminal.applyCompletions(textBeforeCursor, options) }
        }
    }

    override fun onInterrupt() {
        TerminalBridge.write("^C\n")
        if (TerminalBridge.waitingForInput) TerminalBridge.submit("\u0003")   // PythonOS turns this into a KeyboardInterrupt
        else callPython("interrupt")
    }

    override fun onLongPress() {
        showMenu(terminal)
    }

    override fun onTextSizeChanged(sp: Float) {
        prefs.edit().putFloat("text_size", sp).apply()
    }

    // ----------------------------------------------- TerminalBridge.Listener
    override fun onOutput() {
        terminal.onOutput()
    }

    override fun onPrompt(secret: Boolean) {
        runOnUiThread {
            terminal.setSecret(secret)
            terminal.showKeyboard()
        }
    }

    override fun onFinished() {
        // "shutdown" closes the app; the next launch boots the OS again
        started = false
        runOnUiThread { terminal.postDelayed({ if (!isFinishing) finishAndRemoveTask() }, 1500) }
    }

    companion object {
        @Volatile private var started = false
    }
}
