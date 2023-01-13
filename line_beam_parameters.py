import functools

from pydm import Display
from pydm.exception import raise_to_operator
from pydm.widgets import PyDMLabel
from pydm.widgets.channel import PyDMChannel
from qtpy import QtCore, QtWidgets

from beamclass_table import bc_table, get_desc_for_bc, install_bc_setText
from data_bounds import VALID_RATES, get_valid_rate
from tooltips import (get_ev_range_tooltip, get_tooltip_for_bc,
                      get_tooltip_for_bc_bitmask)
from utils import morph_into_vertical


class LineBeamParametersControl(Display):
    """
    Class to handle display for the Line Beam Parameters Control tab.
    """
    # object names for all energy range bits checkboxes, set them all
    # to unchecked to start with
    _bits = {f'bit{num}': False for num in reversed(range(32))}
    # same but for the beamclass bits
    _bc_bits = {f'bit{num}_2': False for num in reversed(range(15))}

    # signal to emit when energy range is changed
    energy_range_signal = QtCore.Signal(int)
    # signal to emit when bc range is changed
    bc_range_signal = QtCore.Signal(int)

    energy_channel = None
    bc_range_channel = None

    # Monitor the rate readback for use in the zero rate button
    rate_channel = None

    # Signal to set a new rate from the combobox or from zero rate button
    update_rate_signal = QtCore.Signal(int)
    # Signal to set a new beamclass from the combobox or from zero rate button
    update_beamclass_signal = QtCore.Signal(int)

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.config = macros
        self._channels = []
        self.setup_ui()

    def channels(self):
        "Make sure PyDM can find the channels we set up for cleanup."
        return self._channels

    def ui_filename(self):
        return 'line_beam_parameters.ui'

    def setup_ui(self):
        self.setup_bits_connections()
        self.setup_bit_indicators()
        self.setup_energy_range_channel()
        self.setup_rate_channel()
        self.setup_bc_bits_connections()
        self.setup_bc_range_channel()
        self.setup_ev_rbv_channel()
        self.setup_bc_rbv_channel()
        self.setup_zero_rate()
        self.setup_rate_combo()
        install_bc_setText(self.ui.max_bc_label)
        self.setup_beamclass_combo()
        self.rate_channel.connect()

    def setup_bits_connections(self):
        """
        Connect all the check boxes bits with the calc_energy_range method to
        calculate the range upon changing a bit state.
        """
        for key in self._bits:
            cb = self.findChild(QtWidgets.QCheckBox, key)
            cb.clicked.connect(functools.partial(
                self.calc_energy_range, key))

    def setup_bit_indicators(self):
        """
        Borrowed function from fast_faults, to help morph the labels vertically
        """
        for key in self._bits:
            label = self.findChild(PyDMLabel, f"label_{key}")
            if label is not None:
                morph_into_vertical(label)

    def calc_energy_range(self, key, checked):
        """
        Catch when a check box is checked/unchecked and calculate
        the current bitmask.

        Parameters
        ----------
        key : str
            The check box object name.
        checked: bool
            True if the checkbox is checked
        """
        self._bits[key] = checked
        decimal_value = functools.reduce(
            (lambda x, y: (x << 1) | y),
            map(int, [value for value in self._bits.values()])
        )

        # emit the decimal value to the PhotonEnergyRange
        self.energy_range_signal.emit(decimal_value)

    def setup_energy_range_channel(self):
        prefix = self.config.get('line_arbiter_prefix')
        ch = f'ca://{prefix}BeamParamCntl:ReqBP:PhotonEnergyRanges'

        self.energy_channel = PyDMChannel(
            ch,
            value_slot=self.energy_range_changed,
            value_signal=self.energy_range_signal
        )
        self.energy_channel.connect()
        self._channels.append(self.energy_channel)

    def energy_range_changed(self, energy_range):
        """
        This slot is supposed to handled the initial value of the
        Photon Energy Range coming in as soon as we connect, as well
        as whenever this value is changed outside this application.

        Parameters
        ----------
        energy_range : int
            The decimal value of the photon energy range.
        """
        if energy_range is None:
            return

        # EPICS is signed but we want the unsigned 32-bit int
        if energy_range < 0:
            energy_range = 2**32 + energy_range

        binary_range = list(bin(energy_range).replace("0b", ""))
        binary_list = list(map(int, binary_range))
        while len(binary_list) < 32:
            binary_list = [0] + binary_list
        for key, status in zip(self._bits.keys(), binary_list):
            self._bits[key] = bool(status)
            cb = self.findChild(QtWidgets.QCheckBox, key)
            cb.setChecked(bool(status))

    def setup_rate_channel(self):
        prefix = self.config.get('line_arbiter_prefix')
        self.rate_channel = PyDMChannel(
            f'ca://{prefix}BeamParamCntl:ReqBP:Rate',
            value_slot=self.watch_rate_update,
            value_signal=self.update_rate_signal,
        )
        self._channels.append(self.rate_channel)

    def setup_bc_bits_connections(self):
        """
        Set up the beamclass selector updates

        Connect all the check boxes bits with the calc_energy_range method to
        calculate the range upon changing a bit state.

        Set a tooltip on each checkbox that makes it clear what that bit controls.
        """
        self.update_beamclass_signal.connect(self.update_beamclass_bitmask_from_max)
        self.bc_range_signal.connect(self.update_beamclass_max_from_bitmask)
        for key in self._bc_bits:
            cb = self.findChild(QtWidgets.QCheckBox, key)
            cb.clicked.connect(functools.partial(
                self.calc_bc_range, key))
            cb.setToolTip(get_tooltip_for_bc(1 + int(key.split('_')[0][3:])))

    def calc_bc_range(self, key, checked):
        """
        Catch when a check box is checked/unchecked and calculate
        the current bitmask.

        Parameters
        ----------
        key : str
            The check box object name.
        checked: bool
            True if the checkbox is checked
        """
        self._bc_bits[key] = checked
        decimal_value = functools.reduce(
            (lambda x, y: (x << 1) | y),
            map(int, [value for value in self._bc_bits.values()])
        )

        # emit the decimal value to the PhotonEnergyRange
        self.bc_range_signal.emit(decimal_value)

    def setup_bc_range_channel(self):
        prefix = self.config.get('line_arbiter_prefix')
        ch = f'ca://{prefix}BeamParamCntl:ReqBP:BeamClassRanges'

        self.bc_range_channel = PyDMChannel(
            ch,
            value_slot=self.bc_range_changed,
            value_signal=self.bc_range_signal,
        )
        self.bc_range_channel.connect()
        self._channels.append(self.bc_range_channel)

    def bc_range_changed(self, bc_range):
        """
        This slot is supposed to handled the initial value of the
        Beamclass Range coming in as soon as we connect, as well
        as whenever this value is changed outside this application.

        Parameters
        ----------
        bc_range : int
            The decimal value of the photon energy range.
        """
        if bc_range is None:
            return

        # EPICS is signed but we want the unsigned 32-bit int
        if bc_range < 0:
            bc_range = 2**32 + bc_range

        binary_range = list(bin(bc_range).replace("0b", ""))
        binary_list = list(map(int, binary_range))
        while len(binary_list) < 15:
            binary_list = [0] + binary_list
        for key, status in zip(self._bc_bits.keys(), binary_list):
            self._bc_bits[key] = bool(status)
            cb = self.findChild(QtWidgets.QCheckBox, key)
            cb.setChecked(bool(status))
        self.update_beamclass_max_from_bitmask(bc_range)

    def setup_ev_rbv_channel(self):
        prefix = self.config.get('line_arbiter_prefix')
        self.ev_ranges = None
        self.last_ev_range = 0
        ev_definition = PyDMChannel(
            f'ca://{prefix}eVRangeCnst_RBV',
            value_slot=self.new_ev_ranges,
        )
        ev_definition.connect()
        self._channels.append(ev_definition)
        self.ev_range_rbv_channel = PyDMChannel(
            f'ca://{prefix}BeamParamCntl:ReqBP:PhotonEnergyRanges_RBV',
            value_slot=self.on_ev_range_rbv_update,
        )
        self.ev_range_rbv_channel.connect()
        self._channels.append(self.ev_range_rbv_channel)

    def setup_bc_rbv_channel(self):
        prefix = self.config.get('line_arbiter_prefix')
        ch = f'ca://{prefix}BeamParamCntl:ReqBP:BeamClassRanges_RBV'
        self.bc_range_rbv_channel = PyDMChannel(
            ch,
            value_slot=self.on_bc_range_rbv_update,
        )
        self.bc_range_rbv_channel.connect()
        self._channels.append(self.bc_range_rbv_channel)

    def setup_zero_rate(self):
        self.ui.zeroRate.clicked.connect(self.set_zero_rate)
        self.rate_req = None
        self.beamclass_req = None
        self.apply_attempts = 0
        self.zero_rate_timer = QtCore.QTimer()
        self.zero_rate_timer.timeout.connect(self.apply_zero_rate)
        self.zero_rate_timer.setSingleShot(True)
        self.zero_rate_timer.setInterval(100)

    def watch_rate_update(self, value):
        """
        Watch the rate channel so we know the most recent value.

        This is also used to update the rate selection combobox on
        one GUI after another GUI makes a selection.
        """
        self.rate_req = value
        self.update_rate_combobox_value(value)

    def set_zero_rate(self):
        """
        Slot activated when the zero rate button is pressed.

        Modify the rate edit, emit a signal for the apply step.
        """
        self.apply_attempts = 0
        self.update_rate_signal.emit(0)
        self.update_beamclass_signal.emit(0)
        self.zero_rate_timer.start()

    def apply_zero_rate(self):
        """
        Try every 100ms, if our rate was updated then apply it.
        """
        if self.rate_req == 0:
            self.applyButton.sendValue()
        elif self.apply_attempts <= 10:
            self.apply_attempts += 1
            self.zero_rate_timer.start()
        else:
            raise_to_operator(
                TimeoutError('Apply zero rate failed!')
            )

    def setup_rate_combo(self):
        """
        Fill the combobox for rate selection and make it work.
        """
        for rate in VALID_RATES:
            self.ui.rateComboBox.addItem(f'{rate} Hz')
        self.ui.rateComboBox.activated.connect(self.select_new_rate)

    def select_new_rate(self, index):
        """
        Handler for when the user selects a new rate using the combo box.
        """
        self.update_rate_signal.emit(VALID_RATES[index])

    def update_rate_combobox_value(self, value):
        """
        Set the combobox to the index that corresponds with value.

        This does not write to the PV, it just changes the visual
        state of the combobox.

        If value is not a valid value, the combobox will display the
        nearest lowest valid value.
        """
        valid_rate = get_valid_rate(value)
        self.ui.rateComboBox.setCurrentIndex(VALID_RATES.index(valid_rate))

    def setup_beamclass_combo(self):
        """
        Fill the combobox for beamclass selection and make it work.
        """
        for beamclass_index in range(len(bc_table)):
            desc = get_desc_for_bc(beamclass_index)
            self.ui.beamclassComboBox.addItem(f'{beamclass_index}: {desc}')
        self.update_beamclass_combobox_tooltip(0)
        self.ui.beamclassComboBox.activated.connect(self.select_new_beamclass)
        self.ui.beamclassComboBox.currentIndexChanged.connect(
            self.update_beamclass_combobox_tooltip
        )

    def update_beamclass_combobox_tooltip(self, index):
        """Make the beamclass combobox tooltip match the text."""
        self.ui.beamclassComboBox.setToolTip(get_tooltip_for_bc(index))

    def select_new_beamclass(self, index):
        """
        Handler for when the user selects a new beamclass using the combo box.
        """
        self.update_beamclass_signal.emit(index)

    def update_beamclass_combobox_value(self, value):
        """
        Set the combobox to the index that corresponds with value.

        This does not write to the PV, it just changes the visual
        state of the combobox.
        """
        self.ui.beamclassComboBox.setCurrentIndex(value)

    def update_beamclass_bitmask_from_max(self, value):
        """
        Given a max value, generate the simplified beamclass bitmask.

        This is a bitmask that doesn't skip any bits between 0 and the
        desired max value.
        """
        self.bc_range_signal.emit(2**value-1)

    def update_beamclass_max_from_bitmask(self, value):
        """
        Given a bitmask, update the max value combobox appropriately.
        """
        count = 0
        while value > 0:
            count += 1
            value = value >> 1
        self.update_beamclass_combobox_value(count)

    def on_ev_range_rbv_update(self, value):
        self.update_ev_tooltip(value)

    def update_ev_tooltip(self, value=None):
        if value is None:
            value = self.last_ev_range
        else:
            self.last_ev_range = value
        if self.ev_ranges is None:
            return
        self.ui.ev_rbv_bytes.PyDMToolTip = get_ev_range_tooltip(value, self.ev_ranges)

    def new_ev_ranges(self, value):
        self.ev_ranges = value
        self.update_ev_tooltip()

    def on_bc_range_rbv_update(self, value):
        # Update the rbv tooltips
        self.ui.bc_rbv_bytes.PyDMToolTip = get_tooltip_for_bc_bitmask(value)
        # Update the max bc label
        count = 0
        while value > 0:
            count += 1
            value = value >> 1
        self.ui.max_bc_label.setText(str(count))
        self.ui.max_bc_label.setToolTip(get_tooltip_for_bc(count))
