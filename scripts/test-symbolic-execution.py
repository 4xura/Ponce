"""Exercise Ponce's debugger, symbolization and SMT handler on the owned probe."""
import json
import os
import re
import time
from pathlib import Path

import ida_auto
import ida_bytes
import ida_dbg
import ida_ida
import ida_idaapi
import ida_kernwin
import ida_loader
import ida_name
import ida_nalt
import ida_pro
import idc  # IDA's -S script argument vector
from PySide6.QtCore import QTimer

output = Path(idc.ARGV[1])
result = {"passed": False, "phase": "initializing", "expected_solution": 35}
deadline = time.monotonic() + 40
state = "entry"
addresses = {}
ip_register = "RIP" if ida_ida.inf_is_64bit() else "EIP"
result["database_bits"] = 64 if ida_ida.inf_is_64bit() else 32


def record(phase):
    result["phase"] = phase
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")


def stop_test(error=None):
    if error is not None:
        result["failed_at"] = result["phase"]
        result["error"] = repr(error)
        record("failed")
    else:
        result["passed"] = True
        record("complete")
    ida_dbg.enable_step_trace(False)
    if ida_dbg.get_process_state() != ida_dbg.DSTATE_NOTASK:
        ida_dbg.request_exit_process()
        ida_dbg.run_requests()
    QTimer.singleShot(300, lambda: ida_pro.qexit(0 if result["passed"] else 1))


def tick():
    global state
    try:
        if time.monotonic() > deadline:
            raise TimeoutError("Symbolic test timed out in phase " + state)
        process_state = ida_dbg.get_process_state()
        if state == "entry":
            if process_state == ida_dbg.DSTATE_SUSP:
                ip = ida_dbg.get_reg_val(ip_register)
                if ip != addresses["ponce_entry"]:
                    ida_dbg.request_continue_process()
                    ida_dbg.run_requests()
                else:
                    ida_dbg.del_bpt(addresses["ponce_entry"])
                    result["initial_input"] = ida_bytes.get_bytes(addresses["ponce_input"], 1, ida_bytes.GMB_READALL)[0]
                    ida_kernwin.jumpto(addresses["ponce_input"], -1, ida_kernwin.UIJMP_IDAVIEW)
                    record("symbolizing_input")
                    state = "symbolize"
        elif state == "symbolize":
            assert ida_kernwin.get_screen_ea() == addresses["ponce_input"]
            result["symbolize_action_dispatch"] = bool(ida_kernwin.process_ui_action("Ponce:taint_symbolize_memory"))
            ida_kernwin.process_ui_action("Ponce:show_SymbolicVarsWindows")
            state = "symbolic_row"
        elif state == "symbolic_row":
            row = ida_kernwin.get_chooser_data("Ponce Symbolic Variables", 0)
            result["symbolic_variable"] = row
            assert row and "SymVar_" in row[1], "Input was not symbolized"
            assert ida_dbg.is_step_trace_enabled(), "Ponce did not enable debugger tracing"
            record("tracing_arithmetic")
            state = "branch"
            ida_dbg.request_continue_process()
            ida_dbg.run_requests()
        elif state == "branch":
            if process_state == ida_dbg.DSTATE_SUSP:
                ip = ida_dbg.get_reg_val(ip_register)
                assert ip == addresses["ponce_false"], "Unexpected breakpoint"
                result["native_arithmetic_result"] = ida_dbg.get_reg_val("EAX")
                assert result["native_arithmetic_result"] == 8
                messages = ida_kernwin.msg_get_lines(150)
                summaries = [line for line in messages if "BP Instructions traced:" in line]
                assert summaries, "No Ponce tracing summary"
                summary = re.search(r"Instructions traced: (\d+) Symbolic instructions: (\d+) Symbolic conditions: (\d+)", summaries[0])
                assert summary and int(summary[3]) >= 1, "Ponce recorded no symbolic branch"
                result["trace_summary"] = summaries[0]
                ida_dbg.enable_step_trace(False)
                disassembly = ida_kernwin.find_widget("IDA View-A") or ida_kernwin.find_widget("IDA View-RIP")
                assert disassembly is not None, "Disassembly widget not found"
                ida_kernwin.activate_widget(disassembly, True)
                ida_kernwin.jumpto(addresses["ponce_branch"], -1, ida_kernwin.UIJMP_IDAVIEW)
                state = "solve"
                record("solving_branch")
        elif state == "solve":
            result["solve_screen_ea"] = hex(ida_kernwin.get_screen_ea())
            result["solve_widget"] = ida_kernwin.get_widget_title(ida_kernwin.get_current_widget())
            assert ida_kernwin.get_screen_ea() == addresses["ponce_branch"], "Disassembly cursor is not on the symbolic branch"
            # Supply the same branch metadata that Ponce's context-menu builder
            # attaches to the native solve handler. This avoids a modal popup.
            ida_kernwin.update_action_tooltip("Ponce:solve_formula_sub", "Owned probe branch. Index: 0")
            ida_kernwin.update_action_state("Ponce:solve_formula_sub", ida_kernwin.AST_ENABLE_ALWAYS)
            result["solve_action_dispatch"] = bool(ida_kernwin.process_ui_action("Ponce:solve_formula_sub"))
            state = "model"
        elif state == "model":
            messages = ida_kernwin.msg_get_lines(100)
            model_lines = [line for line in messages if re.search(r"SymVar_\d+:\s+0x", line)]
            if model_lines:
                model = re.search(r"SymVar_\d+:\s+(0x[0-9a-fA-F]+)", model_lines[0])
                result["solver_output"] = model_lines[0]
                result["solver_value"] = int(model[1], 16)
                assert result["solver_value"] == result["expected_solution"], "Incorrect solver model"
                assert result["solver_value"] + 7 == 42
                stop_test()
                return
        QTimer.singleShot(100, tick)
    except Exception as error:
        stop_test(error)


try:
    ida_auto.auto_wait()
    assert ida_loader.load_plugin("Ponce64") is not None
    for name in ("ponce_entry", "ponce_input", "ponce_branch", "ponce_true", "ponce_false"):
        ea = ida_name.get_name_ea(ida_idaapi.BADADDR, name)
        assert ea != ida_idaapi.BADADDR, "Probe symbol missing: " + name
        addresses[name] = ea
    result["addresses"] = {name: hex(ea) for name, ea in addresses.items()}
    debugger = "linux" if os.name == "posix" else "win32"
    result["debugger"] = debugger
    assert ida_dbg.load_debugger(debugger, False), "Local debugger unavailable: " + debugger
    ida_dbg.set_debugger_options(ida_dbg.DOPT_ENTRY_BPT)
    for name in ("ponce_entry", "ponce_true", "ponce_false"):
        ida_dbg.del_bpt(addresses[name])
        assert ida_dbg.add_bpt(addresses[name]), "Cannot set probe breakpoint: " + name
    executable = os.path.normpath(ida_nalt.get_input_file_path())
    record("starting_owned_probe")
    assert ida_dbg.start_process(executable, "", str(Path(executable).parent)) >= 0
    QTimer.singleShot(100, tick)
except Exception as error:
    stop_test(error)
