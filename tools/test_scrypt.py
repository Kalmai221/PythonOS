#!/usr/bin/env python3
"""Passwords: new ones are hashed with scrypt where this Python has it (PBKDF2 where it does not), older PBKDF2 and legacy hashes still log in and are
upgraded the next time the password is typed, and a hash with lighter settings is replaced by a current one."""
import hashlib
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)
os.chdir(tempfile.mkdtemp(prefix="pyos-scrypt-"))
os.makedirs(".OSData", exist_ok=True)

import users  # noqa: E402


def main():
    password = "tiger-Mountain-violet-5921!x"
    have = users.scrypt_available()
    stored = users.hash_password(password)
    if have:
        assert stored.startswith(f"scrypt${users.SCRYPT_N}${users.SCRYPT_R}${users.SCRYPT_P}$"), stored
        assert users.verify_password(password, stored) and not users.verify_password("wrong", stored)
        assert users.hash_password(password) != stored, "a new salt every time"
        assert not users.needs_upgrade(stored)
        # the settings are stored in the hash, so raising them later still reads the old ones; lighter ones get replaced
        light = users._scrypt(password, "00" * 16, 2 ** 14, 8, 1)
        old = f"scrypt$16384$8$1${'00' * 16}${light}"
        assert users.verify_password(password, old) and users.needs_upgrade(old)
        assert users.needs_upgrade("scrypt$broken")
    else:
        assert stored.startswith("pbkdf2$") and users.verify_password(password, stored) and not users.needs_upgrade(stored)
    # an older PBKDF2 hash and the legacy unsalted SHA-256 still verify
    salt = "ab" * 16
    pbkdf2 = f"pbkdf2${users.PBKDF2_ROUNDS}${salt}${hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), users.PBKDF2_ROUNDS).hex()}"
    assert users.verify_password(password, pbkdf2) and not users.verify_password("wrong", pbkdf2)
    assert users.needs_upgrade(pbkdf2) == have
    legacy = hashlib.sha256(password.encode()).hexdigest()
    assert users.verify_password(password, legacy) and users.needs_upgrade(legacy)
    # a system with no scrypt: new hashes are PBKDF2, scrypt hashes cannot be checked (and are not accepted), nothing raises
    real = users._scrypt_ok
    users._scrypt_ok = False
    try:
        assert users.hash_password(password).startswith("pbkdf2$")
        assert not users.needs_upgrade(pbkdf2)
    finally:
        users._scrypt_ok = real
    # logging in upgrades an older hash, and a wrong password changes nothing
    users.USER_DB = "users.json"
    users.save_users({"bob": {"password": pbkdf2, "role": "admin"}})
    ok, _ = users.authenticate("bob", "wrong")
    assert not ok and users.get_users()["bob"]["password"] == pbkdf2
    ok, _ = users.authenticate("bob", password)
    assert ok
    after = users.get_users()["bob"]["password"]
    assert after.startswith("scrypt$" if have else "pbkdf2$") and users.verify_password(password, after)
    print("passwords (scrypt): all checks passed" + ("" if have else " (this Python has no scrypt: the PBKDF2 path was checked)"))


if __name__ == "__main__":
    main()
