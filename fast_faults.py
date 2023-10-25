import functools
import itertools
import json
from string import Template

from pydm import Display
from pydm.widgets import PyDMEmbeddedDisplay
from pydm.widgets.channel import PyDMChannel
from pydm.widgets.datetime import PyDMDateTimeEdit, PyDMDateTimeLabel
from qtpy import QtCore, QtWidgets


def clear_channel(ch):
    if ch:
        try:
            ch.disconnect()
        except:
            pass


class VisibilityEmbedded(PyDMEmbeddedDisplay):

    def __init__(self, channel=None, *args, **kwargs):
        super(VisibilityEmbedded, self).__init__(*args, **kwargs)
        self.setVisible(False)
        self._connected = None
        self.channel = None
        if channel:
            self.channel = PyDMChannel(channel, connection_slot=self.connection_changed)
        self.destroyed.connect(functools.partial(clear_channel, channel))

    def connection_changed(self, status):
        self._connected = status
        if not status:
            self.setVisible(False)

    @QtCore.Slot(list)
    def update_filter(self, filters):
        self.rules = "[]"

        if not filters and self._connected:
            self.setVisible(True)
            return
        channels = []
        conditions = []
        for idx, filter in enumerate(filters):
            ch = Template(filter['channel']).safe_substitute(**self.parsed_macros())
            conditions.append(f'ch[{idx}] == {filter["condition"]}')
            channels.append(dict(channel=ch, trigger=True))

        rule = {
            "name": "FF_Visibility",
            "property": "Visible",
            "channels": channels,
            "expression": " and ".join(conditions)
        }
        rules = json.dumps([rule])
        self.rules = rules


class FastFaults(Display):
    filters_changed = QtCore.Signal(list)

    def __init__(self, parent=None, args=None, macros=None):
        super(FastFaults, self).__init__(parent=parent, args=args, macros=macros)
        self.config = macros
        self.setup_ui()

    def setup_ui(self):
        self.ui.btn_apply_filters.clicked.connect(self.update_filters)
        self.setup_fastfaults()
        self.setup_datetimes()

    def setup_fastfaults(self):
        ffs = self.config.get('fastfaults')
        if not ffs:
            return
        ff_container = self.ui.fastfaults_content
        if ff_container is None:
            return
        count = 0
        for ff in ffs:
            prefix = ff.get('prefix')
            ffo_start = ff.get('ffo_start')
            ffo_end = ff.get('ffo_end')
            ff_start = ff.get('ff_start')
            ff_end = ff.get('ff_end')

            ffos_zfill = len(str(ffo_end)) + 1
            ffs_zfill = len(str(ff_end)) + 1

            entries = itertools.product(
                range(ffo_start, ffo_end+1),
                range(ff_start, ff_end+1)
            )
            template = 'templates/fastfaults_entry.ui'
            for _ffo, _ff in entries:
                s_ffo = str(_ffo).zfill(ffos_zfill)
                s_ff = str(_ff).zfill(ffs_zfill)
                macros = dict(index=count, P=prefix, FFO=s_ffo, FF=s_ff)
                ch = Template('ca://${P}FFO:${FFO}:FF:${FF}:Info:InUse_RBV').safe_substitute(**macros)
                widget = VisibilityEmbedded(parent=ff_container, channel=ch)
                widget.prefixes = macros
                self.filters_changed[list].connect(widget.update_filter)
                widget.macros = json.dumps(macros)
                widget.filename = template
                widget.disconnectWhenHidden = False
                ff_container.layout().addWidget(widget)
                count += 1
        vertical_spacer = QtWidgets.QSpacerItem(20, 40,
                                                QtWidgets.QSizePolicy.Preferred,
                                                QtWidgets.QSizePolicy.MinimumExpanding)
        ff_container.layout().addItem(vertical_spacer)
        self.update_filters()
        print(f'Added {count} fast faults')

    def ui_filename(self):
        return 'fast_faults.ui'

    def update_filters(self):
        default_options = [
            {
                'name': 'inuse',
                'channel': 'ca://${P}FFO:${FFO}:FF:${FF}:Info:InUse_RBV',
                'condition': '"TRUE"',
            }
        ]
        options = [
            {'name': 'ok', 'channel': 'ca://${P}FFO:${FFO}:FF:${FF}:OK_RBV'},
            {'name': 'beampermitted', 'channel': 'ca://${P}FFO:${FFO}:FF:${FF}:BeamPermitted_RBV'},
            {'name': 'vetoed', 'channel': 'ca://${P}FFO:${FFO}:EnableVeto_RBV'},
            {'name': 'bypassed', 'channel': 'ca://${P}FFO:${FFO}:FF:${FF}:Ovrd:Active_RBV'}
        ]
        filters = []
        for opt in default_options:
            filters.append(opt)
        for opt in options:
            gb = self.findChild(QtWidgets.QGroupBox, f"ff_filter_gb_{opt['name']}")
            cb = self.findChild(QtWidgets.QComboBox, f"ff_filter_cb_{opt['name']}")
            if gb.isChecked():
                opt['condition'] = '"' + str(cb.currentText()).upper() + '"'
                filters.append(opt)
        self.filters_changed.emit(filters)

    def setup_datetimes(self):
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_min_times)
        self.timer.singleShot(1000, self.update_min_times)
        self.timer.start(10000)
        self.dt_channel = PyDMChannel(
            self.ui.PyDMDateTimeLabel.channel,
            value_slot=self.update_time_delta,
        )
        self.dt_channel.connect()
        self.destroyed.connect(
            functools.partial(
                clear_channel,
                self.dt_channel,
            )
        )

    def update_min_times(self):
        current_time = QtCore.QDateTime.currentSecsSinceEpoch()
        latest_minute = current_time // 60 * 60
        min_time = QtCore.QDateTime.fromSecsSinceEpoch(latest_minute)
        for widget in self.findChildren(PyDMDateTimeEdit, 'ExpirationSelect'):
            widget.setMinimumDateTime(min_time)

    def update_time_delta(self, arbiter_time):
        client_time = QtCore.QDateTime.currentSecsSinceEpoch()
        diff = arbiter_time - client_time
        text = f'({diff:+d}s)'
        self.ui.time_delta_label.setText(text)
        if abs(diff) >= 5:
            self.ui.time_delta_label.setStyleSheet("QLabel { color : red; }")
        elif abs(diff) < 2:
            self.ui.time_delta_label.setStyleSheet("QLabel { color : black; }")
