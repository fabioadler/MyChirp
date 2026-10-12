"""Per-radio Developer tab: features, raw dump, serial info, versions.

Only added to a radio tab when the View > Developer mode toggle is on.
"""

import logging

from PySide6.QtWidgets import QTabWidget, QTextEdit, QVBoxLayout, QWidget

from mychirp.pysideui.i18n import _
from mychirp.pysideui.services.radio_service import get_service
from mychirp.pysideui.dialogs import devtools

LOG = logging.getLogger(__name__)


class DeveloperTab(QWidget):

    def __init__(self, eset, state, parent=None):
        super().__init__(parent)
        self.eset = eset
        self.state = state

        root = QVBoxLayout(self)
        tabs = QTabWidget(self)
        root.addWidget(tabs)

        self.features_view = QTextEdit()
        self.features_view.setReadOnly(True)
        devtools.make_monospace(self.features_view)
        features = eset.features
        bounds = getattr(features, "memory_bounds", None)
        lines = [
            devtools.versions_text(), "",
            _("Radio: %s") % eset.radio_label,
            _("Class: %s") % type(eset.radio).__name__,
        ]
        if bounds:
            lines.append(_("Memory bounds: %s..%s") % (bounds[0], bounds[1]))
        lines.append(_("Has valid tones: %s")
                     % bool(getattr(features, "valid_tones", None)))
        lines.append("")
        lines.append(devtools.features_text(features))
        self.features_view.setPlainText("\n".join(lines))
        tabs.addTab(self.features_view, _("Features"))

        self.dump_view = QTextEdit()
        self.dump_view.setReadOnly(True)
        devtools.make_monospace(self.dump_view)
        tabs.addTab(self.dump_view, _("Raw dump"))
        self._load_dump()

        self.system_view = QTextEdit()
        self.system_view.setReadOnly(True)
        devtools.make_monospace(self.system_view)
        self.system_view.setPlainText(
            _("Serial ports:\n%s\n\n%s")
            % (devtools.serial_ports_text(), devtools.versions_text()))
        tabs.addTab(self.system_view, _("System"))

    def _load_dump(self):
        self.dump_view.setPlainText(_("Loading raw image..."))
        service = get_service(self)

        def _dump():
            return devtools.hexdump_text(
                devtools.radio_dump_bytes(self.eset.radio))

        def done(job):
            if job.error:
                self.dump_view.setPlainText(
                    _("Failed to read image: %s") % job.error)
            else:
                self.dump_view.setPlainText(job.result)

        service.run_memory_op(_dump, self.eset.radio, on_done=done)

    def retheme(self):
        pass
