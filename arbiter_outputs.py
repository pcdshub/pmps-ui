import json

from pydm import Display
from pydm.widgets import PyDMEmbeddedDisplay
from qtpy import QtWidgets


class ArbiterOutputs(Display):

    def __init__(self, parent=None, args=None, macros=None):
        super(ArbiterOutputs, self).__init__(parent=parent, args=args, macros=macros)
        self.config = macros
        self.setup_ui()

    def setup_ui(self):
        self.setup_outputs()

    def setup_outputs(self):
        ffs = self.config.get('fastfaults')
        if not ffs:
            return
        outs_container = self.ui.arbiter_outputs_content
        if outs_container is None:
            return
        count = 0
        for ff in ffs:
            prefix = ff.get('prefix')
            ffo_start = ff.get('ffo_start')
            ffo_end = ff.get('ffo_end')

            ffos_zfill = len(str(ffo_end)) + 1

            entries = range(ffo_start, ffo_end+1)

            template = 'templates/arbiter_outputs_entry.ui'
            for _ffo in entries:
                s_ffo = str(_ffo).zfill(ffos_zfill)
                macros = dict(index=count, P=prefix, FFO=s_ffo)
                widget = PyDMEmbeddedDisplay(parent=outs_container)
                widget.macros = json.dumps(macros)
                widget.filename = template
                widget.disconnectWhenHidden = False
                outs_container.layout().addWidget(widget)
                count += 1
        print(f'Added {count} arbiter outputs')

    def ui_filename(self):
        return 'arbiter_outputs.ui'
