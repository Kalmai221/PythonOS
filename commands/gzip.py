from pyos import gzipfile

config = {"name": "gzip", "description": "Compress files (gzip [-k] [-d] <file>...); the original is replaced by <file>.gz unless -k keeps it. -d unpacks."}


def execute(args=None):
    return gzipfile.run("gzip", args)
