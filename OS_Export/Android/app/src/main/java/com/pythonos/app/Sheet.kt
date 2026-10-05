package com.pythonos.app

import android.app.Activity
import android.app.Dialog
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.view.WindowManager
import android.view.animation.DecelerateInterpolator
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView

/** The colours the app's own widgets use (set from the chosen palette). */
class SheetColors(val surface: Int, val chip: Int, val accent: Int, val text: Int, val muted: Int)

/**
 * A bottom sheet in the app's own style: rounded top corners, a grab handle, rows with a glyph, a title and a line of explanation,
 * switches, colour swatches, a text-size stepper. It replaces the stock popup menu and alert dialogs. Everything is built from
 * framework views, so there is nothing extra to download or to keep up to date. It slides up unless the system has animations off.
 */
class Sheet(private val activity: Activity, private val colors: SheetColors) {

    private val density = activity.resources.displayMetrics.density
    private fun dp(value: Int) = (value * density).toInt()
    private var dialog: Dialog? = null
    private val body = LinearLayout(activity).apply { orientation = LinearLayout.VERTICAL }

    private fun rounded(color: Int, radiusDp: Float) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = radiusDp * density
    }

    private fun ripple(shape: Drawable): Drawable =
        RippleDrawable(ColorStateList.valueOf(Color.argb(48, 255, 255, 255)), shape, null)

    private fun add(view: View, top: Int = 0, bottom: Int = 0) {
        body.addView(view, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            .apply { setMargins(0, dp(top), 0, dp(bottom)) })
    }

    private fun text(value: String, sizeSp: Float, color: Int, bold: Boolean = false) = TextView(activity).apply {
        text = value
        setTextColor(color)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp)
        if (bold) typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
    }

    // ------------------------------------------------------------------ content
    fun title(value: String, subtitle: String? = null) {
        add(text(value, 20f, colors.text, bold = true), top = 4)
        if (subtitle != null) add(text(subtitle, 13f, colors.muted), top = 2)
        add(View(activity), top = 8)
    }

    fun section(value: String) {
        add(text(value.uppercase(), 11f, colors.muted, bold = true), top = 14, bottom = 6)
    }

    fun paragraph(value: String) {
        add(text(value, 14f, colors.text).apply { setLineSpacing(0f, 1.15f) }, bottom = 6)
    }

    /** A tappable row: a round glyph, a title and an optional line under it. */
    fun row(glyph: String, title: String, subtitle: String? = null, onClick: () -> Unit) {
        val row = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(12), dp(10), dp(12), dp(10))
            background = ripple(rounded(colors.chip, 14f))
            isClickable = true
            setOnClickListener { dismiss(); onClick() }
        }
        row.addView(glyphBubble(glyph))
        val labels = LinearLayout(activity).apply { orientation = LinearLayout.VERTICAL }
        labels.addView(text(title, 15f, colors.text, bold = true))
        if (subtitle != null) labels.addView(text(subtitle, 12f, colors.muted))
        row.addView(labels, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply { setMargins(dp(12), 0, 0, 0) })
        add(row, bottom = 6)
    }

    fun toggle(glyph: String, title: String, subtitle: String?, checked: Boolean, onChange: (Boolean) -> Unit) {
        val row = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(12), dp(10), dp(12), dp(10))
            background = rounded(colors.chip, 14f)
        }
        row.addView(glyphBubble(glyph))
        val labels = LinearLayout(activity).apply { orientation = LinearLayout.VERTICAL }
        labels.addView(text(title, 15f, colors.text, bold = true))
        if (subtitle != null) labels.addView(text(subtitle, 12f, colors.muted))
        row.addView(labels, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply { setMargins(dp(12), 0, dp(8), 0) })
        val switch = Switch(activity).apply {
            isChecked = checked
            trackTintList = ColorStateList.valueOf(Color.argb(120, Color.red(colors.accent), Color.green(colors.accent), Color.blue(colors.accent)))
            thumbTintList = ColorStateList.valueOf(colors.accent)
            setOnCheckedChangeListener { _, on -> onChange(on) }
        }
        row.addView(switch)
        row.isClickable = true
        row.setOnClickListener { switch.toggle() }
        add(row, bottom = 6)
    }

    /** Round colour samples; tapping one calls onPick(index). The chosen one has a ring. */
    fun swatches(names: List<String>, samples: List<Int>, selected: Int, onPick: (Int) -> Unit) {
        val line = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL }
        for (i in names.indices) {
            val cell = LinearLayout(activity).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER_HORIZONTAL
                isClickable = true
                setOnClickListener { dismiss(); onPick(i) }
            }
            val dot = View(activity).apply {
                background = GradientDrawable().apply {
                    shape = GradientDrawable.OVAL
                    setColor(samples[i])
                    setStroke(dp(if (i == selected) 3 else 1), if (i == selected) colors.accent else Color.argb(90, 255, 255, 255))
                }
            }
            cell.addView(dot, LinearLayout.LayoutParams(dp(44), dp(44)))
            cell.addView(text(names[i], 12f, if (i == selected) colors.text else colors.muted), LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { setMargins(0, dp(4), 0, 0) })
            line.addView(cell, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        add(line, bottom = 6)
    }

    /** "Text size   A-  13  A+". `value` is read again after each tap so the number follows the change. */
    fun stepper(label: String, value: () -> String, onMinus: () -> Unit, onPlus: () -> Unit) {
        val row = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(14), dp(6), dp(8), dp(6))
            background = rounded(colors.chip, 14f)
        }
        row.addView(text(label, 15f, colors.text, bold = true), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val number = text(value(), 15f, colors.text).apply { gravity = Gravity.CENTER; minWidth = dp(40) }
        fun small(symbol: String, action: () -> Unit) = TextView(activity).apply {
            text = symbol
            gravity = Gravity.CENTER
            setTextColor(colors.accent)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f)
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            background = ripple(rounded(Color.TRANSPARENT, 20f))
            isClickable = true
            setOnClickListener { action(); number.text = value() }
        }
        row.addView(small("−", onMinus), LinearLayout.LayoutParams(dp(44), dp(44)))
        row.addView(number)
        row.addView(small("+", onPlus), LinearLayout.LayoutParams(dp(44), dp(44)))
        add(row, bottom = 6)
    }

    /** One or two buttons side by side. The first is the main action. */
    fun buttons(primary: String, onPrimary: () -> Unit, secondary: String? = null, onSecondary: () -> Unit = {}) {
        val line = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL }
        fun button(label: String, main: Boolean, action: () -> Unit) = TextView(activity).apply {
            text = label
            gravity = Gravity.CENTER
            setTextColor(if (main) Color.WHITE else colors.accent)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            background = ripple(GradientDrawable().apply {
                cornerRadius = 14f * density
                if (main) setColor(colors.accent) else { setColor(Color.TRANSPARENT); setStroke(dp(1), Color.argb(90, 255, 255, 255)) }
            })
            isClickable = true
            setOnClickListener { dismiss(); action() }
        }
        line.addView(button(primary, true, onPrimary), LinearLayout.LayoutParams(0, dp(48), 1f))
        if (secondary != null) {
            line.addView(button(secondary, false, onSecondary), LinearLayout.LayoutParams(0, dp(48), 1f).apply { setMargins(dp(10), 0, 0, 0) })
        }
        add(line, top = 10)
    }

    private fun glyphBubble(glyph: String) = TextView(activity).apply {
        text = glyph
        gravity = Gravity.CENTER
        setTextColor(colors.accent)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
        background = GradientDrawable().apply {
            shape = GradientDrawable.OVAL
            setColor(Color.argb(40, Color.red(colors.accent), Color.green(colors.accent), Color.blue(colors.accent)))
        }
        layoutParams = LinearLayout.LayoutParams(dp(40), dp(40))
    }

    // --------------------------------------------------------------- showing it
    private fun animationsOn(): Boolean = try {
        Settings.Global.getFloat(activity.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) > 0f
    } catch (e: Exception) {
        true
    }

    fun show() {
        val sheet = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(10), dp(16), dp(24))
            background = GradientDrawable().apply {
                setColor(colors.surface)
                val r = 24f * density
                cornerRadii = floatArrayOf(r, r, r, r, 0f, 0f, 0f, 0f)
            }
        }
        val handle = View(activity).apply { background = rounded(Color.argb(70, 255, 255, 255), 3f) }
        sheet.addView(handle, LinearLayout.LayoutParams(dp(40), dp(5)).apply { gravity = Gravity.CENTER_HORIZONTAL; setMargins(0, 0, 0, dp(10)) })
        val scroll = ScrollView(activity).apply { isVerticalScrollBarEnabled = false }
        scroll.addView(body)
        sheet.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))

        val d = Dialog(activity, android.R.style.Theme_Translucent_NoTitleBar)
        d.requestWindowFeature(Window.FEATURE_NO_TITLE)
        d.setContentView(sheet, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        d.setCanceledOnTouchOutside(true)
        d.window?.apply {
            setBackgroundDrawable(ColorDrawable(Color.TRANSPARENT))
            setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            setGravity(Gravity.BOTTOM)
            addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND)
            attributes = attributes.also { it.dimAmount = 0.55f }
        }
        dialog = d
        d.show()
        if (animationsOn()) {
            sheet.translationY = dp(420).toFloat()
            sheet.alpha = 0.6f
            sheet.animate().translationY(0f).alpha(1f).setDuration(240).setInterpolator(DecelerateInterpolator()).start()
        }
    }

    fun dismiss() {
        try {
            dialog?.dismiss()
        } catch (e: Exception) {
            // the activity may already be going away
        }
        dialog = null
    }
}
