#!/usr/bin/env python3
"""Create the key that signs the PythonOS APKs, once, so every release can be installed over the one before it.

Android only installs an update over an installed app when both are signed with the SAME key. CI used to make a throwaway key on every
run, so no APK could update another. This makes one permanent key:

    python tools/android_signing_setup.py                 make the key (in ~/.pythonos-signing) and the pin file; nothing is sent anywhere
    python tools/android_signing_setup.py --upload        also store it as the four repository secrets CI reads (needs the `gh` command, logged in)
    python tools/android_signing_setup.py --show          print the fingerprint of the key and of an APK (--apk file.apk, needs apksigner)

What it writes
  <folder>/pythonos-release.p12     the key (a PKCS12 keystore). KEEP A BACKUP: lose it and nobody can update the app, they must reinstall
  <folder>/pythonos-release.env     its passwords. Keep it as secret as the key
  OS_Export/Android/signing.sha256  the key's certificate fingerprint (public). CI refuses a release APK signed with any other key

Never commit the .p12 or the .env. The folder is outside the repository by default.
"""
import argparse
import base64
import datetime
import hashlib
import os
import secrets
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
PIN = os.path.join(REPO, "OS_Export", "Android", "signing.sha256")
DEFAULT_FOLDER = os.path.join(os.path.expanduser("~"), ".pythonos-signing")
ALIAS = "pythonos"


def make_key(folder):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    os.makedirs(folder, exist_ok=True)
    keystore = os.path.join(folder, "pythonos-release.p12")
    envfile = os.path.join(folder, "pythonos-release.env")
    if os.path.exists(keystore) or os.path.exists(envfile):
        raise SystemExit(f"{keystore} already exists. A new key would stop every installed copy from updating, so this will not replace it.\n"
                         "Use --show to see its fingerprint, or --upload to store the existing one as secrets.")
    password = secrets.token_urlsafe(24)
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PythonOS"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PythonOS")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365 * 30)).sign(key, hashes.SHA256()))
    # triple-DES / SHA-1 protection is what every Java version (and apksigner) can read; the file is protected by the password and by where it is kept
    encryption = (serialization.PrivateFormat.PKCS12.encryption_builder()
                  .kdf_rounds(50000).key_cert_algorithm(pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC).hmac_hash(hashes.SHA1())
                  .build(password.encode()))
    data = pkcs12.serialize_key_and_certificates(ALIAS.encode(), key, cert, None, encryption)
    with open(keystore, "wb") as f:
        f.write(data)
    with open(envfile, "w", encoding="utf-8") as f:
        f.write(f"ANDROID_KEYSTORE_PASSWORD={password}\nANDROID_KEY_ALIAS={ALIAS}\nANDROID_KEY_PASSWORD={password}\n")
    for path in (keystore, envfile):
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return keystore, envfile, hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def read_env(envfile):
    values = {}
    with open(envfile, encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                k, v = line.rstrip("\n").split("=", 1)
                values[k] = v
    return values


def fingerprint_of_keystore(keystore, password):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    with open(keystore, "rb") as f:
        _key, cert, _more = pkcs12.load_key_and_certificates(f.read(), password.encode())
    return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def write_pin(fingerprint):
    with open(PIN, "w", encoding="utf-8", newline="\n") as f:
        f.write(fingerprint.lower() + "\n")
    print(f"Wrote {os.path.relpath(PIN, REPO)}  (commit this: it is the public fingerprint CI checks releases against)")


def set_secret(name, value):
    result = subprocess.run(["gh", "secret", "set", name], input=value.encode(), capture_output=True)
    if result.returncode != 0:
        raise SystemExit(f"could not set {name}: {result.stderr.decode(errors='replace').strip()}")
    print(f"  stored {name}")


def upload(keystore, envfile):
    values = read_env(envfile)
    with open(keystore, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    print("Storing the key as repository secrets (GitHub keeps them encrypted; CI reads them only to sign):")
    set_secret("ANDROID_KEYSTORE_BASE64", encoded)
    set_secret("ANDROID_KEYSTORE_PASSWORD", values["ANDROID_KEYSTORE_PASSWORD"])
    set_secret("ANDROID_KEY_ALIAS", values["ANDROID_KEY_ALIAS"])
    set_secret("ANDROID_KEY_PASSWORD", values["ANDROID_KEY_PASSWORD"])


def apk_fingerprint(apk):
    import glob
    home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or ""
    tools = sorted(glob.glob(os.path.join(home, "build-tools", "*", "apksigner*")))
    if not tools:
        raise SystemExit("apksigner was not found (it is part of the Android SDK build-tools; set ANDROID_HOME)")
    out = subprocess.run([tools[-1], "verify", "--print-certs", apk], capture_output=True, text=True)
    for line in out.stdout.splitlines():
        if "certificate SHA-256 digest" in line:
            return line.rsplit(":", 1)[1].strip().lower()
    raise SystemExit(out.stderr.strip() or "the APK has no signature")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--folder", default=DEFAULT_FOLDER, help=f"where the key is kept (default {DEFAULT_FOLDER})")
    parser.add_argument("--upload", action="store_true", help="store the key as the repository secrets CI reads (uses gh)")
    parser.add_argument("--show", action="store_true", help="print fingerprints and exit")
    parser.add_argument("--apk", help="with --show: also print the fingerprint of this APK")
    args = parser.parse_args()
    keystore = os.path.join(args.folder, "pythonos-release.p12")
    envfile = os.path.join(args.folder, "pythonos-release.env")

    if args.show:
        if os.path.exists(keystore):
            print("key        ", fingerprint_of_keystore(keystore, read_env(envfile)["ANDROID_KEYSTORE_PASSWORD"]))
        if os.path.exists(PIN):
            print("pinned     ", open(PIN, encoding="utf-8").read().strip())
        if args.apk:
            print("APK        ", apk_fingerprint(args.apk))
        return 0

    if os.path.exists(keystore):
        print(f"Using the existing key in {args.folder}")
        fingerprint = fingerprint_of_keystore(keystore, read_env(envfile)["ANDROID_KEYSTORE_PASSWORD"])
    else:
        keystore, envfile, fingerprint = make_key(args.folder)
        print(f"Made the key: {keystore}\nIts passwords:  {envfile}")
        print("\nBACK THESE TWO FILES UP NOW (a password manager or an encrypted drive). Without this key nobody can update the app.")
    print(f"Certificate SHA-256: {fingerprint}")
    write_pin(fingerprint)
    if args.upload:
        upload(keystore, envfile)
    else:
        print("\nNext: run again with --upload to store it as the repository secrets, or add ANDROID_KEYSTORE_BASE64, "
              "ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_ALIAS and ANDROID_KEY_PASSWORD yourself.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
