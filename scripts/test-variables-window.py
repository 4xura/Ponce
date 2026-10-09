"""GUI regression: an empty symbolic table must open, refresh and reopen safely."""
import json
from pathlib import Path

import ida_auto
import ida_kernwin
import ida_loader
import ida_pro
import idc
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QCoreApplication, QEvent

result_path = Path(idc.ARGV[1])
result = {"passed": False, "phase": "start"}

def checkpoint(phase):
    result["phase"] = phase
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

class ForeignChooser(ida_kernwin.Choose):
    def __init__(self):
        super().__init__("Ponce regression foreign chooser", [["Test row", 20]])
    def OnGetSize(self):
        return 1
    def OnGetLine(self, n):
        return ["Unrelated chooser row"]

foreign_chooser = ForeignChooser()

def finish_test():
    try:
        widget = ida_kernwin.find_widget("Ponce Symbolic Variables")
        assert widget is not None
        if not result.get("functions_ready"):
            checkpoint("switching_to_foreign_chooser")
            foreign_chooser.Show(modal=False)
            functions = ida_kernwin.find_widget("Ponce regression foreign chooser")
            assert functions is not None, "Foreign chooser widget not found"
            ida_kernwin.activate_widget(functions, True)
            result["functions_ready"] = True
            QTimer.singleShot(300, finish_test)
            return
        functions = ida_kernwin.find_widget("Ponce regression foreign chooser")
        assert functions is not None, "Foreign chooser widget not found"
        if functions is not None:
            ida_kernwin.activate_widget(functions, True)
            QApplication.processEvents()
            result["current_widget"] = ida_kernwin.get_widget_title(ida_kernwin.get_current_widget())
            checkpoint("rejecting_foreign_chooser_action")
            ida_kernwin.process_ui_action("Ponce:action_chooser_comment")
            ida_kernwin.process_ui_action("Ponce:action_chooser_add_constrain")
        checkpoint("refreshing")
        ida_kernwin.refresh_chooser("Ponce Symbolic Variables")
        QApplication.processEvents()
        checkpoint("closing")
        ida_kernwin.close_widget(widget, ida_kernwin.WCLS_SAVE)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()
        checkpoint("reopening")
        ida_kernwin.process_ui_action("Ponce:show_SymbolicVarsWindows")
        QApplication.processEvents()
        widget = ida_kernwin.find_widget("Ponce Symbolic Variables")
        assert widget is not None
        ida_kernwin.close_widget(widget, ida_kernwin.WCLS_SAVE)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()
        result["passed"] = True
        checkpoint("complete")
    except Exception as error:
        result["failed_at"] = result["phase"]
        result["error"] = repr(error)
        checkpoint("failed")
    ida_pro.qexit(0 if result["passed"] else 1)

def begin_test():
    checkpoint("opening")
    ida_kernwin.process_ui_action("Ponce:show_SymbolicVarsWindows")
    checkpoint("processing_open_events")
    QTimer.singleShot(300, finish_test)

try:
    ida_auto.auto_wait()
    assert ida_loader.load_plugin("Ponce64") is not None
    QTimer.singleShot(300, begin_test)
except Exception as error:
    result["error"] = repr(error)
    checkpoint("failed")
    ida_pro.qexit(1)
