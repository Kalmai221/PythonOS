"""Tests marketplace API 2: plain requirements only, and libraries installed from a local wheel (no network) into the package's own .libs folder."""
import importlib.util
import os
import shutil
import sys
import tempfile
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from pyos import marketapi  # noqa: E402

for good in ("yt-dlp", "requests>=2.31", "requests>=2.31,<3", "rich[jupyter]==13.7.1", "a_b.c-d~=1.0"):
    assert marketapi.valid_pip_spec(good), good
for bad in ("git+https://example.invalid/x", "--index-url=http://evil", "pkg @ https://example.invalid/x.whl", "a b", "./local", "x;python_version>'3'", "", None):
    assert not marketapi.valid_pip_spec(bad), bad
assert marketapi.pip_specs({"pip": ["yt-dlp"]}) == ["yt-dlp"] and marketapi.pip_specs({}) == []
try:
    marketapi.pip_specs({"pip": ["a", "--user"]})
    raise SystemExit("an option must be refused")
except ValueError:
    pass
assert marketapi.compatibility({"api": 2})[0] and not marketapi.compatibility({"api": 3})[0]

work = tempfile.mkdtemp(prefix="pyos-pip-")
try:
    wheels = os.path.join(work, "wheels")
    os.makedirs(wheels)
    with zipfile.ZipFile(os.path.join(wheels, "tinydemo-1.0-py3-none-any.whl"), "w") as z:
        z.writestr("tinydemo/__init__.py", "VALUE = 42\n")
        z.writestr("tinydemo-1.0.dist-info/METADATA", "Metadata-Version: 2.1\nName: tinydemo\nVersion: 1.0\n")
        z.writestr("tinydemo-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        z.writestr("tinydemo-1.0.dist-info/RECORD", "tinydemo/__init__.py,,\ntinydemo-1.0.dist-info/METADATA,,\ntinydemo-1.0.dist-info/WHEEL,,\ntinydemo-1.0.dist-info/RECORD,,\n")
    os.environ["PYOS_PIP_ARGS"] = f'--no-index --find-links "{wheels}"'
    spec = importlib.util.spec_from_file_location("marketplace_pip_test", os.path.join(REPO, "programs", "marketplace.py"))
    market = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(market)
    target = os.path.join(work, "app", ".libs")
    market.install_pip(["tinydemo"], target)
    assert os.path.isfile(os.path.join(target, "tinydemo", "__init__.py")), "the library must be in the app's own folder"
    try:
        market.install_pip(["no-such-library-anywhere"], os.path.join(work, "other"))
        raise SystemExit("a library that cannot be found must fail the install")
    except RuntimeError as e:
        assert "could not install" in str(e), e
    from pathlib import Path
    folder = Path(work) / "app"
    (folder / ".libs" / ".specs").write_text('["tinydemo"]')
    assert market.libs_ready(folder, ["tinydemo"]) and not market.libs_ready(folder, ["tinydemo", "other"]), "an update keeps libraries that did not change"
finally:
    shutil.rmtree(work, ignore_errors=True)
print("marketplace API 2 ok")
