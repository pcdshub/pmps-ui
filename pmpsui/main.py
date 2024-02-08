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
        '--macro',
        help=("Macro subsitution to use, in JSON object format.  Same as PyDM"
              "macro substitution")
    )

    parser.add_argument(
        '--log_level',
        help='Configure logging level',
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO"
    )

    return parser


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

    macros = None
    if args.macro is not None:
        macros = parse_macro_string(args.macro)

    cli_args = ['--log_level', args.log_level]
    if args.no_web:
        cli_args = ['--no_web'] + cli_args

    # Here we supply the path to PyDMApplication, without doing this teardown
    # results in channel connection errors.  (create QApp, create display, exec)
    qapp = PyDMApplication(
        ui_file=Path(__file__).parent / 'pmps.py',
        command_line_args=cli_args,
        macros=macros,
        use_main_window=False,
        hide_nav_bar=True,
    )

    qapp.exec_()
