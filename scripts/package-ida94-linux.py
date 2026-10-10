#!/usr/bin/env python3
"""Package the Linux plugin with installation instructions and dependency licenses."""
import argparse
import hashlib
from pathlib import Path
import re
import zipfile


def main():
    repository = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="")
    parser.add_argument("--binary", type=Path, default=repository / "build-ida94-linux/Ponce64.so")
    parser.add_argument("--dependencies", type=Path,
                        default=repository / ".deps/vcpkg/installed/x64-linux-static-release")
    args = parser.parse_args()
    if args.version and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.version):
        parser.error("Version must be a simple tag name")
    binary = args.binary.read_bytes()
    files = {"Ponce64.so": binary, "LICENSE": (repository / "LICENSE").read_bytes()}
    for library in ("triton", "capstone", "z3"):
        files[f"licenses/{library}.txt"] = (args.dependencies / "share" / library / "copyright").read_bytes()
    files["INSTALL.txt"] = (
        "Ponce for IDA Pro 9.4 on Linux x64\n\n"
        "Close IDA, copy Ponce64.so into <IDA Pro 9.4>/plugins/, then restart IDA.\n"
        "One plugin supports both 32-bit and 64-bit input programs.\n"
        "Triton, Capstone, and Z3 are linked statically.\n"
        "Source and build instructions: https://github.com/4xura/Ponce\n"
    ).encode()
    files["SHA256SUMS"] = (hashlib.sha256(binary).hexdigest() + "  Ponce64.so\n").encode()
    dist = repository / "dist"
    dist.mkdir(exist_ok=True)
    archive = dist / (f"ponce-{args.version}-linux.zip" if args.version else "Ponce-IDA-9.4-Linux.zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name, data in files.items():
            package.writestr("Ponce_ida94/" + name, data)
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None
        assert hashlib.sha256(package.read("Ponce_ida94/Ponce64.so")).digest() == hashlib.sha256(binary).digest()
    print(archive)


if __name__ == "__main__":
    main()
