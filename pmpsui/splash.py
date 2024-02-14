from qtpy import QtCore, QtWidgets
from qtpy.QtWidgets import QSplashScreen


class PMPSSplashScreen(QSplashScreen):
    """
    A splash screen specific to PMPS, with a PMPS logo and bounding box on the
    message box
    """
    def __init__(self, *args, **kwargs):
        self.msg = ''
        super().__init__(*args, **kwargs)
        self.progress = QtWidgets.QProgressBar(self)
        splash_rect = self.geometry()
        self.progress.setGeometry(0, splash_rect.height()-20, splash_rect.width(), 20)
        self.progress.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        self.progress.setValue(50)
        self.progress.setMaximum(100)
        self.progress.setEnabled(True)

    def drawContents(self, painter):
        painter.drawText(
            self.rect_setting,
            self.alignment | QtCore.Qt.TextWordWrap,
            self.msg
        )

    def set_message_rect(self, rect: QtCore.QRect, alignment: int) -> None:
        self.rect_setting = rect
        self.alignment = alignment

    def show_message(self, msg: str) -> None:
        self.msg = msg
        self.showMessage(msg, self.alignment)

    def set_progress(self, curr: int) -> None:
        self.progress.setValue(curr)
