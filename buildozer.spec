# (1) Application Information
[app]
title = MyConsoleApp
package.name = myconsoleapp
package.domain = org.example
source.main = installer/run.py  # Path to your main script

# (2) Source Files
source.include_exts = py
source.include_patterns = installer/*
source.dir = installer

# (3) Version & Build
version = 1.0

# Install dependencies from installer-requirements.txt
# Example: If your installer-requirements.txt contains "requests", add it here
requirements = python3,rich,yaspin  # Replace with your actual dependencies

# (4) Android Packaging
android.permissions = INTERNET
android.api = 31
android.minapi = 21
android.ndk = 23b
android.ndk_api = 21
android.arch = arm64-v8a,armeabi-v7a,x86,x86_64
android.gradle_dependencies = 

# (5) Buildozer Configurations
p4a.branch = master
p4a.fork = kivy
p4a.source_dir = 

# (6) Terminal Mode (Console App)
android.entrypoint = sh  # Runs in a shell terminal
android.private_storage = True
android.allow_cleartext_default = True

# (7) Build Type
package.mode = release  # Change to "debug" for testing
package.format = apk

# (8) Orientation (Doesn't matter for CLI apps, but required)
orientation = portrait

# (9) Buildozer Behavior
log_level = 2
warn_on_root = 1
