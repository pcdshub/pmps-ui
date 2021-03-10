import json
from qtpy import QtCore, QtWidgets
from pydm import Display
from pydm.widgets import PyDMEmbeddedDisplay
from PyQt5.QtGui import QTableWidgetItem


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
            other_label = other_widget.embedded_widget.ui.findChild(
                self._obj_type, str(self._obj_name))

            widget = self.tableWidget().cellWidget(self.row(), column)
            label = widget.embedded_widget.ui.findChild(
                self._obj_type, str(self._obj_name))
            return float(other_label.text()) < float(label.text())
        except Exception:
            return QTableWidgetItem.__lt__(self, other)


class PreemptiveRequests(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super(PreemptiveRequests, self).__init__(parent=parent,
                                                 args=args, macros=macros)
        self.config = macros
        self.setup_ui()

    def setup_ui(self):
        self.setup_requests()
        self.ui.sort_rate_button.clicked.connect(self.sort_rate_items)
        self.ui.sort_transm_button.clicked.connect(
            self.sort_transmission_items)

    def setup_requests(self):
        if not self.config:
            return
        reqs = self.config.get('preemptive_requests')
        if not reqs:
            return
        # reqs_container = self.ui.reqs_content
        reqs_table = self.ui.reqs_table_widget
        # setup table
        reqs_table.setColumnCount(2)
        reqs_table.hideColumn(1)
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
                macros = dict(index=count, P=prefix, ARBITER=arbiter,
                              POOL=pool)
                widget = PyDMEmbeddedDisplay(parent=reqs_table)
                widget.macros = json.dumps(macros)
                channel = f'ca://{prefix}{arbiter}:AP:Entry:{pool}:Live_RBV'
                rule = {
                    "name": "PR_Visibility",
                    "property": "Visible",
                    "channels": [dict(channel=channel, trigger=True)],
                    "expression": "ch[0] == 1"
                }
                widget.rules = json.dumps([rule])
                widget.filename = template
                widget.disconnectWhenHidden = False
                widget.loadWhenShown = False

                # insert items in the table
                row_position = reqs_table.rowCount()
                reqs_table.insertRow(row_position)
                reqs_table.setCellWidget(row_position, 0, widget)

                # insert a fake QTableWidgetItem to customize sorting
                # based on Rate - column position 0
                rate_item = CustomTableWidgetItem(widget_type=QtWidgets.QLabel,
                                                  widget_name='rate_label')
                rate_item.setSizeHint(widget.size())
                reqs_table.setItem(row_position, 0, rate_item)
                # insert a fake QTableWidgetItem to customize sorting
                # based on Transmission - column position 1
                trans_item = CustomTableWidgetItem(
                    widget_type=QtWidgets.QLabel,
                    widget_name='transmission_label')
                trans_item.setSizeHint(widget.size())
                reqs_table.setItem(row_position, 1, trans_item)

                count += 1
        reqs_table.resizeRowsToContents()
        print(f'Added {count} preemptive requests')

    def sort_rate_items(self, value):
        column = 0
        if value is True:
            self.ui.reqs_table_widget.sortItems(column,
                                                QtCore.Qt.DescendingOrder)
        else:
            self.ui.reqs_table_widget.sortItems(column,
                                                QtCore.Qt.AscendingOrder)

    def sort_transmission_items(self, value):
        column = 1
        if value is True:
            self.ui.reqs_table_widget.sortItems(column,
                                                QtCore.Qt.DescendingOrder)
        else:
            self.ui.reqs_table_widget.sortItems(column,
                                                QtCore.Qt.AscendingOrder)

    def ui_filename(self):
        return 'preemptive_requests.ui'
