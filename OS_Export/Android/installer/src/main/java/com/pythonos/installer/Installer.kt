package com.pythonos.installer

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import android.widget.Toast
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/** What the installer does: find the right PythonOS APK for this device, download it, check it, hand it to Android's installer. */
object Installer {
    const val TARGET = "com.pythonos.app"
    private const val API = "https://api.github.com/repos/Kalmai221/PythonOS/releases/latest"
    private const val ACTION = "com.pythonos.installer.INSTALL_RESULT"

    class Release(val tag: String, val name: String, val url: String, val sha256: String, val size: Long)

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

    /** The latest release's APK for [abi], with the checksum the release publishes for it. */
    fun latest(abi: String): Release {
        val json = JSONObject(text(API))
        val assets = json.getJSONArray("assets")
        var apk: JSONObject? = null
        var sums: String? = null
        for (i in 0 until assets.length()) {
            val asset = assets.getJSONObject(i)
            val name = asset.getString("name")
            if (name.endsWith("-android-$abi.apk")) apk = asset
            if (name == "SHA256SUMS") sums = asset.getString("browser_download_url")
        }
        if (apk == null) throw IOException("the latest release has no app for this device ($abi)")
        if (sums == null) throw IOException("the latest release has no checksums, so the app cannot be checked")
        val name = apk.getString("name")
        var hash: String? = null
        for (line in text(sums).lines()) {
            val parts = line.trim().split(Regex("\\s+"), limit = 2)
            if (parts.size == 2 && parts[1].trimStart('*') == name) hash = parts[0].lowercase()
        }
        if (hash == null) throw IOException("the release has no checksum for $name")
        return Release(json.getString("tag_name"), name, apk.getString("browser_download_url"), hash, apk.optLong("size"))
    }

    /** Downloads the APK into the cache and checks it. A file that does not match is deleted and an IOException says so. */
    fun download(context: Context, release: Release, progress: (Int) -> Unit): File {
        val folder = File(context.cacheDir, "update")
        folder.mkdirs()
        folder.listFiles()?.forEach { it.delete() }
        val target = File(folder, "pythonos.apk")
        val connection = open(release.url)
        try {
            connection.connect()
            if (connection.responseCode !in 200..299) throw IOException("the download failed (HTTP ${connection.responseCode})")
            val total = if (connection.contentLengthLong > 0) connection.contentLengthLong else release.size
            val digest = MessageDigest.getInstance("SHA-256")
            var done = 0L
            var last = -1
            connection.inputStream.use { input ->
                FileOutputStream(target).use { output ->
                    val buffer = ByteArray(65536)
                    while (true) {
                        val n = input.read(buffer)
                        if (n < 0) break
                        output.write(buffer, 0, n)
                        digest.update(buffer, 0, n)
                        done += n
                        if (total > 0) {
                            val percent = (done * 100 / total).toInt()
                            if (percent != last) { last = percent; progress(percent) }
                        }
                    }
                }
            }
            val got = digest.digest().joinToString("") { "%02x".format(it) }
            if (!got.equals(release.sha256, ignoreCase = true)) {
                target.delete()
                throw IOException("the download does not match its checksum (damaged or changed), so it was deleted")
            }
        } finally {
            connection.disconnect()
        }
        return target
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
            PackageInstaller.STATUS_SUCCESS -> Toast.makeText(context, "PythonOS is installed. Open it from this app or your app list.", Toast.LENGTH_LONG).show()
            else -> {
                val why = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "Android did not say why"
                val conflict = status == PackageInstaller.STATUS_FAILURE_CONFLICT || status == PackageInstaller.STATUS_FAILURE_INCOMPATIBLE
                val hint = if (conflict) " An older PythonOS signed with a different key is installed: back up (the backup command), uninstall it, then install again." else ""
                Toast.makeText(context, "Not installed: $why.$hint", Toast.LENGTH_LONG).show()
            }
        }
    }
}
