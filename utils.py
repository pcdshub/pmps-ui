import functools
from typing import Callable

from pydm.widgets.base import PyDMWidget
from pydm.widgets.channel import PyDMChannel
from qtpy import QtCore, QtGui, QtWidgets


def morph_into_vertical(label: QtWidgets.QLabel):
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

    # Unbind the size restrictions from the ui file that make it viewable in designer
    label.setMaximumWidth(label.maximumHeight())

    label.minimumSizeHint = minimumSizeHint
    label.sizeHint = sizeHint
    label.paintEvent = paintEvent
    label.update()


class BackCompat(QtCore.QObject):
    """
    Collector of channels for backwards compatibility.

    This is a class instead of bare functions so we can hold and clean up
    channels at the end of the process.
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Copy some of the channel handling from PyDM for cleanup
        # This otherwise requires a full "widget" and is annoying
        # I'm not 100% sure if this works or not or if that matters
        self._channels = []

    def channels(self) -> list[PyDMChannel]:
        """
        Helper for proper channel cleanup.
        """
        return self._channels()

    def add_alternate_channel(self, widget: PyDMWidget, channel: str) -> None:
        """
        Add an alternate channel for the widget.

        When the alternate channel connects, it will be assigned to the widget
        instead of the widget's original chanenl.

        This is intended to be used for PV name changes so that either name will work.

        Parameters
        ----------
        widget : PyDMWidget
            A widget that has a singular "channel" property that holds the channel
            address that can be updated.
        channel : str
            A channel address to use as the alternate channel.
        """
        # Assign the alt channel somewhere so it doesn't get garbage collected
        ch = PyDMChannel(
            address=channel,
            connection_slot=functools.partial(
                self.apply_alt_channel,
                widget=widget,
                channel=channel,
            ),
        )
        ch.connect()
        self._channels.append(ch)

    def apply_alt_channel(
        self,
        connected: bool,
        widget: PyDMWidget,
        channel: str,
    ) -> None:
        """
        Connection callback for updating a widget's default channel.

        This will be called when the alternate channel connects.

        Parameters
        ----------
        connected : bool
            Boolean from the connection_state_signal that lets us know if
            the alternate channel is connected.
        widget : PyDMWidget
            Widget to update
        channel : str
            Alternate channel to apply.
        """
        if connected and widget.channel != channel:
            widget.channel = channel

    def add_ev_ranges_alternate(self, widget: PyDMWidget) -> None:
        """
        Handle the evRanges PV name change.

        Currently, some IOCs are using "PhotonEnergyRanges" and the
        newer IOCs are using "eVRanges" to appropriately shorten the PV names.

        The .ui files have been updated to use "eVRanges" and this function
        will use add_alternate_channel for backwards compatibility
        until we've updated every IOC.
        """
        return self.add_alternate_channel(
            widget=widget,
            channel=widget.channel.replace("eVRanges", "PhotonEnergyRanges")
        )
