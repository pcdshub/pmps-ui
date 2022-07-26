import webbrowser

from pydm import Display
from qtpy import QtCore


class GrafanaLogDisplay(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=None)
        self.config = macros
        self.setup_ui()

    def setup_ui(self):
        self.dash_url = self.config.get('dashboard_url')
        self.web_open = False
        self.ui.btn_open_browser.clicked.connect(self.handle_open_browser)

    def open_webpage_if_tab(self, tab_index):
        if tab_index == 6 and not self.web_open:
            self.ui.webbrowser.load(QtCore.QUrl(self.dash_url))
            self.web_open = True
        elif self.web_open:
            self.ui.webbrowser.load(QtCore.QUrl('about:blank'))
            self.web_open = False

    def handle_open_browser(self):
        url = self.ui.webbrowser.url().toString()
        if url:
            webbrowser.open(url, new=2, autoraise=True)

    def ui_filename(self):
        return 'grafana_log_display.ui'
