from pyos import checksum

config = {"name": "sha1sum", "description": "SHA-1 checksum of files (or piped text): sha1sum <file>...  |  sha1sum -c <list>"}


def execute(args=None):
    return checksum.run("sha1sum", "sha1", args)
