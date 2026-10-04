package com.pythonos.app

import android.content.Context
import android.content.res.AssetManager
import java.io.File

/**
 * PythonOS reads and writes files relative to its working directory, so the OS is copied
 * out of the APK's assets into the app's private storage on first launch (and after an
 * app update). Users' files, accounts and settings live there too and survive updates.
 */
object PayloadInstaller {
    private val CODE_DIRS = listOf("commands", "core", "programs", "pyos")
    private val KEEP_IF_EXISTS = setOf("config.json")

    fun install(context: Context): File {
        val target = File(context.filesDir, "pythonos")
        val prefs = context.getSharedPreferences("payload", Context.MODE_PRIVATE)
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        val version = "${info.versionName}-${info.lastUpdateTime}"

        if (prefs.getString("version", null) != version || !File(target, "main.py").exists()) {
            target.mkdirs()
            for (dir in CODE_DIRS) File(target, dir).deleteRecursively()
            copy(context.assets, "pythonos", target)
            prefs.edit().putString("version", version).apply()
        }
        return target
    }

    private fun copy(assets: AssetManager, assetPath: String, dest: File) {
        val children = assets.list(assetPath)
        if (children.isNullOrEmpty()) {
            if (dest.name in KEEP_IF_EXISTS && dest.exists()) return
            dest.parentFile?.mkdirs()
            assets.open(assetPath).use { input -> dest.outputStream().use { input.copyTo(it) } }
        } else {
            dest.mkdirs()
            for (child in children) copy(assets, "$assetPath/$child", File(dest, child))
        }
    }
}
