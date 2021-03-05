import json
from qtpy import QtWidgets
from pydm import Display
from pydm.widgets import PyDMEmbeddedDisplay


class PLCIOCStatus(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super(PLCIOCStatus, self).__init__(
            parent=parent, args=args, macros=macros)
        self.config = macros
        self.setup_ui()

    def setup_ui(self):
        self.setup_plc_ioc_status()

    def setup_plc_ioc_status(self):
        ffs = self.config.get('fastfaults')
        if not ffs:
            return
        if self.plc_ioc_container is None:
            return

        # TODO: does this guy need to be in the loop?
        template = 'templates/plc_ioc_entry.ui'
        for ff in ffs:
            prefix = ff.get('prefix')
            name = prefix.strip(':')
            macros = dict(P=prefix, N=name)
            widget = PyDMEmbeddedDisplay(parent=self.plc_ioc_container)
            widget.macros = json.dumps(macros)
            widget.filename = template
            widget.disconnectWhenHidden = False
            self.plc_ioc_container.layout().addWidget(widget)
        vertical_spacer = (
            QtWidgets.QSpacerItem(20, 40,
                                  QtWidgets.QSizePolicy.Preferred,
                                  QtWidgets.QSizePolicy.MinimumExpanding))
        self.plc_ioc_container.layout().addItem(vertical_spacer)

    def ui_filename(self):
        return 'plc_ioc_status.ui'
