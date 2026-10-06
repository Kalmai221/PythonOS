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
    // the arm64-v8a one (about half the size). The universal APK works anywhere. Chaquopy requires ndk.abiFilters in every variant,
    // so this is done with product flavors (Android's ABI "splits" are not supported together with it).
    flavorDimensions += "abi"
    productFlavors {
        create("universal") {
            dimension = "abi"
            ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
        }
        create("arm64") {
            dimension = "abi"
            ndk { abiFilters += listOf("arm64-v8a") }
        }
        create("x64") {
            dimension = "abi"
            ndk { abiFilters += listOf("x86_64") }
        }
    }

    // Release builds are signed with the permanent key CI reads from these environment variables (see tools/android_signing_setup.py:
    // Android only installs an update over an installed app when both carry the same key). Without them (a local build) they are signed
    // with the debug key, so the APK can still be installed by sideloading, but it cannot update or be updated by a release.
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
