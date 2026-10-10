#!/usr/bin/env python3
"""Build owned ELF probes and verify Ponce in isolated IDA 9.4 sessions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import tempfile


def main():
    repository = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ida_directory", type=Path)
    parser.add_argument("--plugin", type=Path, default=repository / "build-ida94-linux/Ponce64.so")
    parser.add_argument("--sdk", type=Path, default=repository / ".deps/ida-sdk94/src")
    parser.add_argument("--dependencies", type=Path,
                        default=repository / ".deps/vcpkg/installed/x64-linux-static-release")
    args = parser.parse_args()
    ida = args.ida_directory.resolve()
    plugin = args.plugin.resolve()
    if not (ida / "ida").is_file() or not plugin.is_file():
        parser.error("Linux IDA and a built Ponce64.so are required")
    build = repository / "build-ida94-linux"
    build.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="validation-", dir=build))
    stage = run / "ida"
    stage.mkdir()
    for item in ida.iterdir():
        if item.name not in ("plugins", "cfg"):
            (stage / item.name).symlink_to(item, target_is_directory=item.is_dir())
    shutil.copytree(ida / "cfg", stage / "cfg")
    (stage / "plugins").mkdir()
    for name in ("idapython3.so", "hexx64.so", "linux_user.so", "dbg.so", "dwarf.so", "eh_parse.so"):
        (stage / "plugins" / name).symlink_to(ida / "plugins" / name)
    shutil.copy2(plugin, stage / "plugins/Ponce64.so")
    user = run / "ida-user"
    user.mkdir()
    # Reuse the user's existing acceptance state; don't alter their profile.
    original_user = Path(os.environ.get("IDAUSR", str(Path.home() / ".idapro")).split(os.pathsep)[0])
    if (original_user / "ida.reg").is_file():
        shutil.copy2(original_user / "ida.reg", user / "ida.reg")
    config_writer = run / "write-config"
    subprocess.run([
        "c++", "-std=c++17", "-D__LINUX__", "-D__X64__", "-D__EA64__", "-D__IDP__",
        "-DUSE_DANGEROUS_FUNCTIONS", "-I" + str(repository / "src"),
        "-I" + str(args.sdk.resolve() / "include"),
        "-I" + str(args.dependencies.resolve() / "include"),
        str(repository / "tests/write-symbolic-test-config.cpp"),
        "-L" + str(args.dependencies.resolve() / "lib"),
        "-ltriton", "-lcapstone", "-lz3", "-pthread", "-o", str(config_writer),
    ], check=True)
    environment = dict(os.environ, IDADIR=str(stage), IDAUSR=str(user), QT_QPA_PLATFORM="offscreen")
    summary = {"plugin_sha256": hashlib.sha256(plugin.read_bytes()).hexdigest(),
               "run_directory": str(run), "tests": []}
    print(f"Evidence directory: {run}", flush=True)
    for bits in (64, 32):
        probe = run / f"probe{bits}"
        subprocess.run(["cc", f"-m{bits}", "-nostdlib", "-no-pie", "-Wl,-e,ponce_entry", "-g",
                        str(repository / "tests/symbolic-addition-linux.S"), "-o", str(probe)], check=True)
        for name, executable, script in (
            ("console-smoke", "idat", "smoke-ida94.py"),
            ("gui-smoke", "ida", "smoke-ida94.py"),
            ("chooser-regression", "ida", "test-variables-window.py"),
            ("symbolic-execution", "ida", "test-symbolic-execution.py"),
        ):
            work = run / f"x{bits}-{name}"
            work.mkdir()
            shutil.copy2(probe, work / "probe")
            subprocess.run([str(config_writer), str(work / "Ponce.cfg")], check=True)
            output = work / "result.json"
            command = [str(stage / executable), "-A", "-L" + str(work / "ida.log"),
                       f'-S"{repository / "scripts" / script}" "{output}"', str(work / "probe")]
            with (work / "console.log").open("w") as log:
                process = subprocess.Popen(command, cwd=work, env=environment,
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    exit_code = process.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    exit_code = 124
            result = json.loads(output.read_text()) if output.exists() else {"passed": False, "error": "No JSON result"}
            passed = exit_code == 0 and result.get("passed") is True
            summary["tests"].append({"test": name, "bits": bits, "exit_code": exit_code, "result": result})
            (run / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            print(f"x{bits} {name}: {'PASS' if passed else 'FAIL'}", flush=True)
            if not passed:
                print(json.dumps(result, indent=2), flush=True)
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
