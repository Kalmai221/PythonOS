// Text of the installer in four languages (English, Spanish, French, German). T("key") returns the text in the chosen language;
// a missing translation falls back to English, so a gap can never break the installer.
using System;
using System.Collections.Generic;
using System.Globalization;

namespace PythonOS.Setup
{
    internal static class Strings
    {
        public static readonly string[] Codes = new string[] { "en", "es", "fr", "de" };
        public static readonly string[] Names = new string[] { "English", "Español", "Français", "Deutsch" };
        public static string Language = "en";

        public static string Detect()
        {
            string two = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName.ToLowerInvariant();
            return Array.IndexOf(Codes, two) >= 0 ? two : "en";
        }

        public static string T(string key)
        {
            Dictionary<string, string> table;
            string text;
            if (Language != "en" && Tables.TryGetValue(Language, out table) && table.TryGetValue(key, out text)) return text;
            if (Tables["en"].TryGetValue(key, out text)) return text;
            return key;
        }

        public static string T(string key, params object[] args)
        {
            return string.Format(T(key), args);
        }

        private static readonly Dictionary<string, Dictionary<string, string>> Tables = Build();

        private static Dictionary<string, Dictionary<string, string>> Build()
        {
            Dictionary<string, Dictionary<string, string>> all = new Dictionary<string, Dictionary<string, string>>();

            Dictionary<string, string> en = new Dictionary<string, string>();
            en["title"] = "PythonOS Setup";
            en["welcome"] = "Welcome to PythonOS";
            en["welcome.sub"] = "A small operating system you drive with typed commands. This installer downloads the latest version from GitHub and checks it before installing.";
            en["language"] = "Language";
            en["found"] = "PythonOS {0} is already installed in {1}.";
            en["opt.install"] = "Install PythonOS";
            en["opt.update"] = "Update to {0}";
            en["opt.repair"] = "Repair (reinstall the program files, keep your data)";
            en["opt.uninstall"] = "Uninstall PythonOS";
            en["where"] = "Install location";
            en["browse"] = "Browse...";
            en["memory"] = "Memory PythonOS can use (changeable later)";
            en["memory.all"] = "All of the computer's memory";
            en["desktop"] = "Create a desktop shortcut";
            en["startmenu"] = "Create a Start menu shortcut";
            en["install"] = "Install";
            en["update"] = "Update";
            en["repair"] = "Repair";
            en["uninstall"] = "Uninstall";
            en["next"] = "Next";
            en["back"] = "Back";
            en["cancel"] = "Cancel";
            en["close"] = "Close";
            en["retry"] = "Try again";
            en["launch"] = "Start PythonOS now";
            en["openlog"] = "Open the log";
            en["step.check"] = "Checking this computer";
            en["step.find"] = "Finding the latest version";
            en["step.download"] = "Downloading";
            en["step.verify"] = "Checking the download";
            en["step.install"] = "Installing";
            en["step.shortcuts"] = "Creating shortcuts";
            en["step.requirements"] = "Checking requirements";
            en["req.system"] = "Downloading the PythonOS system...";
            en["req.libraries"] = "Installing the Python libraries...";
            en["err.system"] = "The PythonOS system could not be downloaded. Check your internet connection and try again.";
            en["err.libraries"] = "The Python libraries PythonOS needs could not be installed. Check your internet connection and try again.";
            en["step.remove"] = "Removing PythonOS";
            en["speed"] = "{0} of {1} - {2}/s";
            en["eta"] = " - about {0} left";
            en["done"] = "PythonOS is installed";
            en["done.update"] = "PythonOS was updated to {0}";
            en["done.partial"] = "PythonOS is now {0}, not {1}: the newest files could not be downloaded. Run updatecheck inside PythonOS to finish.";
            en["done.repair"] = "PythonOS was repaired";
            en["done.uninstall"] = "PythonOS was removed";
            en["done.sub"] = "Find it in the Start menu.";
            en["whatsnew"] = "What's new in {0}";
            en["failed"] = "The installation stopped";
            en["failed.sub"] = "Nothing was changed that cannot be repaired. The log has the details:";
            en["err.windows"] = "PythonOS needs Windows 10 (version 1809) or newer.";
            en["err.space"] = "There is not enough free space (about {0} MB are needed).";
            en["err.release"] = "The latest release could not be read. Check your internet connection.";
            en["err.nosums"] = "This release has no checksum file, so the download cannot be checked. Nothing was installed.";
            en["err.sum"] = "The download does not match its checksum. It may be damaged or changed, so it was not installed.";
            en["err.file"] = "The release does not contain the Windows package.";
            en["err.running"] = "PythonOS is running. Close it and try again.";
            en["webview"] = "The Microsoft WebView2 Runtime is missing. It draws the PythonOS window.";
            en["webview.get"] = "Install it now (about 2 MB download from Microsoft)";
            en["keepdata"] = "Also delete my PythonOS files, accounts and settings";
            en["uninstall.ask"] = "Remove PythonOS from this computer?";
            en["ask.running"] = "PythonOS is running. Close it now?";

            Dictionary<string, string> es = new Dictionary<string, string>();
            es["title"] = "Instalación de PythonOS";
            es["welcome"] = "Bienvenido a PythonOS";
            es["welcome.sub"] = "Un pequeño sistema operativo que se maneja con comandos. Este instalador descarga la última versión de GitHub y la comprueba antes de instalarla.";
            es["language"] = "Idioma";
            es["found"] = "PythonOS {0} ya está instalado en {1}.";
            es["opt.install"] = "Instalar PythonOS";
            es["opt.update"] = "Actualizar a {0}";
            es["opt.repair"] = "Reparar (reinstala los archivos del programa y conserva tus datos)";
            es["opt.uninstall"] = "Desinstalar PythonOS";
            es["where"] = "Carpeta de instalación";
            es["browse"] = "Examinar...";
            es["memory"] = "Memoria que puede usar PythonOS (se puede cambiar después)";
            es["memory.all"] = "Toda la memoria del equipo";
            es["desktop"] = "Crear un acceso directo en el escritorio";
            es["startmenu"] = "Crear un acceso directo en el menú Inicio";
            es["install"] = "Instalar"; es["update"] = "Actualizar"; es["repair"] = "Reparar"; es["uninstall"] = "Desinstalar";
            es["next"] = "Siguiente"; es["back"] = "Atrás"; es["cancel"] = "Cancelar"; es["close"] = "Cerrar"; es["retry"] = "Reintentar";
            es["launch"] = "Iniciar PythonOS ahora";
            es["openlog"] = "Abrir el registro";
            es["step.check"] = "Comprobando este equipo";
            es["step.find"] = "Buscando la última versión";
            es["step.download"] = "Descargando";
            es["step.verify"] = "Comprobando la descarga";
            es["step.install"] = "Instalando";
            es["step.shortcuts"] = "Creando accesos directos";
            es["step.requirements"] = "Comprobando los requisitos";
            es["req.system"] = "Descargando el sistema PythonOS...";
            es["req.libraries"] = "Instalando las bibliotecas de Python...";
            es["err.system"] = "No se pudo descargar el sistema PythonOS. Comprueba tu conexión a internet e inténtalo de nuevo.";
            es["err.libraries"] = "No se pudieron instalar las bibliotecas de Python que necesita PythonOS. Comprueba tu conexión a internet e inténtalo de nuevo.";
            es["step.remove"] = "Quitando PythonOS";
            es["speed"] = "{0} de {1} - {2}/s";
            es["eta"] = " - faltan unos {0}";
            es["done"] = "PythonOS está instalado";
            es["done.update"] = "PythonOS se actualizó a {0}";
            es["done.partial"] = "PythonOS es ahora {0}, no {1}: no se pudieron descargar los archivos más recientes. Ejecute updatecheck en PythonOS para terminar.";
            es["done.repair"] = "PythonOS se reparó";
            es["done.uninstall"] = "PythonOS se eliminó";
            es["done.sub"] = "Lo encontrarás en el menú Inicio.";
            es["whatsnew"] = "Novedades de {0}";
            es["failed"] = "La instalación se detuvo";
            es["failed.sub"] = "No se cambió nada que no se pueda reparar. El registro tiene los detalles:";
            es["err.windows"] = "PythonOS necesita Windows 10 (versión 1809) o posterior.";
            es["err.space"] = "No hay espacio libre suficiente (se necesitan unos {0} MB).";
            es["err.release"] = "No se pudo leer la última versión. Comprueba tu conexión a internet.";
            es["err.nosums"] = "Esta versión no tiene archivo de sumas de comprobación, así que la descarga no se puede verificar. No se instaló nada.";
            es["err.sum"] = "La descarga no coincide con su suma de comprobación. Puede estar dañada o alterada, por eso no se instaló.";
            es["err.file"] = "La versión no contiene el paquete de Windows.";
            es["err.running"] = "PythonOS se está ejecutando. Ciérralo e inténtalo de nuevo.";
            es["webview"] = "Falta el Microsoft WebView2 Runtime. Dibuja la ventana de PythonOS.";
            es["webview.get"] = "Instalarlo ahora (descarga de unos 2 MB de Microsoft)";
            es["keepdata"] = "Eliminar también mis archivos, cuentas y ajustes de PythonOS";
            es["uninstall.ask"] = "¿Quitar PythonOS de este equipo?";
            es["ask.running"] = "PythonOS se está ejecutando. ¿Cerrarlo ahora?";

            Dictionary<string, string> fr = new Dictionary<string, string>();
            fr["title"] = "Installation de PythonOS";
            fr["welcome"] = "Bienvenue dans PythonOS";
            fr["welcome.sub"] = "Un petit système d'exploitation que l'on pilote en tapant des commandes. Cet installateur télécharge la dernière version depuis GitHub et la vérifie avant de l'installer.";
            fr["language"] = "Langue";
            fr["found"] = "PythonOS {0} est déjà installé dans {1}.";
            fr["opt.install"] = "Installer PythonOS";
            fr["opt.update"] = "Mettre à jour vers {0}";
            fr["opt.repair"] = "Réparer (réinstalle les fichiers du programme, conserve vos données)";
            fr["opt.uninstall"] = "Désinstaller PythonOS";
            fr["where"] = "Dossier d'installation";
            fr["browse"] = "Parcourir...";
            fr["memory"] = "Mémoire utilisable par PythonOS (modifiable plus tard)";
            fr["memory.all"] = "Toute la mémoire de l'ordinateur";
            fr["desktop"] = "Créer un raccourci sur le Bureau";
            fr["startmenu"] = "Créer un raccourci dans le menu Démarrer";
            fr["install"] = "Installer"; fr["update"] = "Mettre à jour"; fr["repair"] = "Réparer"; fr["uninstall"] = "Désinstaller";
            fr["next"] = "Suivant"; fr["back"] = "Retour"; fr["cancel"] = "Annuler"; fr["close"] = "Fermer"; fr["retry"] = "Réessayer";
            fr["launch"] = "Démarrer PythonOS maintenant";
            fr["openlog"] = "Ouvrir le journal";
            fr["step.check"] = "Vérification de cet ordinateur";
            fr["step.find"] = "Recherche de la dernière version";
            fr["step.download"] = "Téléchargement";
            fr["step.verify"] = "Vérification du téléchargement";
            fr["step.install"] = "Installation";
            fr["step.shortcuts"] = "Création des raccourcis";
            fr["step.requirements"] = "Vérification des prérequis";
            fr["req.system"] = "Téléchargement du système PythonOS...";
            fr["req.libraries"] = "Installation des bibliothèques Python...";
            fr["err.system"] = "Le système PythonOS n'a pas pu être téléchargé. Vérifiez votre connexion internet et réessayez.";
            fr["err.libraries"] = "Les bibliothèques Python nécessaires à PythonOS n'ont pas pu être installées. Vérifiez votre connexion internet et réessayez.";
            fr["step.remove"] = "Suppression de PythonOS";
            fr["speed"] = "{0} sur {1} - {2}/s";
            fr["eta"] = " - environ {0} restantes";
            fr["done"] = "PythonOS est installé";
            fr["done.update"] = "PythonOS a été mis à jour vers {0}";
            fr["done.partial"] = "PythonOS est maintenant en {0}, pas en {1} : les fichiers les plus récents n'ont pas pu être téléchargés. Lancez updatecheck dans PythonOS pour terminer.";
            fr["done.repair"] = "PythonOS a été réparé";
            fr["done.uninstall"] = "PythonOS a été supprimé";
            fr["done.sub"] = "Vous le trouverez dans le menu Démarrer.";
            fr["whatsnew"] = "Nouveautés de {0}";
            fr["failed"] = "L'installation s'est arrêtée";
            fr["failed.sub"] = "Rien n'a été modifié qui ne puisse être réparé. Le journal contient les détails :";
            fr["err.windows"] = "PythonOS nécessite Windows 10 (version 1809) ou plus récent.";
            fr["err.space"] = "Il n'y a pas assez d'espace libre (environ {0} Mo nécessaires).";
            fr["err.release"] = "La dernière version n'a pas pu être lue. Vérifiez votre connexion internet.";
            fr["err.nosums"] = "Cette version n'a pas de fichier de sommes de contrôle : le téléchargement ne peut pas être vérifié. Rien n'a été installé.";
            fr["err.sum"] = "Le téléchargement ne correspond pas à sa somme de contrôle. Il est peut-être endommagé ou modifié, il n'a donc pas été installé.";
            fr["err.file"] = "La version ne contient pas le paquet Windows.";
            fr["err.running"] = "PythonOS est en cours d'exécution. Fermez-le et réessayez.";
            fr["webview"] = "Le Microsoft WebView2 Runtime est absent. Il affiche la fenêtre de PythonOS.";
            fr["webview.get"] = "L'installer maintenant (environ 2 Mo à télécharger chez Microsoft)";
            fr["keepdata"] = "Supprimer aussi mes fichiers, comptes et réglages PythonOS";
            fr["uninstall.ask"] = "Supprimer PythonOS de cet ordinateur ?";
            fr["ask.running"] = "PythonOS est en cours d'exécution. Le fermer maintenant ?";

            Dictionary<string, string> de = new Dictionary<string, string>();
            de["title"] = "PythonOS-Setup";
            de["welcome"] = "Willkommen bei PythonOS";
            de["welcome.sub"] = "Ein kleines Betriebssystem, das du mit getippten Befehlen bedienst. Dieses Setup lädt die neueste Version von GitHub und prüft sie vor der Installation.";
            de["language"] = "Sprache";
            de["found"] = "PythonOS {0} ist bereits in {1} installiert.";
            de["opt.install"] = "PythonOS installieren";
            de["opt.update"] = "Auf {0} aktualisieren";
            de["opt.repair"] = "Reparieren (Programmdateien neu installieren, Daten behalten)";
            de["opt.uninstall"] = "PythonOS deinstallieren";
            de["where"] = "Installationsordner";
            de["browse"] = "Durchsuchen...";
            de["memory"] = "Arbeitsspeicher für PythonOS (später änderbar)";
            de["memory.all"] = "Der gesamte Arbeitsspeicher des Computers";
            de["desktop"] = "Verknüpfung auf dem Desktop erstellen";
            de["startmenu"] = "Verknüpfung im Startmenü erstellen";
            de["install"] = "Installieren"; de["update"] = "Aktualisieren"; de["repair"] = "Reparieren"; de["uninstall"] = "Deinstallieren";
            de["next"] = "Weiter"; de["back"] = "Zurück"; de["cancel"] = "Abbrechen"; de["close"] = "Schließen"; de["retry"] = "Erneut versuchen";
            de["launch"] = "PythonOS jetzt starten";
            de["openlog"] = "Protokoll öffnen";
            de["step.check"] = "Dieser Computer wird geprüft";
            de["step.find"] = "Neueste Version wird gesucht";
            de["step.download"] = "Herunterladen";
            de["step.verify"] = "Download wird geprüft";
            de["step.install"] = "Installieren";
            de["step.shortcuts"] = "Verknüpfungen werden erstellt";
            de["step.requirements"] = "Voraussetzungen werden geprüft";
            de["req.system"] = "Das PythonOS-System wird heruntergeladen...";
            de["req.libraries"] = "Die Python-Bibliotheken werden installiert...";
            de["err.system"] = "Das PythonOS-System konnte nicht heruntergeladen werden. Prüfe deine Internetverbindung und versuche es erneut.";
            de["err.libraries"] = "Die von PythonOS benötigten Python-Bibliotheken konnten nicht installiert werden. Prüfe deine Internetverbindung und versuche es erneut.";
            de["step.remove"] = "PythonOS wird entfernt";
            de["speed"] = "{0} von {1} - {2}/s";
            de["eta"] = " - noch etwa {0}";
            de["done"] = "PythonOS ist installiert";
            de["done.update"] = "PythonOS wurde auf {0} aktualisiert";
            de["done.partial"] = "PythonOS ist jetzt {0}, nicht {1}: die neuesten Dateien konnten nicht geladen werden. Führen Sie updatecheck in PythonOS aus, um abzuschließen.";
            de["done.repair"] = "PythonOS wurde repariert";
            de["done.uninstall"] = "PythonOS wurde entfernt";
            de["done.sub"] = "Du findest es im Startmenü.";
            de["whatsnew"] = "Neu in {0}";
            de["failed"] = "Die Installation wurde angehalten";
            de["failed.sub"] = "Es wurde nichts verändert, was sich nicht reparieren ließe. Das Protokoll enthält die Einzelheiten:";
            de["err.windows"] = "PythonOS benötigt Windows 10 (Version 1809) oder neuer.";
            de["err.space"] = "Es ist nicht genug freier Speicher vorhanden (etwa {0} MB nötig).";
            de["err.release"] = "Die neueste Version konnte nicht gelesen werden. Prüfe deine Internetverbindung.";
            de["err.nosums"] = "Diese Version hat keine Prüfsummendatei, der Download kann also nicht geprüft werden. Es wurde nichts installiert.";
            de["err.sum"] = "Der Download passt nicht zu seiner Prüfsumme. Er ist möglicherweise beschädigt oder verändert und wurde deshalb nicht installiert.";
            de["err.file"] = "Die Version enthält das Windows-Paket nicht.";
            de["err.running"] = "PythonOS läuft. Schließe es und versuche es erneut.";
            de["webview"] = "Die Microsoft WebView2 Runtime fehlt. Sie zeichnet das PythonOS-Fenster.";
            de["webview.get"] = "Jetzt installieren (etwa 2 MB Download von Microsoft)";
            de["keepdata"] = "Auch meine PythonOS-Dateien, Konten und Einstellungen löschen";
            de["uninstall.ask"] = "PythonOS von diesem Computer entfernen?";
            de["ask.running"] = "PythonOS läuft. Jetzt schließen?";

            all["en"] = en; all["es"] = es; all["fr"] = fr; all["de"] = de;
            return all;
        }
    }
}
