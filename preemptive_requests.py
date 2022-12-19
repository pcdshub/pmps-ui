import functools
import json
import logging
import typing
from dataclasses import dataclass
from string import Template

import prettytable
from pydm import Display
from pydm.widgets import PyDMByteIndicator, PyDMEmbeddedDisplay, PyDMLabel
from pydm.widgets.channel import PyDMChannel
from qtpy import QtCore, QtWidgets

from data_bounds import get_valid_rate

logger = logging.getLogger(__name__)


class PreemptiveRequests(Display):
    """
    The Display that handles the Preemptive Requests tab.

    This display features a sortable and filterable QTableWidget.

    Internally, the table is structured as:
    - Column 0 is the only visible column and holds the templated widgets
    - Column 1 stores the original table insertion order and is not visible
    - Columns 2 and up correspond with the item_info_list and are not visible
    - Each row is loaded using information from the config file

    Unlike the fast fault tab, which populates a QVBoxLayout with a bunch of
    instances of VisibilityEmbeddedWidget, this display populates a
    QTableWidget with a bunch of instances of PyDMEmbeddedDisplay. This is done
    for a few reasons:
    - QVBoxLayout is not natively sortable without removing and replacing all
      the widgets you want to include, which is ultimately messy and
      potentially slow or error-prone depending on the implementation.
      QTableWidget is natively sortable on any of its columns.
    - Visibility of an item in a QTableWidget is not controlled by the normal
      visibility properties, so the visibility rules cannot be used the same
      way as in the fast faults tab. When you try this, you just see every row
      of the table all the time. Therefore, the previous approch is not useful
      here, and instead we link the channels up with the QTableWidget.hideRow
      and QTableWidget.showRow methods.
    """
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.config = macros
        self._channels = []
        self.mode = None
        self.mode_index = None
        self.mode_enum = None
        self.setup_ui()

    def setup_ui(self):
        """Do all steps to prepare the inner workings of the display."""
        self.setup_requests()
        self.setup_sorts_and_filters()
        self.setup_mode()

    def setup_requests(self):
        """Populate the table from the config file and the item_info_list."""
        if not self.config:
            return
        reqs = self.config.get('preemptive_requests')
        if not reqs:
            return
        reqs_table = self.ui.reqs_table_widget
        # setup table
        ncols = len(item_info_list) + 2
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

                # special setup for the rate label
                # this is a plain QLabel so we can display true rate
                # true rate is locked to one of a few fixed values
                rate_label = widget.findChild(
                    QtWidgets.QLabel,
                    'rate_label',
                )
                rate_label.channel = Template(
                    'ca://${P}${ARBITER}:AP:Entry:${POOL}:Rate_RBV'
                ).safe_substitute(**macros)
                rate_channel = PyDMChannel(
                    rate_label.channel,
                    value_slot=functools.partial(
                        self.update_valid_rate,
                        label=rate_label,
                    ),
                )
                rate_channel.connect()
                self._channels.append(rate_channel)

                # Extra channel for the beamclass
                # This lets us sub in an appropriate tooltip stub based on
                # the beamclass value as it updates
                beamclass_label = widget.embedded_widget.ui.beamclass_label
                bc_channel = PyDMChannel(
                    beamclass_label.channel,
                    value_slot=functools.partial(
                        self.update_beamclass_tooltip,
                        label=beamclass_label,
                    ),
                )
                bc_channel.connect()
                self._channels.append(bc_channel)

                # insert the widget you see into the table
                row_position = reqs_table.rowCount()
                reqs_table.insertRow(row_position)
                reqs_table.setCellWidget(row_position, 0, widget)

                # insert a cell to preserve the original sort order
                item = PMPSTableWidgetItem(
                    store_type=int,
                    data_type=int,
                    default=count,
                    )
                item.setSizeHint(widget.size())
                reqs_table.setItem(row_position, 1, item)

                # insert invisible customized QTableWidgetItems for sorting
                for num, info in enumerate(item_info_list):
                    inner_widget = widget.findChild(
                        info.widget_class,
                        info.widget_name,
                        )
                    item = PMPSTableWidgetItem(
                        store_type=info.store_type,
                        data_type=info.data_type,
                        default=info.default,
                        channel=inner_widget.channel,
                        )
                    item.setSizeHint(widget.size())
                    reqs_table.setItem(row_position, num + 2, item)
                    self._channels.append(item.pydm_channel)

                count += 1
        reqs_table.resizeRowsToContents()
        self.row_count = count
        print(f'Added {count} preemptive requests')

    def setup_sorts_and_filters(self):
        """Initialize the sorting and filtering using the item_info_list."""
        self.ui.sort_choices.addItem('Unsorted')
        for info in item_info_list:
            self.ui.sort_choices.addItem(info.select_text)
        self.ui.sort_choices.currentIndexChanged.connect(self.gui_table_sort)
        self.ui.order_choice.currentIndexChanged.connect(self.gui_table_sort)
        self.ui.sort_button.clicked.connect(self.gui_table_sort)
        self.ui.auto_update.clicked.connect(self.auto_sort_clicked)
        self.ui.full_beam.stateChanged.connect(self.update_all_filters)
        self.ui.inactive.stateChanged.connect(self.update_all_filters)
        self.ui.disconnected.stateChanged.connect(self.update_all_filters)
        self.ui.reqs_table_widget.cellChanged.connect(
            self.handle_item_changed,
            )
        self.update_all_filters()

    def new_mode(self, value):
        """
        Update the display's "mode" to either NC or SC.

        This will hide or show the rate and beamclass columns as appropriate
        and re-interpret the definition of "full beam".
        """
        if isinstance(value, int):
            self.mode_index = value
            if self.mode_enum is None:
                return
            try:
                self.mode = self.mode_enum[self.mode_index]
            except IndexError:
                logger.error(
                    'Bad mode enum strs %s for index %d',
                    self.mode_enum,
                    self.mode_index,
                )
                self.mode = None
        elif isinstance(value, str):
            self.mode = value
        else:
            self.mode = None
        header = self.ui.table_header.embedded_widget.ui
        # Show both if value is None
        header.rate_header.setVisible(self.mode != 'SC')
        header.beamclass_header.setVisible(self.mode != 'NC')
        # Full beam filter depends on the mode
        self.update_all_filters()

    def new_mode_enum_strs(self, value):
        """
        Update the enum strings used to interpret the mode.

        Re-runs new_mode if we have an index already.
        """
        self.mode_enum = value
        if self.mode_index is not None:
            self.new_mode(self.mode_index)

    def setup_mode(self):
        """Create a channel to react to mode changes"""
        mode_pvname = self.config.get('accelerator_mode_pv')
        if not mode_pvname:
            # We'll run in ambiguous mode
            logger.warning('No accelerator_mode_pv in config file.')
            return
        self._mode_channel = PyDMChannel(
            f'ca://{mode_pvname}',
            value_slot=self.new_mode,
            enum_strings_slot=self.new_mode_enum_strs,
        )
        self._mode_channel.connect()
        self._channels.append(self._mode_channel)

    def sort_table(self, column, ascending):
        """
        Sort the table based on the values from one column of the table.

        Parameters
        ----------
        column : int
            The column of the table to sort on.
        ascending : bool
            If true, sort in ascending order, otherwise sort in descending
            order.
        """
        if ascending:
            order = QtCore.Qt.AscendingOrder
        else:
            order = QtCore.Qt.DescendingOrder
        self.ui.reqs_table_widget.sortItems(column, order)

    def handle_item_changed(self, row, column):
        """
        Slot for all updates that trigger when a cell in the table updates.

        This updates the filtering of the updated row, showing or
        hiding it as appropriate, and then re-evaluates the table sort
        if the auto_update checkbox is checked.

        Parameters
        ----------
        row : int
            The row of the cell in the table that recieved an update.
        column : int
            The column of the cell in the table that recieved an update.
            This is currently unused, but is passed by the update signal.
        """
        self.update_filter(row)
        if self.ui.auto_update.isChecked():
            self.gui_table_sort()

    def gui_table_sort(self, *args, **kwargs):
        """
        Slot for all signals that want to trigger a full table sort.

        The sort is done based on the current states of the sort_choices and
        order_choice comboboxes.

        Arguments are ignored and are only included so that any signal can
        call the slot.
        """
        column = self.ui.sort_choices.currentIndex() + 1
        ascending = self.ui.order_choice.currentIndex() == 0
        self.sort_table(column, ascending)

    def auto_sort_clicked(self, checked):
        """
        Slot to trigger a new sort when the auto_sort checkbox is checked.

        Without this method, we can have an unsorted table with the checkbox
        checked because it only re-sorts on update.
        """
        if checked:
            self.gui_table_sort()

    def update_filter(self, row):
        """
        Hide or show a specific row of the table as appropriate.

        The row's values will be checked and compared against the selected
        filters in the ui.

        Currently supports the following filters, which are all active by
        default:
        - Hide if requesting full beam
        - Hide if no activate arbitration
        - Hide if PV disconnected

        In addition, the rate or beamclass widget will be hidden based on the
        mode if the mode is unambiguous.

        Parameters
        ----------
        row : int
            The row of the table to show or hide.
        """
        # Treat the entire row as one entity
        table = self.ui.reqs_table_widget
        values = {}
        for info, column in zip(item_info_list, range(2, table.columnCount())):
            item = table.item(row, column)
            values[info.name] = item.get_value()

        full_rate = values['rate'] >= 120
        full_bc = values['beamclass'] >= 13
        if self.mode == 'NC':
            rate_cpt = full_rate
        elif self.mode == 'SC':
            rate_cpt = full_bc
        else:
            # Ambiguous mode- use both sources
            rate_cpt = full_rate and full_bc

        # Make sure we show/hide the column elements based on mode
        # Ambiguous mode means we show both
        row_widget = table.cellWidget(row, 0).embedded_widget.ui
        row_widget.rate_label.setVisible(self.mode != 'SC')
        row_widget.beamclass_label.setVisible(self.mode != 'NC')

        full_beam = all((
            rate_cpt,
            values['trans'] >= 1,
            values['energy'] >= 32,
            ))
        active = bool(values['active'])
        connected = item.connected

        hide_full_beam = self.ui.full_beam.isChecked()
        hide_inactive = self.ui.inactive.isChecked()
        hide_disconnected = self.ui.disconnected.isChecked()

        hide = any((
            hide_full_beam and full_beam,
            hide_inactive and not active,
            hide_disconnected and not connected,
            ))

        if hide:
            table.hideRow(row)
        else:
            table.showRow(row)

    def update_all_filters(self, *args, **kwargs):
        """Call update_filter on every row of the table."""
        for row in range(self.row_count):
            self.update_filter(row)

    def update_valid_rate(self, value, label):
        valid_rate = get_valid_rate(value)
        label.setText(f'{valid_rate} Hz')

    def update_beamclass_tooltip(self, value, label):
        label.PyDMToolTip = get_tooltip_for_bc('<pre>' + value + '</pre>')

    def ui_filename(self):
        return 'preemptive_requests.ui'

    def channels(self):
        """
        Make sure PyDM can find the channels we set up for cleanup.

        Put this here instead of on the PMPSTableWidgetItem because
        QTableWidgetItem instances are not instances of QWidget, and
        therefore are not checked by PyDM for channels.
        """
        return self._channels


class PMPSTableWidgetItem(QtWidgets.QTableWidgetItem):
    """
    QTableWidgetItem with extra utilities for the PMPS UI

    Adds the following features:
    - Fill value and connection state from PyDMChannel
    - Configurable sorting
    - Process inputs before storing in the table
    - Able to sort as a non-str type

    Parameters
    ----------
    store_type : callable
        Function or type to call on the value from the PyDMChannel before
        storing in the table.
    data_type : callable
        Function or type to call on the str stored in the table before
        comparing with other PMPSTableWidgetItem instances for sorting.
    default : Any
        A starting value for the widget item.
    channel : str, optional
        PyDM channel address for value and connection updates.
    """
    def __init__(self, store_type, data_type, default,
                 channel=None, parent=None):
        super().__init__(parent)
        self.store_type = store_type
        self.data_type = data_type
        self.setText(str(default))
        self.channel = channel
        self.connected = False
        if channel is not None:
            self.pydm_channel = PyDMChannel(
                channel,
                value_slot=self.update_value,
                connection_slot=self.update_connection,
                )
            self.pydm_channel.connect()

    def update_value(self, value):
        """
        Use the hidden text field to store the value from the PV.

        This is pre-processed by the "store_type" attribute because the
        value can only be saved as a string via setText.

        We use the setText instead of an attribute to help with debugging,
        this means you can see what the table is being sorted on
        if you unhide the columns.
        """
        self.setText(str(self.store_type(value)))

    def update_connection(self, connected):
        """
        When our PV connects or disconnects, store the state as an attribute.
        """
        self.connected = connected

    def get_value(self):
        """The value in canonical python type (not string)."""
        return self.data_type(self.text())

    def __lt__(self, other):
        """Use order of defined type, not alphabetical."""
        return self.get_value() < other.get_value()


def bitmask_count(bitmask):
    """Count the number of high bits in a bitmask."""
    bitmask = int(bitmask)
    if bitmask < 0:
        bitmask += 2**32
    return str(bin(bitmask)).count('1')


def str_from_waveform(waveform_array):
    """Convert an EPICS char waveform to a str."""
    text = ''
    for num in waveform_array:
        if num == 0:
            break
        text += chr(num)
    return text


@dataclass(frozen=True)
class ItemInfo:
    """All the data we need to set up the sorts/filters"""
    name: str
    select_text: str
    widget_name: str
    widget_class: type
    store_type: callable
    data_type: callable
    default: typing.Any


# Each entry corresponds to one UI element in the template
# In this way we can easily add/remove/configure the sorting behavior
item_info_list = [
    ItemInfo(
        name='name',
        select_text='Device',
        widget_name='device_label',
        widget_class=PyDMLabel,
        store_type=str_from_waveform,
        data_type=str,
        default='',
    ),
    ItemInfo(
        name='id',
        select_text='Assertion ID',
        widget_name='id_label',
        widget_class=PyDMLabel,
        store_type=int,
        data_type=int,
        default=0,
    ),
    ItemInfo(
        name='rate',
        select_text='Rate [NC]',
        widget_name='rate_label',
        widget_class=QtWidgets.QLabel,
        store_type=int,
        data_type=int,
        default=0,
    ),
    ItemInfo(
        name='beamclass',
        select_text='Beam Class [SC]',
        widget_name='beamclass_label',
        widget_class=PyDMLabel,
        store_type=int,
        data_type=int,
        default=0,
    ),
    ItemInfo(
        name='trans',
        select_text='Transmission',
        widget_name='transmission_label',
        widget_class=PyDMLabel,
        store_type=float,
        data_type=float,
        default=0.0,
    ),
    ItemInfo(
        name='energy',
        select_text='Photon Energy Ranges',
        widget_name='energy_bytes',
        widget_class=PyDMByteIndicator,
        store_type=bitmask_count,
        data_type=int,
        default=0,
    ),
    ItemInfo(
        name='cohort',
        select_text='Cohort Number',
        widget_name='cohort_label',
        widget_class=PyDMLabel,
        store_type=int,
        data_type=int,
        default=0,
    ),
    ItemInfo(
        name='active',
        select_text='Active Arbitration',
        widget_name='live_byte',
        widget_class=PyDMByteIndicator,
        store_type=int,
        data_type=int,
        default=0,
    ),
]

# Copied from https://confluence.slac.stanford.edu/pages/viewpage.action?pageId=341246543 and tweaked
bc_header = """
Index	Display Name	∆T (s)	dt (s)	Q (pC)	Rate max (Hz)	Current (nA)	Power @ 4 GeV (W)	Int. Energy @ 4 GeV (J)	Notes
""".strip().split('\t')
bc_table = """
0	Beam Off	0.5	-	0	0	0	0	0	Beam off, Kickers off
1	Kicker STBY	0.5	-	0	0	0	0	0	Beam off, Kickers standby
2	BC1Hz	1	1	350	1	0.35	1.4	1.4	350 pC x 1 Hz
3	BC10Hz	1	0.1	3500	10	3.5	14	14	350 pC X 10 Hz
4	Diagnostic	0.5	-	5000	-	10	40	20	50 pC x 200 Hz
5	BC120Hz	0.2	0.0083	6000	120	30	120	24	250 pC x 120 Hz
6	Tuning	0.2	-	7000	-	35	140	28	100 pC X 350 Hz
7	1% MAP	0.01	-	3000	-	300	1200	12	100 pC X 3 kHz
8	5% MAP	0.003	-	4500	-	1500	6000	18	100 pC x 15 kHz
9	10% MAP	0.001	-	3000	-	3000	12000	12	100 pC X 30 kHz
10	25% MAP	4e-4	-	3000	-	7500	30000	12	100 pC x 75 kHz
11	50% MAP	2e-1	-	3000	-	15000	60000	12	100 pC x 150 kHz
12	100% MAP	2e-4	-	6000	-	30000	120000	24	100 pC x 300 kHz
13	Unlimited	-	-	-	-	-	-	-	-
14	Spare	-	-	-	-	-	-	-	-
15	Spare	-	-	-	-	-	-	-	-
""".strip().split('\n')
for index, row in enumerate(bc_table):
    bc_table[index] = row.split('\t')


def get_full_bc_table() -> str:
    """
    Show the full table
    """
    table = prettytable.PrettyTable()
    table.field_names = bc_header
    for row in bc_table:
        table.add_row(row)
    return str(table)


def get_tooltip_for_bc(beamclass: int) -> str:
    """
    Create a mini 2-row table suitable for a beam class tooltip.
    """
    table = prettytable.PrettyTable()
    table.field_names = bc_header
    table.add_row(bc_table[beamclass])
    return str(table)
