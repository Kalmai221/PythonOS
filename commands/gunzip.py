from pyos import gzipfile

config = {"name": "gunzip", "description": "Unpack gzip files (gunzip [-k] <file.gz>...); the .gz is removed unless -k keeps it."}


def execute(args=None):
    return gzipfile.run("gunzip", args, decompress=True)
