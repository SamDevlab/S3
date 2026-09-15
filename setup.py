from __future__ import annotations

import gzip
import os
import tarfile
from pathlib import Path

from setuptools import setup
from setuptools.command.sdist import sdist as _sdist


class _ReproducibleSdist(_sdist):
    """Make source archives reproducible when the build pins an epoch."""

    def make_release_tree(self, base_dir, files):
        super().make_release_tree(base_dir, files)
        epoch = os.environ.get("SOURCE_DATE_EPOCH")
        if epoch is None:
            return
        timestamp = int(epoch)
        for path in Path(base_dir).rglob("*"):
            os.utime(path, (timestamp, timestamp))

    def make_archive(
        self,
        base_name,
        format,
        root_dir=None,
        base_dir=None,
        owner=None,
        group=None,
    ):
        epoch = os.environ.get("SOURCE_DATE_EPOCH")
        if format != "gztar" or epoch is None:
            return super().make_archive(base_name, format, root_dir, base_dir, owner, group)

        timestamp = int(epoch)
        archive_name = f"{base_name}.tar.gz"
        source_root = Path(root_dir or os.curdir)
        source_base = Path(base_dir or os.curdir)
        with open(archive_name, "wb") as raw_archive:
            with gzip.GzipFile(fileobj=raw_archive, mode="wb", filename="", mtime=timestamp) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                    def normalize(member):
                        member.mtime = timestamp
                        member.uid = 0
                        member.gid = 0
                        member.uname = ""
                        member.gname = ""
                        return member

                    archive.add(source_root / source_base, filter=normalize)
        return archive_name


setup(cmdclass={"sdist": _ReproducibleSdist})
