import argparse
import logging
from pathlib import Path

from pydm import PyDMApplication
from pydm.utilities.macro import parse_macro_string

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
        '--area',
        required=True,
        choices=("KFE", "LFE", "TST"),
        help="Which area's configuration to load"
    )

    parser.add_argument(
        '--log_level',
        help='Configure logging level',
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO"
    )

    return parser


class WindowStartsHiddenPyDMApplication(PyDMApplication):
    """
    Force the main window to stay hidden until after loading the GUI.

    If not used, then we get a blank grey PyDMMainWindow during loads.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.main_window.show()

    def make_main_window(self, *args, **kwargs):
        super().make_main_window(*args, **kwargs)
        self.main_window.hide()


def main():
    """
    Mimics relevant portions of pydm_launcher.main, for bundling into pmpsui entrypoint
    """
    parser = make_parser()
    args = parser.parse_args()

    try:
        """
        We must import QtWebEngineWidgets before creating a QApplication
        otherwise we get the following error if someone adds a WebView at Designer:
        ImportError: QtWebEngineWidgets must be imported before a QCoreApplication instance is created
        """
        from qtpy import QtWebEngineWidgets  # noqa: F401
    except ImportError:
        logger.debug("QtWebEngine is not supported.")
    # end of pydm launcher vendoring


    macros = parse_macro_string(f"CFG={args.area}")

    cli_args = ['--log_level', args.log_level]
    if args.no_web:
        cli_args = ['--no-web'] + cli_args

    # Here we supply the path to PyDMApplication, without doing this teardown
    # results in channel connection errors.  (create QApp, create display, exec)
    qapp = WindowStartsHiddenPyDMApplication(
        ui_file=Path(__file__).parent / 'pmps.py',
        command_line_args=cli_args,
        macros=macros,
        use_main_window=False,
        hide_nav_bar=True,
    )
    qapp.exec_()
