import argparse
import logging
from functools import partial
from os import path
from pathlib import Path
from typing import Optional, Union

import yaml
from pydm import Display
from pydm.widgets import PyDMLabel
from pydm.widgets.channel import PyDMChannel
from qtpy import QtCore, QtGui
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import QApplication

from pmpsui.beamclass_table import install_bc_setText
from pmpsui.splash import PMPSSplashScreen
from pmpsui.tooltips import (get_mode_tooltip_lines, get_tooltip_for_bc,
                             setup_combobox_tooltip)
from pmpsui.utils import BackCompat, morph_into_vertical
from pmpsui.widgets import EvByteIndicator

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
    parser.add_argument(
        '--log_level',
        help='Configure logging level',
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO"
    )
    return parser


class PMPS(Display):
    new_mode_signal = QtCore.Signal(str)

    def __init__(self, parent=None, args=None, macros=None):
        # self.user_args = args
        # Assumes args are passed as list of [no_web, log_level] as in main.py
        self.splash: Optional[PMPSSplashScreen] = None
        self.setup_splash()

        if not args:
            args = []

        parser = make_parser()
        self.user_args = parser.parse_args(args=args)

        logger = logging.getLogger("")
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)-8s] - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(self.user_args.log_level)
        handler.setLevel(self.user_args.log_level)

        if not macros:
            macros = {}
        # Fallback for old start without macros
        config_name = macros.get('CFG', 'LFE')
        # Read definitions from db file.
        c_file = path.join(path.dirname(path.realpath(__file__)),
                           "configs",
                           f"{config_name}_config.yml")
        config = {}
        with open(c_file, 'r') as f:
            config = yaml.safe_load(f)

        macros_from_config = [
            'line_arbiter_prefix',
            'undulator_kicker_rate_pv',
            'accelerator_mode_pv',
            'trans_req_pv',
            'trans_rbv_pv',
        ]

        for m in macros_from_config:
            if m in macros:
                continue
            macros[m] = config.get(m)

        # add CFG macro to display the Line when starting without macros
        macros['CFG'] = config_name
        super(PMPS, self).__init__(parent=parent, args=args, macros=macros)

        self.config = config
        line_arbiter_prefix = self.config.get('line_arbiter_prefix')
        if line_arbiter_prefix is not None:
            EvByteIndicator.set_range_address(f'ca://{line_arbiter_prefix}eVRangeCnst_RBV')
        self._channels = []
        self.setup_ui()

        self.splash.finish(self)
        self.splash = None

    def setup_splash(self) -> None:
        pixmap = QPixmap(str(Path(__file__).parent.parent / 'pmps_splash.png'))
        self.splash = PMPSSplashScreen(pixmap)
        self.splash.set_message_rect(QtCore.QRect(250, 100, 300, 150),
                                     alignment=QtCore.Qt.AlignLeft)

        splash_font = QtGui.QFont("Arial", 12, QtGui.QFont.Bold)
        self.splash.setFont(splash_font)
        self.splash.show_message('PMPS UI setup beginning...')
        self.splash.set_progress(0)
        self.splash.show()

    def update_splash_message(
        self,
        msg: str,
        progress: Optional[int]=None
    ) -> None:
        if self.splash is None:
            return

        if progress is not None:
            self.splash.set_progress(progress)
        self.splash.show_message(msg)
        app = QApplication.instance()
        app.processEvents()

    def setup_ui(self):
        self.update_splash_message('Setting up ui...', progress=10)
        self.setup_mode_selector()
        self.setup_ev_range_labels()
        self.setup_tooltips()
        self.update_splash_message('Set up mode selector, ev-range labels, tooltips',
                                   progress=15)
        self.setup_backcompat()
        self.update_splash_message('Begin setting up tabs', progress=20)
        self.setup_tabs()
        self.update_splash_message('Finished setting up ui', progress=100)

    def setup_mode_selector(self):
        self.ui.mode_combo.addItems(
            ['Auto', 'NC', 'SC', 'Both']
        )
        setup_combobox_tooltip(self.ui.mode_combo, get_mode_tooltip_lines())
        self.last_mode_index = 0
        loc = PyDMChannel(
            'loc://selected_mode?type=str&init=Both',
            value_signal=self.new_mode_signal,
        )
        loc.connect()
        self._channels.append(loc)
        pvname = self.config.get('accelerator_mode_pv')
        self.last_pv_mode = None
        self.last_mode_enum = None
        if pvname is not None:
            pv = PyDMChannel(
                f'ca://{pvname}',
                value_slot=self.new_mode_from_pv,
                enum_strings_slot=self.new_mode_enum_from_pv,
            )
            pv.connect()
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
                self.new_mode_signal.emit(str(self.last_pv_mode))
        elif index == 1:
            self.new_mode_signal.emit('NC')
        elif index == 2:
            self.new_mode_signal.emit('SC')
        elif index == 3:
            self.new_mode_signal.emit('Both')

    def new_mode_from_pv(self, value: Union[int, str]):
        self.last_pv_mode = value
        self.update_accl_mode()

    def new_mode_enum_from_pv(self, value: list[str]):
        self.last_mode_enum = value
        self.update_accl_mode()

    def update_accl_mode(self):
        if isinstance(self.last_pv_mode, int) and self.last_mode_enum is not None:
            try:
                self.last_pv_mode = self.last_mode_enum[self.last_pv_mode]
            except IndexError:
                # We can only get here if the enum strs change
                # Skip and wait for the next update
                pass
        if isinstance(self.last_pv_mode, str):
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

    def update_bc_tooltip(self, value, label):
        label.PyDMToolTip = get_tooltip_for_bc(value)

    def setup_backcompat(self):
        self.backcompat = BackCompat(parent=self)
        self.backcompat.add_ev_ranges_alternate(self.ui.ev_req_bytes)
        self.backcompat.add_ev_ranges_alternate(self.ui.ev_curr_bytes)

    def setup_tabs(self):
        # We will do crazy things at this screen... avoid painting
        self.setUpdatesEnabled(False)

        self.setup_fastfaults()
        # TODO: maybe figure out how to give real progress quantities?
        self.update_splash_message('Fast faults added', progress=40)

        self.setup_preemptive_requests()
        self.update_splash_message('Preemptive requests added', progress=55)

        self.setup_arbiter_outputs()
        self.update_splash_message('Arbiter outputs added', progress=65)

        self.setup_ev_calculation()
        self.update_splash_message('eV Calculation added', progress=70)

        self.setup_line_parameters_control()
        self.update_splash_message('Line parameter controls added', progress=75)

        self.setup_trans_override()
        self.update_splash_message('Transmission override added', progress=80)

        self.setup_plc_ioc_status()
        self.update_splash_message('PLC IOC Statuses added', progress=85)

        self.setup_beam_class_table()
        self.update_splash_message('Beam class table added', progress=90)

        dash_url = self.config.get('dashboard_url')
        if self.user_args.no_web or dash_url is None:
            self.ui.tab_arbiter_outputs.removeTab(8)
        else:
            self.setup_grafana_log_display()
            self.update_splash_message('Beam class table added', progress=95)

        line_arbiter_prefix = self.config.get("line_arbiter_prefix", "")
        if "LFE" in line_arbiter_prefix:
            self.ui.tab_arbiter_outputs.removeTab(6)

        # We are done... re-enable painting
        self.setUpdatesEnabled(True)

    def setup_fastfaults(self):
        # Do not import Display subclasses at the top-level, this breaks PyDM
        # if using PyDMApplication + pydm as a launcher script
        from pmpsui.fast_faults import FastFaults
        tab = self.ui.tb_fast_faults
        ff_widget = FastFaults(macros=self.config)
        tab.layout().addWidget(ff_widget)

    def setup_preemptive_requests(self):
        from pmpsui.preemptive_requests import PreemptiveRequests
        tab = self.ui.tb_preemptive_requests
        pr_widget = PreemptiveRequests(macros=self.config)
        tab.layout().addWidget(pr_widget)

    def setup_arbiter_outputs(self):
        from pmpsui.arbiter_outputs import ArbiterOutputs
        tab = self.ui.tb_arbiter_outputs
        ao_widget = ArbiterOutputs(macros=self.config)
        tab.layout().addWidget(ao_widget)

    def setup_ev_calculation(self):
        from pmpsui.ev_calculation import EVCalculation
        tab = self.ui.tb_ev_calculation
        ev_widget = EVCalculation(macros=self.config)
        tab.layout().addWidget(ev_widget)

    def setup_line_parameters_control(self):
        from pmpsui.line_beam_parameters import LineBeamParametersControl
        tab = self.ui.tb_line_beam_param_ctrl
        beam_widget = LineBeamParametersControl(macros=self.config)
        tab.layout().addWidget(beam_widget)

    def setup_trans_override(self):
        from pmpsui.trans_override import TransOverride
        tab = self.ui.tb_trans_override
        jf_widget = TransOverride(macros=self.config)
        tab.layout().addWidget(jf_widget)

    def setup_plc_ioc_status(self):
        from pmpsui.plc_ioc_status import PLCIOCStatus
        tab = self.ui.tb_plc_ioc_status
        plc_widget = PLCIOCStatus(macros=self.config)
        tab.layout().addWidget(plc_widget)

    def setup_beam_class_table(self):
        from pmpsui.beamclass_table import BeamclassTable
        tab = self.ui.tb_beamclass_table
        beamclass_widget = BeamclassTable(macros=self.config)
        tab.layout().addWidget(beamclass_widget)

    def setup_grafana_log_display(self):
        from pmpsui.grafana_log_display import GrafanaLogDisplay
        tab = self.ui.tb_grafana_log_display
        grafana_widget = GrafanaLogDisplay(macros=self.config)
        self.ui.tab_arbiter_outputs.currentChanged.connect(
            grafana_widget.open_webpage_if_tab,
        )
        tab.layout().addWidget(grafana_widget)

    def ui_filename(self):
        return 'ui/pmps.ui'

    def channels(self):
        """Make sure PyDM can find the channels we set up for cleanup."""
        return self._channels
