package com.pythonos.installer

import android.graphics.Typeface
import android.text.Spannable
import android.text.SpannableStringBuilder
import android.text.style.BackgroundColorSpan
import android.text.style.RelativeSizeSpan
import android.text.style.StyleSpan
import android.text.style.TypefaceSpan

/**
 * Shows the Markdown of a release's "What's new" as styled text: headings, bullets, numbered lists, **bold**, `code`, quotes, code blocks and
 * rules. Links show their text only (a screen full of web addresses helps nobody). Anything it does not know is shown as it is written, so
 * unusual text never disappears. The colours of the text itself come from the TextView; only the code background is given here.
 * (The same file is in the app module, in its own package.)
 */
object Markdown {
    private val HEADING = Regex("^(#{1,6})\\s+(.*)$")
    private val BULLET = Regex("^[-*+]\\s+(.*)$")
    private val NUMBERED = Regex("^(\\d+)[.)]\\s+(.*)$")
    private val QUOTE = Regex("^>\\s?(.*)$")
    private val RULE = Regex("^(-{3,}|\\*{3,}|_{3,})$")
    private val LINK = Regex("\\[([^\\]]+)\\]\\([^)]*\\)")

    fun render(source: String, codeBackground: Int): CharSequence {
        val out = SpannableStringBuilder()
        var inFence = false
        var blank = false
        for (raw in source.replace("\r\n", "\n").lines()) {
            val line = raw.trimEnd()
            val trimmed = line.trimStart()
            if (trimmed.startsWith("```")) {
                inFence = !inFence
                continue
            }
            if (inFence) {
                val start = out.length
                out.append(line).append("\n")
                out.setSpan(TypefaceSpan("monospace"), start, out.length, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                out.setSpan(BackgroundColorSpan(codeBackground), start, out.length, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                continue
            }
            if (trimmed.isEmpty()) {
                blank = out.isNotEmpty()
                continue
            }
            if (blank) {
                out.append("\n")
                blank = false
            }
            val indent = "  ".repeat((line.length - trimmed.length) / 2)
            val heading = HEADING.find(trimmed)
            val bullet = BULLET.find(trimmed)
            val numbered = NUMBERED.find(trimmed)
            val quote = QUOTE.find(trimmed)
            when {
                heading != null -> {
                    val size = when (heading.groupValues[1].length) { 1 -> 1.35f; 2 -> 1.2f; 3 -> 1.08f; else -> 1.0f }
                    val start = out.length
                    inline(out, heading.groupValues[2], true, codeBackground)
                    out.setSpan(RelativeSizeSpan(size), start, out.length, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                    out.append("\n")
                }
                bullet != null -> {
                    out.append(indent).append("•  ")
                    inline(out, bullet.groupValues[1], false, codeBackground)
                    out.append("\n")
                }
                numbered != null -> {
                    out.append(indent).append(numbered.groupValues[1]).append(".  ")
                    inline(out, numbered.groupValues[2], false, codeBackground)
                    out.append("\n")
                }
                quote != null -> {
                    val start = out.length
                    out.append("┃ ")
                    inline(out, quote.groupValues[1], false, codeBackground)
                    out.setSpan(StyleSpan(Typeface.ITALIC), start, out.length, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                    out.append("\n")
                }
                RULE.matches(trimmed) -> out.append("─".repeat(24)).append("\n")
                else -> {
                    inline(out, trimmed, false, codeBackground)
                    out.append("\n")
                }
            }
        }
        if (out.isNotEmpty() && out[out.length - 1] == '\n') out.delete(out.length - 1, out.length)
        return out
    }

    /** One line of text with **bold** and `code` applied. [bold] makes the whole line bold (headings). */
    private fun inline(out: SpannableStringBuilder, text: String, bold: Boolean, codeBackground: Int) {
        val plain = LINK.replace(text) { it.groupValues[1] }
        var strong = bold
        var code = false
        val buffer = StringBuilder()
        fun flush() {
            if (buffer.isEmpty()) return
            val start = out.length
            out.append(buffer.toString())
            if (strong) out.setSpan(StyleSpan(Typeface.BOLD), start, out.length, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
            if (code) {
                out.setSpan(TypefaceSpan("monospace"), start, out.length, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                out.setSpan(BackgroundColorSpan(codeBackground), start, out.length, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
            buffer.setLength(0)
        }
        var i = 0
        while (i < plain.length) {
            if (!code && plain.startsWith("**", i)) {
                flush()
                strong = if (bold) true else !strong
                i += 2
                continue
            }
            if (plain[i] == '`') {
                flush()
                code = !code
                i += 1
                continue
            }
            buffer.append(plain[i])
            i += 1
        }
        flush()
    }
}
