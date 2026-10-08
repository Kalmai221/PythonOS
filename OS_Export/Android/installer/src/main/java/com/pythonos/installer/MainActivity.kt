package com.pythonos.installer

import android.app.Activity
import android.app.AlertDialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.os.SystemClock
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.io.File
import java.util.concurrent.Executors

/**
 * The installer screen: what is installed, what is the latest, one button for the next step, the steps while it works, and a few
 * tools (other versions, what is new, uninstall, copy details for a bug report). Colours follow the system's light or dark setting.
 */
class MainActivity : Activity() {
    private class Palette(night: Boolean, system: Int? = null) {
        val bg = if (night) Color.rgb(19, 19, 18) else Color.rgb(250, 249, 246)
        val card = if (night) Color.rgb(27, 27, 25) else Color.WHITE
        val text = if (night) Color.rgb(232, 230, 224) else Color.rgb(29, 28, 26)
        val muted = if (night) Color.rgb(160, 156, 146) else Color.rgb(102, 99, 92)
        val line = if (night) Color.rgb(52, 51, 46) else Color.rgb(222, 219, 211)
        val accent = system ?: if (night) Color.rgb(111, 193, 156) else Color.rgb(28, 107, 82)
        val onAccent = if (night) Color.rgb(13, 31, 23) else Color.WHITE
        val good = if (night) Color.rgb(98, 196, 138) else Color.rgb(27, 122, 71)
        val bad = if (night) Color.rgb(240, 138, 128) else Color.rgb(179, 38, 30)
    }

    /** A flat rounded progress bar in the accent colour, like the one in the Windows installer. */
    private class Meter(context: Context, private val track: Int, private val fill: Int) : View(context) {
        var progress = 0
            set(value) { field = value.coerceIn(0, 1000); invalidate() }
        private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        override fun onDraw(canvas: Canvas) {
            val r = height / 2f
            paint.color = track
            canvas.drawRoundRect(RectF(0f, 0f, width.toFloat(), height.toFloat()), r, r, paint)
            if (progress > 0) {
                paint.color = fill
                canvas.drawRoundRect(RectF(0f, 0f, maxOf(height.toFloat(), width * progress / 1000f), height.toFloat()), r, r, paint)
            }
        }
    }

    private lateinit var p: Palette
    private lateinit var journey: TextView
    private lateinit var statusTitle: TextView
    private lateinit var statusDetail: TextView
    private lateinit var deviceLine: TextView
    private lateinit var stepsBox: LinearLayout
    private val stepViews = ArrayList<TextView>()
    private lateinit var bar: Meter
    private lateinit var barText: TextView
    private lateinit var primary: Button
    private lateinit var open: Button
    private lateinit var news: Button
    private lateinit var other: Button
    private lateinit var uninstall: Button
    private lateinit var copy: Button
    private lateinit var notes: TextView
    private val worker = Executors.newSingleThreadExecutor()
    private val stepNames = listOf("Check this device", "Find the version", "Download", "Check the download", "Install")

    private var busy = false
    private var installed: String? = null
    private var latest: Installer.Release? = null
    private var lastProblem: String? = null
    private var justInstalled = false          // the install just finished: show the success part until the next check or install

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()

    private fun rounded(fill: Int, radiusDp: Int, stroke: Int = 0): GradientDrawable = GradientDrawable().apply {
        cornerRadius = dp(radiusDp).toFloat()
        setColor(fill)
        if (stroke != 0) setStroke(dp(1), stroke)
    }

    private fun label(size: Float, color: Int, bold: Boolean = false) = TextView(this).apply {
        setTextSize(TypedValue.COMPLEX_UNIT_SP, size)
        setTextColor(color)
        if (bold) typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        setLineSpacing(0f, 1.15f)
    }

    private fun style(button: Button, filled: Boolean) {
        button.isAllCaps = false
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
        button.typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        button.setTextColor(if (filled) p.onAccent else p.text)
        button.background = if (filled) rounded(p.accent, 10) else rounded(p.card, 10, p.line)
        button.stateListAnimator = null
    }

    private fun card(): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        background = rounded(p.card, 12, p.line)
        setPadding(dp(16), dp(14), dp(16), dp(14))
    }

    @Suppress("DEPRECATION")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val night = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        // Android 12+ lends us the phone's own accent colour so the installer matches the rest of the system
        val system = if (android.os.Build.VERSION.SDK_INT >= 31) try { getColor(if (night) android.R.color.system_accent1_200 else android.R.color.system_accent1_600) } catch (e: Exception) { null } else null
        p = Palette(night, system)
        window.setBackgroundDrawable(ColorDrawable(p.bg))
        window.statusBarColor = p.bg
        window.navigationBarColor = p.bg
        if (!night) window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR

        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(26), dp(20), dp(24))
        }

        // header: a small mark, the name, what this is
        val header = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        val mark = TextView(this).apply {
            text = ">_"
            gravity = Gravity.CENTER
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f)
            setTextColor(p.onAccent)
            typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
            background = rounded(p.accent, 14)
        }
        header.addView(mark, LinearLayout.LayoutParams(dp(52), dp(52)))
        val names = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        names.addView(label(24f, p.text, true).apply { text = "PythonOS Setup" })
        names.addView(label(14f, p.muted).apply { text = "Install and update the app" })
        header.addView(names, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(14) })
        column.addView(header, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(16) })
        journey = label(13f, p.muted)
        column.addView(journey, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(16) })

        // status card
        val status = card()
        statusTitle = label(20f, p.text, true)
        statusDetail = label(15f, p.muted)
        deviceLine = label(13f, p.muted)
        status.addView(statusTitle)
        status.addView(statusDetail, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(4) })
        status.addView(deviceLine, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
        column.addView(status, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(14) })

        // steps, shown while it works
        stepsBox = card()
        for (name in stepNames) {
            val row = label(15f, p.muted)
            stepViews.add(row)
            stepsBox.addView(row, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(3); bottomMargin = dp(3) })
        }
        bar = Meter(this, p.line, p.accent)
        barText = label(13f, p.muted)
        stepsBox.addView(bar, LinearLayout.LayoutParams(-1, dp(8)).apply { topMargin = dp(10) })
        stepsBox.addView(barText, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(6) })
        stepsBox.visibility = View.GONE
        column.addView(stepsBox, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(14) })

        // the next step
        primary = Button(this)
        style(primary, true)
        primary.setOnClickListener { onPrimary() }
        column.addView(primary, LinearLayout.LayoutParams(-1, dp(52)))

        // tools
        open = Button(this).apply { text = "Open PythonOS"; setOnClickListener { openApp() } }
        news = Button(this).apply { text = "What is new"; setOnClickListener { toggleNotes() } }
        other = Button(this).apply { text = "Other versions"; setOnClickListener { pickVersion() } }
        uninstall = Button(this).apply { text = "Uninstall"; setOnClickListener { confirmUninstall() } }
        copy = Button(this).apply { text = "Copy details"; setOnClickListener { copyDetails() } }
        for (b in listOf(open, news, other, uninstall, copy)) style(b, false)
        val rowOne = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        rowOne.addView(open, LinearLayout.LayoutParams(0, dp(46), 1f).apply { rightMargin = dp(6) })
        rowOne.addView(news, LinearLayout.LayoutParams(0, dp(46), 1f).apply { leftMargin = dp(6) })
        val rowTwo = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        rowTwo.addView(other, LinearLayout.LayoutParams(0, dp(46), 1f).apply { rightMargin = dp(6) })
        rowTwo.addView(uninstall, LinearLayout.LayoutParams(0, dp(46), 1f).apply { leftMargin = dp(6) })
        column.addView(rowOne, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
        column.addView(rowTwo, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
        column.addView(copy, LinearLayout.LayoutParams(-1, dp(46)).apply { topMargin = dp(10) })

        notes = label(14f, p.text).apply {
            background = rounded(p.card, 12, p.line)
            setPadding(dp(16), dp(14), dp(16), dp(14))
            visibility = View.GONE
            setOnClickListener { latest?.let { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(it.page))) } }
        }
        column.addView(notes, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(14) })

        val footer = label(12f, p.muted).apply {
            text = "Downloads come from github.com/Kalmai221/PythonOS and are checked against the release's SHA-256 checksums before Android is asked to install them. The file is kept until it is installed."
        }
        column.addView(footer, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(22) })

        setContentView(ScrollView(this).apply { setBackgroundColor(p.bg); isFillViewport = true; addView(column) })
        Installer.onResult = { ok, message -> runOnUiThread { installFinished(ok, message) } }
        for (i in stepNames.indices) setStep(i, 0)
    }

    override fun onDestroy() {
        Installer.onResult = null
        super.onDestroy()
    }

    override fun onResume() {
        super.onResume()
        installed = installedVersion()
        Installer.cleanStale(this, installed)
        if (!busy) {
            render()
            if (latest == null) check()
        }
    }

    // ------------------------------------------------------------------------------------------------ state
    private fun installedVersion(): String? = try {
        packageManager.getPackageInfo(Installer.TARGET, 0).versionName
    } catch (e: PackageManager.NameNotFoundException) {
        null
    }

    private fun mb(bytes: Long): String = String.format("%.1f MB", bytes / 1048576.0)

    /** The three stages as dots, the way the Windows installer shows them: where you are is filled in. */
    private fun showJourney(stage: Int) {
        val names = listOf("Check", "Install", "Done")
        val text = SpannableStringBuilder()
        for ((i, name) in names.withIndex()) {
            if (i > 0) text.append("   ")
            val start = text.length
            text.append(if (i <= stage) "●  " else "○  ").append(name)
            text.setSpan(ForegroundColorSpan(if (i == stage) p.accent else if (i < stage) p.text else p.muted), start, text.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
        journey.text = text
    }

    private fun render() {
        showJourney(if (justInstalled) 2 else if (busy) 1 else 0)
        val abi = Installer.abi()
        val summary = StringBuilder("Device       Android ${android.os.Build.VERSION.RELEASE}, " + (abi ?: "32-bit processor"))
        installed?.let { summary.append("\nInstalled    ").append(it) }
        latest?.let { summary.append("\nLatest       ").append(it.version).append(if (it.size > 0) "  (" + mb(it.size) + ")" else "") }
        deviceLine.text = summary
        deviceLine.typeface = Typeface.MONOSPACE
        open.visibility = if (installed != null) View.VISIBLE else View.GONE
        uninstall.visibility = if (installed != null) View.VISIBLE else View.GONE
        if (justInstalled && installed != null) {
            news.visibility = View.GONE
            statusTitle.text = "✓  PythonOS $installed was installed successfully"
            statusTitle.setTextColor(p.good)
            statusDetail.text = "It is ready to use. Open it now, or find PythonOS in your app list. Type help inside it to get started, and updatecheck to update it later. The downloaded file has been removed to free the space."
            primary.text = "Open PythonOS"
            style(primary, true)
            return
        }
        statusTitle.setTextColor(p.text)
        val release = latest
        news.visibility = if (release != null) View.VISIBLE else View.GONE
        other.visibility = if (abi != null) View.VISIBLE else View.GONE
        primary.isEnabled = !busy
        primary.visibility = View.VISIBLE
        if (abi == null) {
            statusTitle.text = "Not available on this device"
            statusDetail.text = "This device has a 32-bit processor, which the PythonOS app does not support yet."
            primary.visibility = View.GONE
            return
        }
        if (release == null) {
            statusTitle.text = if (installed == null) "PythonOS is not installed" else "PythonOS $installed is installed"
            statusDetail.text = lastProblem ?: "Looking for the latest version..."
            primary.text = "Check again"
            style(primary, lastProblem != null)
            return
        }
        val size = if (release.size > 0) ", ${mb(release.size)}" else ""
        val have = installed
        when {
            have == null -> {
                statusTitle.text = "PythonOS is not installed"
                statusDetail.text = "The latest version is ${release.version} (released ${release.published}$size)."
                primary.text = "Install PythonOS ${release.version}"
                style(primary, true)
            }
            Installer.compare(have, release.appVersion) < 0 -> {
                statusTitle.text = "An update is available"
                statusDetail.text = "You have the app $have. The latest app is ${release.appVersion} (released ${release.published}$size). PythonOS also updates itself from inside with updatecheck."
                primary.text = "Update the app to ${release.appVersion}"
                style(primary, true)
            }
            Installer.compare(have, release.appVersion) == 0 -> {
                statusTitle.text = "The app is up to date"
                statusDetail.text = if (Installer.compare(release.appVersion, release.version) < 0)
                    "You have the latest app ($have). The newest release, ${release.version}, only changed PythonOS itself, and that updates from inside: open PythonOS and type updatecheck. There is nothing to install here."
                else
                    "You have the latest version, ${release.version}."
                primary.text = if (Installer.compare(release.appVersion, release.version) < 0) "Open PythonOS" else "Check again"
                style(primary, Installer.compare(release.appVersion, release.version) < 0)
            }
            else -> {
                statusTitle.text = "The app is up to date"
                statusDetail.text = "You have $have, which is newer than the latest release's app (${release.appVersion})."
                primary.text = "Check again"
                style(primary, false)
            }
        }
    }

    private fun check() {
        val abi = Installer.abi() ?: return
        justInstalled = false
        lastProblem = null
        statusDetail.text = "Looking for the latest version..."
        worker.execute {
            try {
                val release = Installer.latest(abi)
                runOnUiThread { latest = release; lastProblem = null; render() }
            } catch (e: Exception) {
                runOnUiThread { lastProblem = "Could not check for the latest version: ${e.message ?: e.toString()}"; latest = null; render() }
            }
        }
    }

    private fun onPrimary() {
        if (justInstalled && installed != null) { openApp(); return }
        val release = latest
        val have = installed
        if (release != null && have != null && Installer.compare(have, release.appVersion) == 0 && Installer.compare(release.appVersion, release.version) < 0) {
            openApp()                                    // the app is current; the newer release is PythonOS itself, which updates from inside
            return
        }
        if (release == null || (have != null && Installer.compare(have, release.appVersion) >= 0)) {
            latest = null
            check()
            return
        }
        run(release)
    }

    // ------------------------------------------------------------------------------------------------ installing
    private fun setStep(index: Int, state: Int) {
        val marker = when (state) { 1 -> "●"; 2 -> "✓"; 3 -> "✕"; else -> "○" }
        val color = when (state) { 1 -> p.text; 2 -> p.good; 3 -> p.bad; else -> p.muted }
        stepViews[index].text = "$marker  ${stepNames[index]}"
        stepViews[index].setTextColor(color)
    }

    private fun run(release: Installer.Release) {
        justInstalled = false
        if (!Installer.canInstall(this)) {
            AlertDialog.Builder(this)
                .setTitle("Allow installing apps")
                .setMessage("Android needs your permission before this app can install PythonOS. On the next screen, switch on \"Allow from this source\", then come back here.")
                .setPositiveButton("Open settings") { _, _ -> startActivity(Installer.allowIntent(this)) }
                .setNegativeButton("Not now", null)
                .show()
            return
        }
        if (Installer.metered(this) && release.size > 0) {
            AlertDialog.Builder(this)
                .setTitle("Use mobile data?")
                .setMessage("This download is ${mb(release.size)} and you are not on an unlimited connection. Download it now?")
                .setPositiveButton("Download") { _, _ -> work(release) }
                .setNegativeButton("Wait for Wi-Fi", null)
                .show()
            return
        }
        work(release)
    }

    private fun work(release: Installer.Release) {
        busy = true
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)          // the screen stays on while it downloads
        lastProblem = null
        primary.isEnabled = false
        stepsBox.visibility = View.VISIBLE
        for (i in stepNames.indices) setStep(i, 0)
        bar.progress = 0
        barText.text = ""
        showJourney(1)
        statusTitle.text = "Installing ${release.version}"
        statusDetail.text = "Keep this screen open until Android asks you to confirm."
        setStep(0, 2)
        setStep(1, 1)
        worker.execute {
            var step = 1
            try {
                Installer.checksum(release)
                runOnUiThread { setStep(1, 2); setStep(2, 1) }
                step = 2
                val started = SystemClock.elapsedRealtime()
                var first = -1L
                val apk: File = Installer.download(this, release) { done, total ->
                    if (first < 0) first = done
                    val seconds = (SystemClock.elapsedRealtime() - started) / 1000.0
                    val speed = if (seconds > 0.5) (done - first) / seconds else 0.0
                    val text = if (total > 0) "${mb(done)} of ${mb(total)}" + (if (speed > 0) String.format("  ·  %.1f MB/s", speed / 1048576.0) else "") + (if (speed > 0 && total > done) String.format("  ·  %d s left", ((total - done) / speed).toLong() + 1) else "") else mb(done)
                    runOnUiThread { bar.progress = if (total > 0) (done * 1000 / total).toInt() else 0; barText.text = text }
                }
                step = 3
                runOnUiThread { setStep(2, 2); setStep(3, 2); setStep(4, 1); bar.progress = 1000; barText.text = "Downloaded and checked (SHA-256 ${release.sha256.take(12)}...). Confirm the installation in the window Android shows." }
                step = 4
                Installer.install(this, apk)
            } catch (e: Exception) {
                val why = e.message ?: e.toString()
                runOnUiThread {
                    window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    setStep(step, 3); showJourney(0)
                    busy = false
                    lastProblem = "Not installed: $why"
                    statusTitle.text = "That did not work"
                    statusDetail.text = lastProblem ?: ""
                    primary.isEnabled = true
                    primary.text = "Try again"
                    style(primary, true)
                }
            }
        }
    }

    private fun installFinished(ok: Boolean, message: String) {
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        busy = false
        installed = installedVersion()
        if (ok) {
            Installer.cleanup(this)                       // the downloaded file is only removed once PythonOS is installed
            for (i in stepNames.indices) setStep(i, 2)
            barText.text = "The downloaded file has been removed."
            justInstalled = true
            lastProblem = null
            render()
            Toast.makeText(this, "PythonOS is installed.", Toast.LENGTH_LONG).show()
        } else {
            setStep(4, 3)
            lastProblem = message
            primary.isEnabled = true
            render()
            statusTitle.text = "That did not work"
            statusDetail.text = message + "\nThe downloaded file is kept, so trying again does not download it again."
            primary.text = "Try again"
            style(primary, true)
        }
    }

    // ------------------------------------------------------------------------------------------------ the tools
    private fun openApp() {
        val intent = packageManager.getLaunchIntentForPackage(Installer.TARGET)
        if (intent != null) startActivity(intent) else Toast.makeText(this, "PythonOS is not installed.", Toast.LENGTH_SHORT).show()
    }

    private fun toggleNotes() {
        if (notes.visibility == View.VISIBLE) {
            notes.visibility = View.GONE
            return
        }
        val release = latest ?: return
        val text = if (release.notes.isNotEmpty()) release.notes else "No release notes."
        notes.text = Markdown.render("## What is new in ${release.version}\n\n$text\n\nTap to open the full release page.", p.line)
        notes.visibility = View.VISIBLE
    }

    private fun pickVersion() {
        val abi = Installer.abi() ?: return
        Toast.makeText(this, "Looking up versions...", Toast.LENGTH_SHORT).show()
        worker.execute {
            try {
                val list = Installer.recent(abi)
                runOnUiThread {
                    if (list.isEmpty()) {
                        Toast.makeText(this, "No versions found.", Toast.LENGTH_LONG).show()
                        return@runOnUiThread
                    }
                    val names = list.map { it.version + "  ·  " + it.published + (if (it.size > 0) "  ·  " + mb(it.size) else "") }.toTypedArray()
                    AlertDialog.Builder(this)
                        .setTitle("Install a version")
                        .setItems(names) { _, which -> chooseOlder(list[which]) }
                        .setNegativeButton("Cancel", null)
                        .show()
                }
            } catch (e: Exception) {
                runOnUiThread { Toast.makeText(this, "Could not list versions: ${e.message ?: e.toString()}", Toast.LENGTH_LONG).show() }
            }
        }
    }

    private fun chooseOlder(release: Installer.Release) {
        val have = installed
        if (have != null && Installer.compare(have, release.appVersion) > 0) {
            AlertDialog.Builder(this)
                .setTitle("Install an older version?")
                .setMessage("You have $have. Android refuses to install an older version over a newer one. If it does, uninstall PythonOS first (back up your files with the backup command inside PythonOS), then install again.")
                .setPositiveButton("Try anyway") { _, _ -> run(release) }
                .setNegativeButton("Cancel", null)
                .show()
        } else {
            run(release)
        }
    }

    private fun confirmUninstall() {
        AlertDialog.Builder(this)
            .setTitle("Uninstall PythonOS?")
            .setMessage("This removes PythonOS and everything stored inside it (accounts, files, settings) from this device. Back up first with the backup command inside PythonOS.")
            .setPositiveButton("Uninstall") { _, _ -> startActivity(Installer.uninstallIntent()) }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun copyDetails() {
        val text = Installer.details(this, installed, latest) + (lastProblem?.let { "\nLast problem: $it" } ?: "")
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("PythonOS Installer", text))
        Toast.makeText(this, "Details copied. Paste them into a bug report.", Toast.LENGTH_LONG).show()
    }
}
