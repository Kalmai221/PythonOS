plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.pythonos.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.pythonos.app"
        minSdk = 24
        targetSdk = 34
        // CI passes these:  gradle assembleRelease -PversionName=1.2.0 -PversionCode=42
        versionCode = (project.findProperty("versionCode") as String?)?.toIntOrNull() ?: 1
        versionName = (project.findProperty("versionName") as String?) ?: "1.0"
    }

    // One APK per processor type plus a universal one. Chaquopy's native libraries make a single APK large; a phone only needs
    // the arm64-v8a one (about half the size). The universal APK works anywhere. (abiFilters must not be set together with splits.)
    splits {
        abi {
            isEnable = true
            reset()
            include("arm64-v8a", "x86_64")
            isUniversalApk = true
        }
    }

    // Release builds use your own keystore when these environment variables are set
    // (see OS_Export/README.md); otherwise they are signed with the debug key so the
    // APK can still be installed by sideloading.
    signingConfigs {
        create("release") {
            val keystore = System.getenv("ANDROID_KEYSTORE_FILE")
            if (!keystore.isNullOrEmpty()) {
                storeFile = file(keystore)
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("ANDROID_KEY_PASSWORD")
            } else {
                initWith(getByName("debug"))
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    packaging {
        resources.excludes += "META-INF/**"
    }
}

chaquopy {
    defaultConfig {
        version = "3.13"
        pip {
            // Everything in requirements.txt. Android cannot run pip at runtime, so the OS
            // starts in "bundled" mode (PYOS_BUNDLED=1) and uses these as shipped.
            install("rich")
            install("psutil")
            install("requests")
            install("yaspin")
            install("ping3")
            install("prompt_toolkit")
            install("pygments")
            install("tzdata")
        }
    }
}
