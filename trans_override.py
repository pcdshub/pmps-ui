from pydm import Display


class TransOverride(Display):
    """
    Class to handle display for the Transmission Override tab.
    """

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.config = macros
        self._channels = []
        self.setup_ui()

    def channels(self):
        "Make sure PyDM can find the channels we set up for cleanup."
        return self._channels

    def ui_filename(self):
        return 'trans_override.ui'

    def setup_ui(self):
        # There's no special setup for this tab yet
        # All calculations related to the values set here
        # are needed only in other tabs
        ...
