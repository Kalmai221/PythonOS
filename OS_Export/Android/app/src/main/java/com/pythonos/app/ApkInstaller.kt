package com.pythonos.app

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * Installs a newer version of this app: downloads the APK, checks it against the checksum PythonOS read from the release, and hands it to
 * Android's package installer, which asks you to confirm (an app cannot replace itself silently).
 * PythonOS calls this through TerminalBridge.installUpdate (the updatecheck command, or the app menu).
 */
object ApkInstaller {
    private const val ACTION = "com.pythonos.app.INSTALL_RESULT"

    /** Downloads [url] into the app's cache and returns the file. Throws IOException when the checksum does not match or is missing. */
    fun download(context: Context, url: String, sha256: String, progress: (Int) -> Unit): File {
        if (sha256.isBlank()) throw IOException("the release has no checksum for this file, so it cannot be checked")
        val folder = File(context.cacheDir, "update")
        folder.mkdirs()
        folder.listFiles()?.forEach { it.delete() }
        val target = File(folder, "pythonos-update.apk")
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.connectTimeout = 15000
        connection.readTimeout = 30000
        connection.instanceFollowRedirects = true
        try {
            connection.connect()
            if (connection.responseCode !in 200..299) throw IOException("the download failed (HTTP ${connection.responseCode})")
            val total = connection.contentLengthLong
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
            if (!got.equals(sha256.trim(), ignoreCase = true)) {
                target.delete()
                throw IOException("the download does not match its checksum (damaged or changed), so it was deleted")
            }
        } finally {
            connection.disconnect()
        }
        return target
    }

    /** Gives the APK to Android's installer. Android shows its own confirmation (and, the first time, asks to allow installs from this app). */
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
            val pending = PendingIntent.getBroadcast(context, id, intent, flags)
            session.commit(pending.intentSender)
        } catch (e: Exception) {
            session.abandon()
            throw e
        } finally {
            session.close()
        }
    }
}

/** Receives the installer's progress: opens Android's confirmation screen when it asks for one, and says how it ended. */
class InstallReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val confirm = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)
                if (confirm != null) {
                    confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    context.startActivity(confirm)
                }
            }
            PackageInstaller.STATUS_SUCCESS -> TerminalBridge.write("\u001b[32mThe new version of the app was installed.\u001b[0m\n")
            else -> {
                val why = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "Android did not say why"
                TerminalBridge.write("\u001b[31mThe app was not updated: $why\u001b[0m\n")
            }
        }
    }
}
