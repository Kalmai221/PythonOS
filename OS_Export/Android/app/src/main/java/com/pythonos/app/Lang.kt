package com.pythonos.app

import android.content.Context
import java.util.Locale

/**
 * The app's language: the menu, the update sheets and the toasts. The first launch asks (before PythonOS starts) and PythonOS is
 * told the answer, so its own first-time setup does not ask again; the menu's Language row changes both later. Texts are looked
 * up by their English wording; anything without a translation shows in English. {0}, {1} ... are filled in from the arguments.
 */
object Lang {
    val choices = listOf("en" to "English", "es" to "Español", "fr" to "Français", "de" to "Deutsch")
    var code = "en"
        private set

    /** True once a language was chosen (or the phone's language was accepted); false on the very first launch. */
    fun chosen(context: Context): Boolean = context.getSharedPreferences("terminal", Context.MODE_PRIVATE).contains("lang")

    fun init(context: Context) {
        val saved = try { context.getSharedPreferences("terminal", Context.MODE_PRIVATE).getString("lang", null) } catch (e: Exception) { null }
        val wanted = saved ?: Locale.getDefault().language
        code = if (choices.any { it.first == wanted }) wanted else "en"
    }

    /** The phone's language when we have it, else English: the pre-selected answer of the first question. */
    fun guess(): String = Locale.getDefault().language.takeIf { l -> choices.any { it.first == l } } ?: "en"

    fun choose(context: Context, wanted: String) {
        code = wanted
        try { context.getSharedPreferences("terminal", Context.MODE_PRIVATE).edit().putString("lang", wanted).apply() } catch (e: Exception) { }
        // PythonOS reads these when it starts (pyos/i18n.py, core/firsttimeuse.py)
        try {
            android.system.Os.setenv("PYOS_LANG", wanted, true)
            android.system.Os.setenv("PYOS_LANG_CHOSEN", "1", true)
        } catch (e: Throwable) { }
    }

    /** Puts the saved choice into the environment for PythonOS, if there is one. */
    fun export(context: Context) {
        if (chosen(context)) choose(context, code)
    }

    fun text(english: String, args: Array<out Any?>): String {
        var out = (when (code) { "es" -> ES; "fr" -> FR; "de" -> DE; else -> null })?.get(english) ?: english
        for ((i, value) in args.withIndex()) out = out.replace("{$i}", value?.toString() ?: "")
        return out
    }

    private val ES = mapOf(
        "Paste" to "Pegar",
        "Type the clipboard into the terminal" to "Escribe el portapapeles en el terminal",
        "Copy screen text" to "Copiar texto de la pantalla",
        "Everything on the screen, as text" to "Todo lo que hay en pantalla, como texto",
        "Help" to "Ayuda",
        "List the commands" to "Lista los comandos",
        "Look" to "Aspecto",
        "Text size" to "Tamaño del texto",
        "Keep screen on" to "Mantener pantalla encendida",
        "Stops the screen from sleeping" to "Evita que la pantalla se apague",
        "Language" to "Idioma",
        "App" to "Aplicación",
        "Check for app update" to "Buscar actualización de la aplicación",
        "The app is a separate download" to "La aplicación es una descarga aparte",
        "Report a problem" to "Informar de un problema",
        "Prepares a report you read before anything is sent" to "Prepara un informe que lees antes de enviar nada",
        "About" to "Acerca de",
        "Nothing to paste" to "Nada que pegar",
        "Screen text copied" to "Texto de la pantalla copiado",
        "App version {0}" to "Versión de la aplicación {0}",
        "The terminal runs PythonOS. PythonOS updates itself; this app is a separate package, so a new version of the app has to be downloaded and installed by hand (Menu, then Check for app update)." to "El terminal ejecuta PythonOS. PythonOS se actualiza solo; esta aplicación es un paquete aparte, así que una versión nueva de la aplicación hay que descargarla e instalarla a mano (Menú y luego Buscar actualización de la aplicación).",
        "OK" to "Aceptar",
        "PythonOS is still starting - try again in a moment" to "PythonOS aún está arrancando: inténtalo de nuevo en un momento",
        "No newer app found (or you're offline)" to "No hay una aplicación más nueva (o no tienes conexión)",
        "New app version {0} available — tap for details" to "Nueva versión de la aplicación {0} disponible: toca para ver detalles",
        "Install the new app" to "Instalar la aplicación nueva",
        "App update available" to "Actualización de la aplicación disponible",
        "PythonOS itself keeps updating on its own. The app around it is a separate package, so Android asks you to confirm its update: tap Install now, PythonOS downloads the new app, checks it, and hands it to Android's installer. Your files are kept." to "PythonOS sigue actualizándose solo. La aplicación que lo rodea es un paquete aparte, así que Android te pide confirmar su actualización: toca Instalar ahora, PythonOS descarga la aplicación nueva, la comprueba y se la pasa al instalador de Android. Tus archivos se conservan.",
        "The file's SHA-256:" to "SHA-256 del archivo:",
        "This release has no checksum for the file, so it cannot be installed from here; use Download instead." to "Esta versión no tiene suma de comprobación del archivo, así que no se puede instalar desde aquí; usa Descargar.",
        "Install now" to "Instalar ahora",
        "Download" to "Descargar",
        "Downloading the new app..." to "Descargando la aplicación nueva...",
        "Not updated: {0}" to "No actualizada: {0}",
        "Language / Idioma / Langue / Sprache" to "Language / Idioma / Langue / Sprache",
        "PythonOS will speak this language. You can change it later in the menu." to "PythonOS hablará este idioma. Puedes cambiarlo después en el menú.",
    )

    private val FR = mapOf(
        "Paste" to "Coller",
        "Type the clipboard into the terminal" to "Saisit le presse-papiers dans le terminal",
        "Copy screen text" to "Copier le texte de l'écran",
        "Everything on the screen, as text" to "Tout ce qui est à l'écran, en texte",
        "Help" to "Aide",
        "List the commands" to "Liste les commandes",
        "Look" to "Apparence",
        "Text size" to "Taille du texte",
        "Keep screen on" to "Garder l'écran allumé",
        "Stops the screen from sleeping" to "Empêche l'écran de se mettre en veille",
        "Language" to "Langue",
        "App" to "Application",
        "Check for app update" to "Chercher une mise à jour de l'application",
        "The app is a separate download" to "L'application se télécharge à part",
        "Report a problem" to "Signaler un problème",
        "Prepares a report you read before anything is sent" to "Prépare un rapport que vous lisez avant tout envoi",
        "About" to "À propos",
        "Nothing to paste" to "Rien à coller",
        "Screen text copied" to "Texte de l'écran copié",
        "App version {0}" to "Version de l'application {0}",
        "The terminal runs PythonOS. PythonOS updates itself; this app is a separate package, so a new version of the app has to be downloaded and installed by hand (Menu, then Check for app update)." to "Le terminal exécute PythonOS. PythonOS se met à jour tout seul ; cette application est un paquet à part, donc une nouvelle version de l'application doit être téléchargée et installée à la main (Menu, puis Chercher une mise à jour de l'application).",
        "OK" to "OK",
        "PythonOS is still starting - try again in a moment" to "PythonOS démarre encore : réessayez dans un instant",
        "No newer app found (or you're offline)" to "Aucune application plus récente (ou vous êtes hors ligne)",
        "New app version {0} available — tap for details" to "Nouvelle version de l'application {0} disponible : touchez pour les détails",
        "Install the new app" to "Installer la nouvelle application",
        "App update available" to "Mise à jour de l'application disponible",
        "PythonOS itself keeps updating on its own. The app around it is a separate package, so Android asks you to confirm its update: tap Install now, PythonOS downloads the new app, checks it, and hands it to Android's installer. Your files are kept." to "PythonOS continue de se mettre à jour tout seul. L'application qui l'entoure est un paquet à part, donc Android vous demande de confirmer sa mise à jour : touchez Installer maintenant, PythonOS télécharge la nouvelle application, la vérifie et la confie à l'installateur d'Android. Vos fichiers sont conservés.",
        "The file's SHA-256:" to "SHA-256 du fichier :",
        "This release has no checksum for the file, so it cannot be installed from here; use Download instead." to "Cette version n'a pas de somme de contrôle pour le fichier, il ne peut donc pas être installé d'ici ; utilisez Télécharger.",
        "Install now" to "Installer maintenant",
        "Download" to "Télécharger",
        "Downloading the new app..." to "Téléchargement de la nouvelle application...",
        "Not updated: {0}" to "Non mise à jour : {0}",
        "Language / Idioma / Langue / Sprache" to "Language / Idioma / Langue / Sprache",
        "PythonOS will speak this language. You can change it later in the menu." to "PythonOS parlera cette langue. Vous pourrez la changer plus tard dans le menu.",
    )

    private val DE = mapOf(
        "Paste" to "Einfügen",
        "Type the clipboard into the terminal" to "Gibt die Zwischenablage im Terminal ein",
        "Copy screen text" to "Bildschirmtext kopieren",
        "Everything on the screen, as text" to "Alles auf dem Bildschirm, als Text",
        "Help" to "Hilfe",
        "List the commands" to "Listet die Befehle auf",
        "Look" to "Aussehen",
        "Text size" to "Textgröße",
        "Keep screen on" to "Bildschirm anlassen",
        "Stops the screen from sleeping" to "Verhindert, dass der Bildschirm ausgeht",
        "Language" to "Sprache",
        "App" to "App",
        "Check for app update" to "Nach App-Update suchen",
        "The app is a separate download" to "Die App ist ein eigener Download",
        "Report a problem" to "Ein Problem melden",
        "Prepares a report you read before anything is sent" to "Bereitet einen Bericht vor, den Sie lesen, bevor etwas gesendet wird",
        "About" to "Info",
        "Nothing to paste" to "Nichts zum Einfügen",
        "Screen text copied" to "Bildschirmtext kopiert",
        "App version {0}" to "App-Version {0}",
        "The terminal runs PythonOS. PythonOS updates itself; this app is a separate package, so a new version of the app has to be downloaded and installed by hand (Menu, then Check for app update)." to "Das Terminal führt PythonOS aus. PythonOS aktualisiert sich selbst; diese App ist ein eigenes Paket, eine neue App-Version muss also von Hand heruntergeladen und installiert werden (Menü, dann Nach App-Update suchen).",
        "OK" to "OK",
        "PythonOS is still starting - try again in a moment" to "PythonOS startet noch – versuchen Sie es gleich noch einmal",
        "No newer app found (or you're offline)" to "Keine neuere App gefunden (oder Sie sind offline)",
        "New app version {0} available — tap for details" to "Neue App-Version {0} verfügbar – tippen für Details",
        "Install the new app" to "Die neue App installieren",
        "App update available" to "App-Update verfügbar",
        "PythonOS itself keeps updating on its own. The app around it is a separate package, so Android asks you to confirm its update: tap Install now, PythonOS downloads the new app, checks it, and hands it to Android's installer. Your files are kept." to "PythonOS aktualisiert sich weiter selbst. Die App darum herum ist ein eigenes Paket, daher bittet Android Sie, ihr Update zu bestätigen: Tippen Sie auf Jetzt installieren, PythonOS lädt die neue App herunter, prüft sie und übergibt sie dem Installer von Android. Ihre Dateien bleiben erhalten.",
        "The file's SHA-256:" to "SHA-256 der Datei:",
        "This release has no checksum for the file, so it cannot be installed from here; use Download instead." to "Diese Version hat keine Prüfsumme für die Datei, sie kann also nicht von hier installiert werden; nutzen Sie Herunterladen.",
        "Install now" to "Jetzt installieren",
        "Download" to "Herunterladen",
        "Downloading the new app..." to "Neue App wird heruntergeladen...",
        "Not updated: {0}" to "Nicht aktualisiert: {0}",
        "Language / Idioma / Langue / Sprache" to "Language / Idioma / Langue / Sprache",
        "PythonOS will speak this language. You can change it later in the menu." to "PythonOS spricht diese Sprache. Sie können sie später im Menü ändern.",
    )
}

/** The translated text for an English wording, with {0}, {1} ... filled in. */
fun t(english: String, vararg args: Any?): String = Lang.text(english, args)
