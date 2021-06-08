import functools
import itertools
import json
import sys
import typing
from dataclasses import dataclass
from string import Template

from pydm import Display
from pydm.widgets import PyDMByteIndicator, PyDMEmbeddedDisplay, PyDMLabel
from pydm.widgets.channel import PyDMChannel
from PyQt5.QtGui import QIcon, QPixmap, QTableWidgetItem
from qtpy import QtCore, QtWidgets


class CustomTableWidgetItem(QTableWidgetItem):
    """
    Custom QTableWidgetItem to allow sorting items in a QTableWidget
    based on the values from a PyDMEmbeddedDisplay widget.

    Parameters
    ----------
    widget_type : QtWidgets
        Type of widget, eg. `QtWidgets.QLabel`
    widget_name : str
        The name of the widget (object name).

    Note
    ----
    For now this class only handles sorting for the QLabel widgets and
    PyDMByteIndicators.
    """
    def __init__(self, store_type, sort_type, default,
                 channel=None, parent=None):
        QTableWidgetItem.__init__(self, parent)
        self.store_type = store_type
        self.sort_type = sort_type
        self.setText(str(default))
        self.channel = channel
        if channel is not None:
            self._channel = PyDMChannel(channel, value_slot=self.update_value)
            self._channel.connect()

    def channels(self):
        """
        Make sure PyDM sees this channel to clean up at the end
        """
        try:
            return [self._channel]
        except AttributeError:
            return []

    def update_value(self, value):
        """
        Use the hidden text field to store the value from the PV
        """
        self.setText(str(self.store_type(value)))

    def __lt__(self, other):
        """
        Use order of defined type, not alphabetical
        """
        return self.sort_type(self.text()) < other.sort_type((other.text()))


def bitmask_count(bitmask_string):
    count = 0
    bitmask = int(bitmask_string)
    if bitmask < 0:
        bitmask += 2**32
    while bitmask > 0:
        if bitmask % 2:
            count += 1
        bitmask = bitmask >> 1
    return count


def str_from_waveform(waveform_array):
    text = ''
    for num in waveform_array:
        if num == 0:
            break
        text += chr(num)
    return text


@dataclass
class SortInfo:
    """All the data we need to set up the sortable table."""
    select_text: str
    widget_name: str
    widget_class: type
    store_type: callable
    sort_type: callable
    default: typing.Any


sort_info_list = [
    SortInfo(
        select_text='Name',
        widget_name='device_label',
        widget_class=PyDMLabel,
        store_type=str_from_waveform,
        sort_type=str,
        default='',
        ),
    SortInfo(
        select_text='ID',
        widget_name='id_label',
        widget_class=PyDMLabel,
        store_type=int,
        sort_type=int,
        default=0,
        ),
    SortInfo(
        select_text='Rate',
        widget_name='rate_label',
        widget_class=PyDMLabel,
        store_type=int,
        sort_type=int,
        default=0,
        ),
    SortInfo(
        select_text='Transmission',
        widget_name='transmission_label',
        widget_class=PyDMLabel,
        store_type=float,
        sort_type=float,
        default=0.0,
        ),
    SortInfo(
        select_text='Energy',
        widget_name='energy_bytes',
        widget_class=PyDMByteIndicator,
        store_type=bitmask_count,
        sort_type=int,
        default=0,
        ),
    SortInfo(
        select_text='Cohort',
        widget_name='cohort_label',
        widget_class=PyDMLabel,
        store_type=int,
        sort_type=int,
        default=0,
        ),
    SortInfo(
        select_text='Active',
        widget_name='live_byte',
        widget_class=PyDMByteIndicator,
        store_type=int,
        sort_type=int,
        default=0,
        ),
    ]


class PreemptiveRequests(Display):
    _bits = {'bit15': False, 'bit14': False, 'bit13': False, 'bit12': False,
             'bit11': False, 'bit10': False, 'bit9': False, 'bit8': False,
             'bit7': False, 'bit6': False, 'bit5': False, 'bit4': False,
             'bit3': False, 'bit2': False, 'bit1': False, 'bit0': False}

    def __init__(self, parent=None, args=None, macros=None):
        super(PreemptiveRequests, self).__init__(parent=parent,
                                                 args=args, macros=macros)
        self.config = macros
        self.setup_ui()

    def setup_ui(self):
        self.setup_requests()
        self.setup_sorts()

    def setup_requests(self):
        if not self.config:
            return
        reqs = self.config.get('preemptive_requests')
        if not reqs:
            return
        reqs_table = self.ui.reqs_table_widget
        # setup table
        ncols = len(sort_info_list) + 1
        reqs_table.setColumnCount(ncols)
        # hide extra sort columns: these just hold values for easy sorting
        for col in range(1, ncols):
            reqs_table.hideColumn(col)

        if reqs_table is None:
            return
        count = 0
        for req in reqs:
            prefix = req.get('prefix')
            arbiter = req.get('arbiter_instance')
            pool_start = req.get('assertion_pool_start')
            pool_end = req.get('assertion_pool_end')

            pool_zfill = len(str(pool_end)) + 1

            template = 'templates/preemptive_requests_entry.ui'
            for pool_id in range(pool_start, pool_end+1):
                pool = str(pool_id).zfill(pool_zfill)
                macros = dict(index=count, P=prefix,
                              ARBITER=arbiter, POOL=pool)
                widget = PyDMEmbeddedDisplay(parent=reqs_table)
                widget.prefixes = macros
                widget.macros = json.dumps(macros)
                widget.filename = template
                widget.loadWhenShown = False
                widget.disconnectWhenHidden = False

                # insert the widget you see into the table
                row_position = reqs_table.rowCount()
                reqs_table.insertRow(row_position)
                reqs_table.setCellWidget(row_position, 0, widget)

                # insert invisible customized QTableWidgetItems for sorting
                for num, info in enumerate(sort_info_list):
                    inner_widget = widget.findChild(
                        info.widget_class,
                        info.widget_name,
                        )
                    item = CustomTableWidgetItem(
                        store_type=info.store_type,
                        sort_type=info.sort_type,
                        default=info.default,
                        channel=inner_widget.channel,
                        )
                    item.setSizeHint(widget.size())
                    reqs_table.setItem(row_position, num + 1, item)

                count += 1
        reqs_table.resizeRowsToContents()
        self.update_filters()
        print(f'Added {count} preemptive requests')

    def setup_sorts(self):
        self.ui.sort_choices.addItem('Unsorted')
        for info in sort_info_list:
            self.ui.sort_choices.addItem(info.select_text)
        self.ui.sort_choices.currentIndexChanged.connect(self.gui_table_sort)
        self.ui.order_choice.currentIndexChanged.connect(self.gui_table_sort)
        self.ui.sort_button.clicked.connect(self.gui_table_sort)
        self.ui.reqs_table_widget.cellChanged.connect(
            self.handle_item_changed,
            )

    def sort_table(self, column, ascending):
        if ascending:
            order = QtCore.Qt.AscendingOrder
        else:
            order = QtCore.Qt.DescendingOrder
        self.ui.reqs_table_widget.sortItems(column, order)

    def handle_item_changed(self, *args, **kwargs):
        if self.ui.auto_update.isChecked():
            self.gui_table_sort()

    def gui_table_sort(self, *args, **kwargs):
        column = self.ui.sort_choices.currentIndex()
        ascending = self.ui.order_choice.currentIndex() == 0
        self.sort_table(column, ascending)

    def update_filters(self):
        return
        # TODO update based on other refactor
        default_options = [
            {'name': 'live',
             'channel': 'ca://${P}${ARBITER}:AP:Entry:${POOL}:Live_RBV',
             'condition': 1
             }]
        options = [
            {'name': 'bitmask',
             'channel': 'ca://${P}${ARBITER}:AP:Entry:${POOL}:PhotonEnergyRanges_RBV'
             }]
        filters = []
        for opt in default_options:
            filters.append(opt)
        for opt in options:
            gb = self.findChild(QtWidgets.QGroupBox, f"ff_filter_gb_{opt['name']}")
            if gb.isChecked():
                opt['condition'] = self.calc_bitmask()
                filters.append(opt)
        self.filters_changed.emit(filters)

    def ui_filename(self):
        return 'preemptive_requests.ui'
