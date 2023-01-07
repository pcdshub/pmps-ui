import argparse
import logging
from functools import partial
from os import path
from typing import Optional

import yaml
from pydm import Display
from pydm.widgets import PyDMByteIndicator, PyDMLabel
from pydm.widgets.channel import PyDMChannel
from qtpy import QtCore

from beamclass_table import install_bc_setText
from tooltips import get_ev_range_tooltip, get_tooltip_for_bc
from utils import morph_into_vertical

logger = logging.getLogger(__name__)


def make_parser():
    parser = argparse.ArgumentParser(
        description='Display the PMPS diagnostic tool inside of PyDM.',
        prog='pydm pmps.py',
    )
    parser.add_argument(
        '--no-web',
        action='store_true',
        help='Disable the grafana web view tab.',
    )
    return parser


class PMPS(Display):
    new_mode_signal = QtCore.Signal(str)

    def __init__(self, parent=None, args=None, macros=None):
        parser = make_parser()
        self.user_args = parser.parse_args(args=args or [])
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

        macros_from_config = [
            'line_arbiter_prefix',
            'undulator_kicker_rate_pv',
            'accelerator_mode_pv',
        ]

        for m in macros_from_config:
            if m in macros:
                continue
            macros[m] = config.get(m)

        # add CFG macro to display the Line when starting without macros
        macros['CFG'] = config_name
        super(PMPS, self).__init__(parent=parent, args=args, macros=macros)

        self.config = config
        self._channels = []
        self.setup_ui()

    def setup_ui(self):
        self.setup_mode_selector()
        self.setup_ev_range_labels()
        self.setup_tooltips()
        self.setup_tabs()

    def setup_mode_selector(self):
        self.ui.mode_combo.addItems(
            ['Auto', 'NC', 'SC', 'Both']
        )
        self.last_mode_index = 0
        loc = PyDMChannel(
            'loc://selected_mode?type=str&init=Both',
            value_signal=self.new_mode_signal,
        )
        loc.connect()
        self._channels.append(loc)
        pvname = self.config.get('accelerator_mode_pv')
        self.last_pv_mode = None
        if pvname is not None:
            pv = PyDMChannel(
                f'ca://{pvname}',
                value_slot=self.new_mode_from_pv,
            )
            self._channels.append(pv)
        self.ui.mode_combo.activated.connect(self.new_mode_activated)

    def new_mode_activated(self, index: Optional[int] = None):
        if index is None:
            index = self.last_mode_index
        else:
            self.last_mode_index = index
        if index == 0:
            if self.last_pv_mode is None:
                self.new_mode_signal.emit('Both')
            else:
                self.new_mode_signal.emit(self.last_pv_mode)
        elif index == 1:
            self.new_mode_signal.emit('NC')
        elif index == 2:
            self.new_mode_signal.emit('SC')
        elif index == 3:
            self.new_mode_signal.emit('Both')

    def new_mode_from_pv(self, value: str):
        self.last_pv_mode = value
        self.new_mode_activated()

    def setup_ev_range_labels(self):
        labels = list(range(7, 40))
        labels.remove(23)
        for l_idx in labels:
            child_label = self.findChild(PyDMLabel, "PyDMLabel_{}".format(l_idx))
            if child_label is not None:
                morph_into_vertical(child_label)

    def setup_tooltips(self):
        labels = (self.ui.curr_bc_label, self.ui.req_bc_label)
        for label in labels:
            ch = PyDMChannel(
                label.channel,
                value_slot=partial(self.update_bc_tooltip, label=label),
            )
            ch.connect()
            self._channels.append(ch)
            install_bc_setText(label)
        self.ev_ranges = None
        self.last_ev_range = 0
        ev_definition = PyDMChannel(
            f'ca://{self.config.get("line_arbiter_prefix")}eVRangeCnst_RBV',
            value_slot=self.new_ev_ranges,
        )
        ev_definition.connect()
        self._channels.append(ev_definition)
        ev_bytes = self.ui.ev_req_bytes
        bytes_channel = PyDMChannel(
            ev_bytes.channel,
            value_slot=self.update_ev_tooltip,
        )
        bytes_channel.connect()
        self._channels.append(bytes_channel)

    def update_bc_tooltip(self, value, label):
        label.PyDMToolTip = get_tooltip_for_bc(value)

    def update_ev_tooltip(self, value=None):
        if value is None:
            value = self.last_ev_range
        else:
            self.last_ev_range = value
        if self.ev_ranges is None:
            return
        self.ui.ev_req_bytes.PyDMToolTip = get_ev_range_tooltip(value, self.ev_ranges)

    def new_ev_ranges(self, value):
        self.ev_ranges = value
        self.update_ev_tooltip()

    def setup_tabs(self):
        # We will do crazy things at this screen... avoid painting
        self.setUpdatesEnabled(False)

        self.setup_fastfaults()
        self.setup_preemptive_requests()
        self.setup_arbiter_outputs()
        self.setup_ev_calculation()
        self.setup_line_parameters_control()
        self.setup_plc_ioc_status()
        self.setup_beam_class_table()

        dash_url = self.config.get('dashboard_url')
        if self.user_args.no_web or dash_url is None:
            self.ui.tab_arbiter_outputs.removeTab(7)
        else:
            self.setup_grafana_log_display()

        # We are done... re-enable painting
        self.setUpdatesEnabled(True)

    def setup_fastfaults(self):
        # Do not import Display subclasses at the top-level, this breaks PyDM
        # if using PyDMApplication + pydm as a launcher script
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

    def setup_line_parameters_control(self):
        from line_beam_parameters import LineBeamParametersControl
        tab = self.ui.tb_line_beam_param_ctrl
        beam_widget = LineBeamParametersControl(macros=self.config)
        tab.layout().addWidget(beam_widget)

    def setup_plc_ioc_status(self):
        from plc_ioc_status import PLCIOCStatus
        tab = self.ui.tb_plc_ioc_status
        plc_widget = PLCIOCStatus(macros=self.config)
        tab.layout().addWidget(plc_widget)

    def setup_beam_class_table(self):
        from beamclass_table import BeamclassTable
        tab = self.ui.tb_beamclass_table
        beamclass_widget = BeamclassTable(macros=self.config)
        tab.layout().addWidget(beamclass_widget)

    def setup_grafana_log_display(self):
        from grafana_log_display import GrafanaLogDisplay
        tab = self.ui.tb_grafana_log_display
        grafana_widget = GrafanaLogDisplay(macros=self.config)
        self.ui.tab_arbiter_outputs.currentChanged.connect(
            grafana_widget.open_webpage_if_tab,
        )
        tab.layout().addWidget(grafana_widget)

    def ui_filename(self):
        return 'pmps.ui'

    def channels(self):
        """Make sure PyDM can find the channels we set up for cleanup."""
        return self._channels


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
