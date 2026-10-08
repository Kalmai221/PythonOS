from pyos import checksum

config = {"name": "md5sum", "description": "MD5 checksum of files (or piped text): md5sum <file>...  |  md5sum -c <list>"}


def execute(args=None):
    return checksum.run("md5sum", "md5", args)
