from pydm import Display

from widgets import UndulatorListWidget


class EVCalculation(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super(EVCalculation, self).__init__(parent=parent, args=args, macros=macros)
        self.config = macros
        self.setup_ui()

    def setup_ui(self):
        und_list = UndulatorListWidget()
        self.ui.frm_undulators.layout().addWidget(und_list)
        und_list.prefix = self.config.get('line_arbiter_prefix')

    def ui_filename(self):
        return 'ev_calculation.ui'
