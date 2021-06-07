import webbrowser
from os import path

import yaml
from pydm import Display
from pydm.widgets import PyDMByteIndicator, PyDMLabel
from pydm.widgets.datetime import PyDMDateTimeEdit, TimeBase
from qtpy import QtCore, QtGui, QtWidgets


def morph_into_vertical(label):
    def minimumSizeHint(*args, **kwargs):
        s = QtWidgets.QLabel.minimumSizeHint(label)
        return QtCore.QSize(s.height(), s.width())

    def sizeHint(*args, **kwargs):
        s = QtWidgets.QLabel.sizeHint(label)
        return QtCore.QSize(s.height(), s.width())

    def paintEvent(*args, **kwargs):
        painter = QtGui.QPainter(label)
        painter.translate(label.sizeHint().width(), label.sizeHint().height())
        painter.rotate(270)

        # size of text inside the label widget
        text_w = label.fontMetrics().boundingRect(label.text()).width()
        text_h = label.fontMetrics().boundingRect(label.text()).height()
        # size of label widget
        label_h = label.sizeHint().height()
        label_w = label.sizeHint().width()
        # this will make it look like it is right (or top) justified
        pos_x = label_h - text_w
        # center the text on the bitmask
        pos_y = -(label_w - text_h)
        painter.drawText(pos_x, pos_y, label.text())

    label.minimumSizeHint = minimumSizeHint
    label.sizeHint = sizeHint
    label.paintEvent = paintEvent
    label.update()


class PMPS(Display):
    def __init__(self, parent=None, args=None, macros=None):
        if not macros:
            macros = {}
        # Fallback for old start without macros
        config_name = macros.get('CFG', 'LFE')
        # Read definitions from db file.
        c_file = path.join(path.dirname(path.realpath(__file__)),
                           f"{config_name}_config.yml")
        config = {}
        with open(c_file, 'r') as f:
            config = yaml.safe_load(f)

        macros_from_config = ['line_arbiter_prefix', 'undulator_kicker_rate_pv']

        for m in macros_from_config:
            if m in macros:
                continue
            macros[m] = config.get(m)

        # add CFG macro to display the Line when starting without macros
        macros['CFG'] = config_name
        super(PMPS, self).__init__(parent=parent, args=args, macros=macros)

        self.config = config

        self.setup_ui()

    def setup_ui(self):
        dash_url = self.config.get('dashboard_url')
        if dash_url:
            self.ui.webbrowser.load(QtCore.QUrl(dash_url))

        self.ui.btn_open_browser.clicked.connect(self.handle_open_browser)

        self.setup_ev_range_labels()
        self.setup_tabs()

    def setup_ev_range_labels(self):
        labels = list(range(7, 40))
        labels.remove(23)
        for l_idx in labels:
            l = self.findChild(PyDMLabel, "PyDMLabel_{}".format(l_idx))
            if l is not None:
                morph_into_vertical(l)

    def setup_tabs(self):
        # We will do crazy things at this screen... avoid painting
        self.setUpdatesEnabled(False)

        self.setup_fastfaults()
        self.setup_preemptive_requests()
        self.setup_arbiter_outputs()
        self.setup_ev_calculation()
        self.setup_line_parameters_contorl()
        self.setup_plc_ioc_status()

        # We are done... re-enable painting
        self.setUpdatesEnabled(True)

    def setup_fastfaults(self):
        from fast_faults import FastFaults

        tab = self.ui.tb_fast_faults
        ff_widget = FastFaults(macros=self.config)
        tab.layout().addWidget(ff_widget)

    def setup_preemptive_requests(self):
        from preemptive_requests import PreemptiveRequests

        tab = self.ui.tb_preemptive_requests
        pr_widget = PreemptiveRequests(macros=self.config)
        tab.layout().addWidget(pr_widget)

    def setup_arbiter_outputs(self):
        from arbiter_outputs import ArbiterOutputs

        tab = self.ui.tb_arbiter_outputs
        ao_widget = ArbiterOutputs(macros=self.config)
        tab.layout().addWidget(ao_widget)

    def setup_ev_calculation(self):
        from ev_calculation import EVCalculation
        tab = self.ui.tb_ev_calculation
        ev_widget = EVCalculation(macros=self.config)
        tab.layout().addWidget(ev_widget)

    def setup_line_parameters_contorl(self):
        from line_beam_parameters import LineBeamParametersControl
        tab = self.ui.tb_line_beam_param_ctrl
        beam_widget = LineBeamParametersControl(macros=self.config)
        tab.layout().addWidget(beam_widget)

    def setup_plc_ioc_status(self):
        from plc_ioc_status import PLCIOCStatus
        tab = self.ui.tb_plc_ioc_status
        plc_widget = PLCIOCStatus(macros=self.config)
        tab.layout().addWidget(plc_widget)

    def handle_open_browser(self):
        url = self.ui.webbrowser.url().toString()
        if url:
            webbrowser.open(url, new=2, autoraise=True)

    def ui_filename(self):
        return 'pmps.ui'


# Hack for negative bitmasks
def update_indicators(self):
    """
    Update the inner bit indicators accordingly with the new value.
    """
    if self._shift < 0:
        value = int(self.value) << abs(self._shift)
    else:
        value = int(self.value) >> self._shift
    if value < 0:
        value = 2**32 + value

    bits = [(value >> i) & 1
            for i in range(self._num_bits)]
    for bit, indicator in zip(bits, self._indicators):
        if self._connected:
            c = self._on_color if bit else self._off_color
        else:
            c = self._disconnected_color
        indicator.setColor(c)


PyDMByteIndicator.update_indicators = update_indicators


# Hack for broken datetime widget
def send_value(self):
    val = self.dateTime()
    now = QtCore.QDateTime.currentDateTime()
    if self._block_past_date and val < now:
        #logger.error('Selected date cannot be lower than current date.')
        print('Selected date cannot be lower than current date.')
        return

    if self.relative:
        new_value = now.msecsTo(val)
    else:
        new_value = val.toMSecsSinceEpoch()

    if self.timeBase == TimeBase.Seconds:
        new_value /= 1000.0
    self.send_value_signal.emit(new_value)


PyDMDateTimeEdit.send_value = send_value
