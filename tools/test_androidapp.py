#!/usr/bin/env python3
"""The Android app's start-up: installing a new APK over an old one must bring the core (kept in the app's files folder) up to date, and
bootstrap.install must keep the version in config.json in step. Chaquopy's `java` module and the network are faked."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    java = types.ModuleType("java")
    java.jclass = lambda name: types.SimpleNamespace()
    sys.modules["java"] = java
    app = load(os.path.join(REPO_ROOT, "OS_Export", "Android", "app", "src", "main", "python", "pyos_android.py"), "pyos_android_under_test")
    real_key = load(os.path.join(REPO_ROOT, "OS_Export", "bootstrap.py"), "bootstrap_keys").version_key

    tmp = tempfile.mkdtemp()
    try:
        installs = []
        fake_bootstrap = types.ModuleType("bootstrap")
        fake_bootstrap.install = lambda dest, log=print, **k: (installs.append(dest), True)[1]
        fake_bootstrap.version_key = real_key
        sys.modules["bootstrap"] = fake_bootstrap
        identity = types.ModuleType("pyos_export")
        sys.modules["pyos_export"] = identity
        said = []

        def start(app_version, core_version):
            """One start of the app: the app is built for app_version; files_dir holds core_version (None = no core yet)."""
            identity.INFO = {"platform": "android", "version": app_version, "api": 2}
            version_file = os.path.join(tmp, "VERSION")
            if core_version is None:
                if os.path.exists(version_file):
                    os.remove(version_file)
            else:
                with open(version_file, "w", encoding="utf-8") as f:
                    f.write(core_version + "\n")
            installs.clear()
            said.clear()
            return app.refresh_core_after_app_update(tmp, said.append)

        # a first installation: no core yet, the app downloads it itself at start-up, so nothing is done here
        assert start("1.0.12", None) is True and installs == []
        # the core is the app's own version, or newer (an app that was not rebuilt keeps its older version number): nothing to do
        assert start("1.0.12", "1.0.12") is True and installs == []
        assert start("1.0.8", "1.0.12") is True and installs == []
        # a new app installed over an old one: the core is older than the app, so the newest release is installed - whatever was remembered,
        # and also the first time after an update from an app that did not yet have this check
        assert start("1.0.13", "1.0.8") is True and installs == [tmp] and any("1.0.8" in line and "1.0.13" in line for line in said)
        assert start("1.0.12", "1.0.11") is True and installs == [tmp]
        # offline: it says so and starts anyway; the same rule asks again at the next start
        fake_bootstrap.install = lambda dest, log=print, **k: False
        assert start("1.0.14", "1.0.12") is False and any("try again" in line for line in said)
        fake_bootstrap.install = lambda dest, log=print, **k: (installs.append(dest), True)[1]
        assert start("1.0.14", "1.0.12") is True and installs == [tmp]
        # an app with no identity is left alone
        del sys.modules["pyos_export"]
        sys.modules["pyos_export"] = types.ModuleType("pyos_export")
        assert app.refresh_core_after_app_update(tmp, said.append) is True

        # bootstrap keeps config.json's version in step without touching the settings
        real = load(os.path.join(REPO_ROOT, "OS_Export", "bootstrap.py"), "bootstrap_under_test")
        with open(os.path.join(tmp, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"version": "1.0.8", "theme": "dark"}, f)
        real.sync_config_version(tmp, "1.0.12")
        with open(os.path.join(tmp, "config.json"), encoding="utf-8") as f:
            assert json.load(f) == {"version": "1.0.12", "theme": "dark"}
        real.sync_config_version(os.path.join(tmp, "nowhere"), "1.0.12")            # no config.json: nothing happens
    finally:
        for name in ("java", "bootstrap", "pyos_export"):
            sys.modules.pop(name, None)
        shutil.rmtree(tmp, ignore_errors=True)
    print("android app: all checks passed")


if __name__ == "__main__":
    main()
