import json
import functools
import itertools
import sys
from string import Template

from fast_faults import VisibilityEmbedded
from pydm import Display
from pydm.widgets import PyDMByteIndicator
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
    def __init__(self, widget_type, widget_name, parent=None):
        QTableWidgetItem.__init__(self, parent)
        self._obj_name = widget_name
        self._obj_type = widget_type

    def __lt__(self, other):
        """
        Override the __lt__ to handle data sorting for rate.
        """
        # column 0 is where the embedded display widget data is at
        column = 0
        try:
            other_widget = other.tableWidget().cellWidget(other.row(), column)
            widget = self.tableWidget().cellWidget(self.row(), column)

            if isinstance(self._obj_type, QtWidgets.QLabel):
                other_value, value = self.sort_label(other_widget, widget)
            elif isinstance(self._obj_type, PyDMByteIndicator):
                other_value, value = self.sort_byte_indicator(other_widget,
                                                              widget)
            else:
                return QTableWidgetItem.__lt__(self, other)
            return float(other_value) < float(value)
        except Exception:
            return QTableWidgetItem.__lt__(self, other)

    def sort_label(self, other_label, label):
        """
        Get the value of the current label and previous label.

        Returns
        -------
        values : tuple
            (other_value, value)
        """
        other_label = other_label.embedded_widget.ui.findChild(
            self._obj_type, str(self._obj_name))
        label = label.embedded_widget.ui.findChild(
            self._obj_type, str(self._obj_name))
        # # values in the labels will have their units displayed,
        # # so we want to eliminate those
        other_value = ''.join(filter(str.isdigit, other_label.text()))
        value = ''.join(filter(str.isdigit, label.text()))
        # if we cannot get the values because PVs are disconnected
        # or we don't have numerical values for some reason, pretend
        # they are maxsize so they go at the end of table if sorting
        # in ascending order
        if other_value == '':
            other_value = sys.maxsize
        if value == '':
            value = sys.maxsize
        return other_value, value

    def sort_byte_indicator(self, other_byte_indicator, byte_indicator):
        """
        Get the value of the current PyDMbyteIndicator and previous one.

        TODO: probably not a very safe idea here to do so:
        Get the number of off bits based on the color of the bit, specifically
        based on the `ON` color. If PVs are disconnected, the bits are
        considered `0`. We could technically differentiate between the
        disconnected and 0 bits by checking one more color if we need to.

        Returns
        -------
        values : tuple
            (other_value, value)
        """
        # color when the bits are on
        on_color = (21, 165, 62, 255)
        other_byte_indicator = other_byte_indicator.embedded_widget.ui.findChild(
            self._obj_type, str(self._obj_name))

        byte_indicator = byte_indicator.embedded_widget.ui.findChild(
            self._obj_type, str(self._obj_name))

        def get_value(indicators):
            temp = []
            for i in indicators:
                bit_color = i._brush.color().getRgb()
                color = bit_color == on_color
                temp.append(color)
            return 16 - sum(temp)
        other_value = get_value(other_byte_indicator._indicators)
        value = get_value(byte_indicator._indicators)
        return other_value, value


class PreemptiveRequests(Display):
    filters_changed = QtCore.Signal(list)
    _toggle_rate_pb = itertools.cycle([True, False]).__next__
    _toggle_transmission_pb = itertools.cycle([True, False]).__next__
    _toggle_energy_range_pb = itertools.cycle([True, False]).__next__

    # elements for the sorting buttons
    sort_desc_pix = QPixmap("templates/sort_desc.png")
    sort_asc_pix = QPixmap("templates/sort_asc.png")
    sort_desc_icon = QIcon()
    sort_asc_icon = QIcon()

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
        self.ui.ff_filter_gb_bitmask.toggled.connect(self.enable_bits)
        self.ui.btn_apply_filters.clicked.connect(self.update_filters)
        self.setup_requests()
        self.setup_sort_buttons()

    def setup_sort_buttons(self):
        self.ui.sort_rate_button.clicked.connect(
            functools.partial(self.sort_rate_items, self.ui.sort_rate_button))
        self.ui.sort_transm_button.clicked.connect(
            functools.partial(self.sort_transmission_items,
                              self.ui.sort_transm_button))
        self.ui.sort_energy_range_button.clicked.connect(
            functools.partial(self.sort_energy_range_items,
                              self.ui.sort_energy_range_button)
        )

        self.sort_desc_icon.addPixmap(self.sort_desc_pix, QIcon.Normal, QIcon.Off)
        self.sort_asc_icon.addPixmap(self.sort_asc_pix, QIcon.Normal, QIcon.Off)

        self.ui.sort_rate_button.setIcon(self.sort_asc_icon)
        self.ui.sort_rate_button.setIconSize(self.ui.sort_rate_button.size())

        self.ui.sort_transm_button.setIcon(self.sort_asc_icon)
        self.ui.sort_transm_button.setIconSize(self.ui.sort_transm_button.size())

        self.ui.sort_energy_range_button.setIcon(self.sort_asc_icon)
        self.ui.sort_energy_range_button.setIconSize(
            self.ui.sort_energy_range_button.size())

    def change_button_state_icon(self, state, btn):
        if state is True:
            btn.setIcon(self.sort_desc_icon)
        else:
            btn.setIcon(self.sort_asc_icon)

    def setup_requests(self):
        if not self.config:
            return
        reqs = self.config.get('preemptive_requests')
        if not reqs:
            return
        reqs_table = self.ui.reqs_table_widget
        # setup table
        reqs_table.setColumnCount(3)
        # we only need a second column to be able to sort based on another
        # element other than the one in the first column - since the widgets
        # are placed in the first column we should hide the second one.
        reqs_table.hideColumn(1)
        reqs_table.hideColumn(2)
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
                ch = Template('ca://${P}${ARBITER}:AP:Entry:${POOL}:Live_RBV').safe_substitute(**macros)
                widget = VisibilityEmbedded(parent=reqs_table, channel=ch)
                widget.prefixes = macros
                self.filters_changed[list].connect(widget.update_filter)

                widget.macros = json.dumps(macros)

                widget.filename = template
                widget.loadWhenShown = False
                widget.disconnectWhenHidden = False

                # insert items in the table
                row_position = reqs_table.rowCount()
                reqs_table.insertRow(row_position)
                reqs_table.setCellWidget(row_position, 0, widget)

                # insert a fake customized QTableWidgetItem to allow sorting
                # based on Rate - column position 0
                rate_item = CustomTableWidgetItem(widget_type=QtWidgets.QLabel,
                                                  widget_name='rate_label')
                rate_item.setSizeHint(widget.size())
                reqs_table.setItem(row_position, 0, rate_item)
                # insert a fake customized QTableWidgetItem to allow sorting
                # based on Transmission - column position 1
                trans_item = CustomTableWidgetItem(
                    widget_type=QtWidgets.QLabel,
                    widget_name='transmission_label')
                trans_item.setSizeHint(widget.size())
                reqs_table.setItem(row_position, 1, trans_item)

                # insert a fake customized QTableWidgetItem to allow sorting
                # based on Energy Range Transmission
                energy_range = CustomTableWidgetItem(
                    widget_type=PyDMByteIndicator,
                    widget_name='energy_range_indicator')
                energy_range.setSizeHint(widget.size())
                reqs_table.setItem(row_position, 2, energy_range)

                count += 1
        reqs_table.resizeRowsToContents()
        self.update_filters()
        print(f'Added {count} preemptive requests')

    def sort_rate_items(self, btn):
        """
        Sort the items in the table based on the Rate values from the embedded
        widget. sortItems will call CustomTableWidgetItem's __ld__ method where
        the values from the rate label (CustomTabWidgetItem column 0) will be
        compared and sorted.
        """
        column = 0
        state = self._toggle_rate_pb()
        if state is True:
            self.ui.reqs_table_widget.sortItems(column,
                                                QtCore.Qt.DescendingOrder)
        else:
            self.ui.reqs_table_widget.sortItems(column,
                                                QtCore.Qt.AscendingOrder)
        self.change_button_state_icon(state, btn)

    def sort_transmission_items(self, btn):
        """
        Sort the items in the table based on the Transmission values from the
        embedded widget. sortItems will call CustomTableWidgetItem's __ld__
        method, where the values from the transmission label
        (CustomTabWidgetItem column 1) will be compared and sorted.
        """
        column = 1
        state = self._toggle_transmission_pb()
        if state is True:
            self.ui.reqs_table_widget.sortItems(column,
                                                QtCore.Qt.DescendingOrder)
        else:
            self.ui.reqs_table_widget.sortItems(column,
                                                QtCore.Qt.AscendingOrder)
        self.change_button_state_icon(state, btn)

    def sort_energy_range_items(self, btn):
        """
          Sort the items in the table based on the Transmission values from the
          embedded widget. sortItems will call CustomTableWidgetItem's __ld__
          method, where the values from the transmission label
          (CustomTabWidgetItem column 1) will be compared and sorted.
          """
        column = 2
        state = self._toggle_energy_range_pb()
        if state is True:
            self.ui.reqs_table_widget.sortItems(column,
                                                QtCore.Qt.DescendingOrder)
        else:
            self.ui.reqs_table_widget.sortItems(column,
                                                QtCore.Qt.AscendingOrder)
        self.change_button_state_icon(state, btn)

    def enable_bits(self, toggle):
        """
        Enable the bits when the combo box is checked.
        """
        if toggle is True:
            for key, item in self._bits.items():
                cb = self.findChild(QtWidgets.QCheckBox, f"filter_cb_{key}")
                cb.setEnabled(True)
        else:
            for key, item in self._bits.items():
                cb = self.findChild(QtWidgets.QCheckBox, f"filter_cb_{key}")
                cb.setEnabled(False)

    def calc_bitmask(self):
        """
        Calculate a decimal number based on the checked/unchecked bits
        from the filter (Photon Energy Range).
        These bits are represented by check boxes where checked = True and
        unchecked = False.
        """
        for key, item in self._bits.items():
            cb = self.findChild(QtWidgets.QCheckBox, f"filter_cb_{key}")
            self._bits[key] = cb.isChecked()

        decimal_value = functools.reduce(
            (lambda x, y: (x << 1) | y),
            map(int, [item for key, item in self._bits.items()])
        )
        return decimal_value

    def update_filters(self):
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
