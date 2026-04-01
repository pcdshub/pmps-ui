import logging

from pydm.widgets.datetime import PyDMDateTimeEdit, TimeBase
from qtpy import QtCore

logger = logging.getLogger(__name__)


def apply_hotfixes():
    # Edge case: pydm v1.27.1 for Seconds mode (absolute set)
    PyDMDateTimeEdit.send_value = hotfix_send_value


def hotfix_send_value(self):
    """Copy original and force result to int type"""
    val = self.dateTime()
    now = QtCore.QDateTime.currentDateTime()
    if self._block_past_date and val < now:  # type: ignore
        logger.error("Selected date cannot be lower than current date.")
        return

    if self.relative:
        new_value = now.msecsTo(val)
    else:
        new_value = val.toMSecsSinceEpoch()
    if self.timeBase == TimeBase.Seconds:
        new_value /= 1000.0
    # This is the hotfix line
    new_value = int(new_value)
    # This was the hotfix line
    self.send_value_signal[int].emit(new_value)
