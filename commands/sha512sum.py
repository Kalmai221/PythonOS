from pyos import checksum

config = {"name": "sha512sum", "description": "SHA-512 checksum of files (or piped text): sha512sum <file>...  |  sha512sum -c <list>"}


def execute(args=None):
    return checksum.run("sha512sum", "sha512", args)
