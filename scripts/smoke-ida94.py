"""Run inside IDA 9.4 with -A -S"smoke-ida94.py result.json" on a disposable input."""
import json
from pathlib import Path

import ida_auto
import ida_ida
import ida_kernwin
import ida_loader
import ida_pro
import idc

result = {"kernel_version": ida_kernwin.get_kernel_version()}
exit_code = 1
try:
    ida_auto.auto_wait()
    result["database_bits"] = 64 if ida_ida.inf_is_64bit() else 32
    plugin = ida_loader.load_plugin("Ponce64")
    result["plugin_loaded"] = plugin is not None
    result["gui"] = bool(ida_kernwin.is_idaq())
    result["actions"] = sorted(
        name for name in ida_kernwin.get_registered_actions() if name.startswith("Ponce:")
    )
    assert result["kernel_version"].startswith("9.4"), result
    assert result["plugin_loaded"], "Ponce64 did not load"
    # idat implements GUI action functions as stubs; enumeration is meaningful
    # only in ida.exe. The console test verifies version and DLL loading.
    result["action_registration_checked"] = result["gui"]
    if result["gui"]:
        assert "Ponce:banner" in result["actions"], "Ponce actions were not registered"
        ida_kernwin.process_ui_action("Ponce:show_SymbolicVarsWindows")
        result["symbolic_variables_window"] = ida_kernwin.find_widget("Ponce Symbolic Variables") is not None
        assert result["symbolic_variables_window"], "Symbolic-variable window did not open"
    result["passed"] = True
    exit_code = 0
except Exception as error:
    result["passed"] = False
    result["error"] = repr(error)
finally:
    Path(idc.ARGV[1]).write_text(json.dumps(result, indent=2), encoding="utf-8")
    ida_pro.qexit(exit_code)
