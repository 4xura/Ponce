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
    # only in the graphical executable. The console test verifies version and loading.
    result["action_registration_checked"] = result["gui"]
    if result["gui"]:
        expected_actions = {
            "Ponce:action_chooser_add_constrain", "Ponce:action_chooser_comment",
            "Ponce:banner", "Ponce:clean", "Ponce:create_snapshot", "Ponce:delete_snapshot",
            "Ponce:enable_disable_tracing", "Ponce:negate_and_inject", "Ponce:negate_inject_restore",
            "Ponce:restore_snapshot", "Ponce:run_until_symbolic_branch",
            "Ponce:show_SymbolicVarsWindows", "Ponce:show_config", "Ponce:solve_formula_sub",
            "Ponce:taint_symbolize_memory", "Ponce:taint_symbolize_register", "Ponce:unload",
        }
        missing_actions = expected_actions - set(result["actions"])
        assert not missing_actions, "Ponce actions missing: " + repr(sorted(missing_actions))
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
