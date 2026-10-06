package com.pythonos.installer

import android.app.Activity
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import java.util.concurrent.Executors

/** One screen: what this installs, one button, a progress bar. */
class MainActivity : Activity() {
    private lateinit var headline: TextView
    private lateinit var detail: TextView
    private lateinit var bar: ProgressBar
    private lateinit var install: Button
    private lateinit var open: Button
    private val worker = Executors.newSingleThreadExecutor()
    private var busy = false

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()

    private fun styled(button: Button, filled: Boolean) {
        button.isAllCaps = false
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
        button.setTextColor(if (filled) Color.WHITE else Color.rgb(122, 162, 247))
        button.typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        button.background = GradientDrawable().apply {
            cornerRadius = dp(14).toFloat()
            if (filled) setColor(Color.rgb(59, 120, 255)) else { setColor(Color.TRANSPARENT); setStroke(dp(1), Color.argb(110, 255, 255, 255)) }
        }
        button.stateListAnimator = null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setBackgroundColor(Color.rgb(12, 12, 12))
            setPadding(dp(28), dp(24), dp(28), dp(24))
        }
        val mark = TextView(this).apply {
            text = ">_"
            setTextColor(Color.rgb(79, 227, 193))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 44f)
            typeface = Typeface.MONOSPACE
        }
        headline = TextView(this).apply {
            text = "PythonOS"
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 30f)
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        }
        detail = TextView(this).apply {
            setTextColor(Color.rgb(170, 176, 190))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            setLineSpacing(0f, 1.2f)
        }
        bar = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = 100
            visibility = View.INVISIBLE
        }
        install = Button(this)
        open = Button(this)
        styled(install, true)
        styled(open, false)
        open.text = "Open PythonOS"
        open.setOnClickListener {
            packageManager.getLaunchIntentForPackage(Installer.TARGET)?.let { startActivity(it) }
        }
        install.setOnClickListener { start() }

        root.addView(mark)
        root.addView(headline, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(4) })
        root.addView(detail, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10); bottomMargin = dp(26) })
        root.addView(bar, LinearLayout.LayoutParams(-1, dp(8)).apply { bottomMargin = dp(18) })
        root.addView(install, LinearLayout.LayoutParams(-1, dp(54)))
        root.addView(open, LinearLayout.LayoutParams(-1, dp(54)).apply { topMargin = dp(12) })
        setContentView(root)
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    private fun installedVersion(): String? = try {
        packageManager.getPackageInfo(Installer.TARGET, 0).versionName
    } catch (e: PackageManager.NameNotFoundException) {
        null
    }

    private fun refresh() {
        if (busy) return
        val current = installedVersion()
        val abi = Installer.abi()
        bar.visibility = View.INVISIBLE
        open.visibility = if (current != null) View.VISIBLE else View.GONE
        if (abi == null) {
            detail.text = "This device has a 32-bit processor, which the PythonOS app does not support yet."
            install.visibility = View.GONE
            return
        }
        install.visibility = View.VISIBLE
        install.isEnabled = true
        if (current == null) {
            detail.text = "Installs the latest PythonOS for this device ($abi). It is downloaded from GitHub and checked before Android is asked to install it."
            install.text = "Install PythonOS"
        } else {
            detail.text = "PythonOS $current is installed. You can check for a newer version; PythonOS also updates itself from inside."
            install.text = "Check for an update"
        }
    }

    private fun start() {
        val abi = Installer.abi() ?: return
        busy = true
        install.isEnabled = false
        bar.progress = 0
        bar.visibility = View.VISIBLE
        say("Looking up the latest version...")
        worker.execute {
            try {
                val release = Installer.latest(abi)
                val installed = installedVersion()
                if (installed != null && installed == release.tag.removePrefix("v")) {
                    done("PythonOS $installed is the latest version.")
                    return@execute
                }
                say("Downloading ${release.tag}...")
                val apk = Installer.download(this, release) { percent -> runOnUiThread { bar.progress = percent; detail.text = "Downloading ${release.tag}... $percent%" } }
                say("Checked. Android will now ask you to confirm.")
                Installer.install(this, apk)
                done("Confirm the installation in the window Android shows.")
            } catch (e: Exception) {
                done("Not installed: ${e.message ?: e.toString()}")
            }
        }
    }

    private fun say(text: String) = runOnUiThread { detail.text = text }

    private fun done(text: String) = runOnUiThread {
        busy = false
        detail.text = text
        bar.visibility = View.INVISIBLE
        install.isEnabled = true
        open.visibility = if (installedVersion() != null) View.VISIBLE else View.GONE
    }
}
