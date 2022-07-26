import argparse
import os.path
import sys

import yaml
from grafana_log_display import GrafanaLogDisplay
from pcdsutils.profile import profiler_context
from pydm import PyDMApplication
from pydm.utilities import setup_renderer
from qtpy.QtCore import QTimer

from arbiter_outputs import ArbiterOutputs
from ev_calculation import EVCalculation
from fast_faults import FastFaults
from line_beam_parameters import LineBeamParametersControl
from plc_ioc_status import PLCIOCStatus
from preemptive_requests import PreemptiveRequests

options = {
    'fast_faults': FastFaults,
    'preemptive_requests': PreemptiveRequests,
    'arbiter_outputs': ArbiterOutputs,
    'ev_calculation': EVCalculation,
    'line_beam_parameters': LineBeamParametersControl,
    'plc_ioc_status': PLCIOCStatus,
    'grafana_log_dispaly': GrafanaLogDisplay,
}


def load_config(cfg: str) -> dict:
    config_file = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            f"{cfg}_config.yml",
    )
    with open(config_file, 'r') as fd:
        return yaml.safe_load(fd)


def main(args):
    module = args.tab.lower()
    Cls = options[module]
    setup_renderer()
    app = PyDMApplication(use_main_window=False)

    with profiler_context(module_names=['pydm', 'PyQt5', module], filename=f'{module}.prof'):
        tab = Cls(macros=load_config(args.cfg.upper()))
        tab.show()

        if args.close:
            close_timer = QTimer()
            close_timer.setSingleShot(True)
            close_timer.timeout.connect(tab.close)
            close_timer.start(1000)

        app.exec_()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('cfg')
    parser.add_argument('tab')
    parser.add_argument('--close', action='store_true')
    args = parser.parse_args()
    main(args)
