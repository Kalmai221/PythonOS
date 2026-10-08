from pyos import checksum

config = {"name": "sha256sum", "description": "SHA-256 checksum of files (or piped text): sha256sum <file>...  |  sha256sum -c <list>"}


def execute(args=None):
    return checksum.run("sha256sum", "sha256", args)
