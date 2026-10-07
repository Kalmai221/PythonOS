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

    tmp = tempfile.mkdtemp()
    try:
        installs = []
        fake_bootstrap = types.ModuleType("bootstrap")
        fake_bootstrap.install = lambda dest, log=print, **k: (installs.append(dest), True)[1]
        sys.modules["bootstrap"] = fake_bootstrap
        identity = types.ModuleType("pyos_export")
        identity.INFO = {"platform": "android", "version": "1.0.12", "api": 2}
        sys.modules["pyos_export"] = identity
        said = []

        # first installation: the app has just downloaded the core itself, so nothing is done, and the app version is remembered
        assert app.refresh_core_after_app_update(tmp, said.append) is True
        assert installs == [] and open(os.path.join(tmp, ".app_version"), encoding="utf-8").read() == "1.0.12"

        # the same app starting again: nothing to do
        assert app.refresh_core_after_app_update(tmp, said.append) is True and installs == []

        # a new APK installed over the old one (the remembered version differs): the core is brought up to date
        identity.INFO = {"platform": "android", "version": "1.0.13", "api": 2}
        assert app.refresh_core_after_app_update(tmp, said.append) is True
        assert installs == [tmp] and open(os.path.join(tmp, ".app_version"), encoding="utf-8").read() == "1.0.13"
        assert any("1.0.13" in line for line in said)

        # offline: it says so, does not remember the new version, and tries again at the next start
        identity.INFO = {"platform": "android", "version": "1.0.14", "api": 2}
        fake_bootstrap.install = lambda dest, log=print, **k: False
        said.clear()
        assert app.refresh_core_after_app_update(tmp, said.append) is False
        assert open(os.path.join(tmp, ".app_version"), encoding="utf-8").read() == "1.0.13" and any("try again" in line for line in said)
        fake_bootstrap.install = lambda dest, log=print, **k: (installs.append(dest), True)[1]
        installs.clear()
        assert app.refresh_core_after_app_update(tmp, said.append) is True and installs == [tmp]

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
