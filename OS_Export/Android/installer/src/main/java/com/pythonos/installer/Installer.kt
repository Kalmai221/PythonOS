package com.pythonos.installer

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.net.ConnectivityManager
import android.net.Uri
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * What the installer does: find the right PythonOS APK for this device, download it (and carry on where it stopped if the connection drops),
 * check it against the release's checksums, hand it to Android's installer, and report how that went.
 */
object Installer {
    const val TARGET = "com.pythonos.app"
    private const val REPO = "Kalmai221/PythonOS"
    private const val API = "https://api.github.com/repos/$REPO/releases"
    private const val ACTION = "com.pythonos.installer.INSTALL_RESULT"

    /** One release that has an app for this device. [sha256] stays empty until [checksum] has looked it up. */
    class Release(
        val tag: String,
        val apkName: String,
        val url: String,
        val sumsUrl: String,
        val size: Long,
        val notes: String,
        val page: String,
        val published: String,
        var sha256: String = ""
    ) {
        /** The release's version (its tag): what PythonOS itself is called, because the core updates from inside the app. */
        val version: String get() = tag.removePrefix("v")

        /**
         * The version of the app file this release carries, read from its file name (PythonOS-1.0.8-android-arm64-v8a.apk). A release does not
         * rebuild an app that did not change, so it can carry the app of an older release: installing it gives that older app's version, never
         * the release's. Comparing the installed app with [version] would offer the same file for ever.
         */
        val appVersion: String
            get() = Regex("^PythonOS-([0-9][0-9A-Za-z.\\-]*?)-android-").find(apkName)?.groupValues?.get(1) ?: version
    }

    /** Set by the screen that is showing: called (on a background thread) when Android reports how the installation ended. */
    @Volatile
    var onResult: ((Boolean, String) -> Unit)? = null

    /** The processor of this device in the names the APKs use, or null when there is no APK for it (32-bit devices). */
    fun abi(): String? {
        for (candidate in Build.SUPPORTED_ABIS) {
            if (candidate == "arm64-v8a" || candidate == "x86_64") return candidate
        }
        return null
    }

    private fun open(url: String): HttpURLConnection {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.connectTimeout = 15000
        connection.readTimeout = 30000
        connection.instanceFollowRedirects = true
        connection.setRequestProperty("User-Agent", "PythonOS-Installer")
        connection.setRequestProperty("Accept", "application/vnd.github+json")
        return connection
    }

    private fun text(url: String): String {
        val connection = open(url)
        try {
            if (connection.responseCode !in 200..299) throw IOException("could not reach GitHub (HTTP ${connection.responseCode})")
            return connection.inputStream.bufferedReader().use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }

    /** The part of a release's text under "What's new" (up to 80 lines), as the Markdown it was written in. */
    fun whatsNew(body: String): String {
        val lines = body.lines()
        val start = lines.indexOfFirst { it.trim().startsWith("## ") && it.contains("What", ignoreCase = true) }
        val out = ArrayList<String>()
        for (i in start + 1 until lines.size) {
            val line = lines[i].trimEnd()
            if (start >= 0 && line.trim().startsWith("## ")) break
            out.add(line)
            if (out.size >= 80) break
        }
        return out.joinToString("\n").trim()                // still Markdown: the screen shows it styled (Markdown.kt)
    }

    /** The release for [abi] in one GitHub release object, or null when it has no app for that processor or no checksums. */
    private fun release(json: JSONObject, abi: String): Release? {
        val assets = json.getJSONArray("assets")
        var apk: JSONObject? = null
        var sums: String? = null
        for (i in 0 until assets.length()) {
            val asset = assets.getJSONObject(i)
            val name = asset.getString("name")
            if (name.endsWith("-android-$abi.apk")) apk = asset
            if (name == "SHA256SUMS") sums = asset.getString("browser_download_url")
        }
        if (apk == null || sums == null) return null
        return Release(
            json.getString("tag_name"), apk.getString("name"), apk.getString("browser_download_url"), sums, apk.optLong("size"),
            whatsNew(json.optString("body", "")), json.optString("html_url", "https://github.com/$REPO/releases"), json.optString("published_at", "").take(10)
        )
    }

    /** The latest release's app for [abi]. */
    fun latest(abi: String): Release {
        val found = release(JSONObject(text("$API/latest")), abi)
        return found ?: throw IOException("the latest release has no app for this device ($abi), or no checksums to check it with")
    }

    /** The newest few releases that have an app for [abi], newest first (for installing an older version). */
    fun recent(abi: String, limit: Int = 8): List<Release> {
        val list = JSONArray(text("$API?per_page=20"))
        val out = ArrayList<Release>()
        for (i in 0 until list.length()) {
            val json = list.getJSONObject(i)
            if (json.optBoolean("draft", false)) continue
            val found = release(json, abi) ?: continue
            out.add(found)
            if (out.size >= limit) break
        }
        return out
    }

    /** Looks up the checksum the release publishes for its app, and keeps it in [Release.sha256]. */
    fun checksum(release: Release) {
        if (release.sha256.isNotEmpty()) return
        var hash: String? = null
        for (line in text(release.sumsUrl).lines()) {
            val parts = line.trim().split(Regex("\\s+"), limit = 2)
            if (parts.size == 2 && parts[1].trimStart('*') == release.apkName) hash = parts[0].lowercase()
        }
        if (hash == null) throw IOException("the release has no checksum for ${release.apkName}")
        release.sha256 = hash
    }

    /** True when the connection costs money or is limited (mobile data, a hotspot). */
    fun metered(context: Context): Boolean = try {
        val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        manager.isActiveNetworkMetered
    } catch (e: Exception) {
        false
    }

    /** False on Android 8 and newer until the person allows this app to install apps (Settings, "Install unknown apps"). */
    fun canInstall(context: Context): Boolean = Build.VERSION.SDK_INT < 26 || context.packageManager.canRequestPackageInstalls()

    /** The Settings page where this app is allowed to install apps. */
    fun allowIntent(context: Context): Intent = Intent("android.settings.MANAGE_UNKNOWN_APP_SOURCES", Uri.parse("package:" + context.packageName))

    /** Android's own uninstall screen for PythonOS. */
    fun uninstallIntent(): Intent = Intent(Intent.ACTION_DELETE, Uri.parse("package:$TARGET"))

    /** Compares dotted versions: negative when [a] is older than [b], 0 when equal, positive when newer. */
    fun compare(a: String, b: String): Int {
        val x = a.split(Regex("[.-]")).mapNotNull { it.toIntOrNull() }
        val y = b.split(Regex("[.-]")).mapNotNull { it.toIntOrNull() }
        for (i in 0 until maxOf(x.size, y.size)) {
            val p = x.getOrElse(i) { 0 }
            val q = y.getOrElse(i) { 0 }
            if (p != q) return p.compareTo(q)
        }
        return 0
    }

    /**
     * Downloads the APK into the cache and checks it. A download that was cut off carries on where it stopped (the part is kept next to the
     * file). A file that does not match its checksum is deleted and an IOException says so. [progress] gets bytes done and the total.
     */
    fun download(context: Context, release: Release, progress: (Long, Long) -> Unit): File {
        checksum(release)
        val folder = File(context.cacheDir, "update")
        folder.mkdirs()
        val part = File(folder, "pythonos-${release.version}.apk.part")
        val target = File(folder, "pythonos-${release.version}.apk")
        folder.listFiles()?.forEach { if (it != part && it != target) it.delete() }
        if (target.exists() && sha256(target).equals(release.sha256, ignoreCase = true)) return target      // already downloaded and fine
        target.delete()
        var have = if (part.exists()) part.length() else 0L
        if (release.size > 0 && have >= release.size) { part.delete(); have = 0L }
        val need = if (release.size > 0) release.size - have else 0L
        if (need > 0 && folder.usableSpace < need + 32L * 1024 * 1024) {
            throw IOException("there is not enough free space on this phone (about ${(need + 32L * 1024 * 1024) / 1048576} MB are needed for the download)")
        }
        val connection = open(release.url)
        try {
            if (have > 0) connection.setRequestProperty("Range", "bytes=$have-")
            connection.connect()
            val code = connection.responseCode
            if (code !in 200..299) throw IOException("the download failed (HTTP $code)")
            val resumed = code == 206
            if (!resumed) have = 0L
            val total = (if (connection.contentLengthLong > 0) connection.contentLengthLong else release.size - have).let { if (it > 0) it + have else release.size }
            var done = have
            connection.inputStream.use { input ->
                FileOutputStream(part, resumed).use { output ->
                    val buffer = ByteArray(65536)
                    while (true) {
                        val n = input.read(buffer)
                        if (n < 0) break
                        output.write(buffer, 0, n)
                        done += n
                        progress(done, total)
                    }
                }
            }
        } finally {
            connection.disconnect()
        }
        val got = sha256(part)
        if (!got.equals(release.sha256, ignoreCase = true)) {
            part.delete()
            throw IOException("the download does not match its checksum (damaged or changed), so it was deleted")
        }
        if (!part.renameTo(target)) throw IOException("could not save the download")
        return target
    }

    /** Removes the downloaded files. Called once PythonOS is installed: until then the file is kept, so a retry does not download it again. */
    fun cleanup(context: Context) {
        File(context.cacheDir, "update").listFiles()?.forEach { it.delete() }
    }

    /** Removes downloads of versions that are no longer newer than what is installed (an old, finished or abandoned download). */
    fun cleanStale(context: Context, installed: String?) {
        if (installed == null) return
        File(context.cacheDir, "update").listFiles()?.forEach { file ->
            val version = file.name.removePrefix("pythonos-").removeSuffix(".part").removeSuffix(".apk")
            if (compare(version, installed) <= 0) file.delete()
        }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(65536)
            while (true) {
                val n = input.read(buffer)
                if (n < 0) break
                digest.update(buffer, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    /** Gives the APK to Android's installer, which asks you to confirm (and, the first time, to allow installs from this app). */
    fun install(context: Context, apk: File) {
        val installer = context.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        val id = installer.createSession(params)
        val session = installer.openSession(id)
        try {
            FileInputStream(apk).use { input ->
                session.openWrite("pythonos.apk", 0, apk.length()).use { output ->
                    input.copyTo(output)
                    session.fsync(output)
                }
            }
            val intent = Intent(context, InstallReceiver::class.java).setAction(ACTION)
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
            session.commit(PendingIntent.getBroadcast(context, id, intent, flags).intentSender)
        } catch (e: Exception) {
            session.abandon()
            throw e
        } finally {
            session.close()
        }
    }

    /** A short description of this device for a bug report (no personal information). */
    fun details(context: Context, installed: String?, latest: Release?): String {
        val version = try { context.packageManager.getPackageInfo(context.packageName, 0).versionName } catch (e: Exception) { "?" }
        return listOf(
            "PythonOS Installer $version",
            "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT}), ${Build.MANUFACTURER} ${Build.MODEL}",
            "Processors: ${Build.SUPPORTED_ABIS.joinToString(", ")}",
            "Installed PythonOS: ${installed ?: "none"}",
            "Latest release: ${latest?.tag ?: "unknown"}",
            "Allowed to install apps: ${canInstall(context)}"
        ).joinToString("\n")
    }
}

/** Receives the installer's progress: opens Android's confirmation screen when it asks, and says how it ended. */
class InstallReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val confirm = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)
                if (confirm != null) {
                    confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    context.startActivity(confirm)
                }
            }
            PackageInstaller.STATUS_SUCCESS -> Installer.onResult?.invoke(true, "PythonOS is installed.")
            else -> {
                val why = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "Android did not say why"
                val conflict = status == PackageInstaller.STATUS_FAILURE_CONFLICT || status == PackageInstaller.STATUS_FAILURE_INCOMPATIBLE
                val hint = if (conflict) " An installed PythonOS is signed with a different key, or is newer than this one: back up (the backup command), uninstall it, then install again." else ""
                Installer.onResult?.invoke(false, "Not installed: $why.$hint")
            }
        }
    }
}
