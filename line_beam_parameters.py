import functools
from string import Template

from pydm import Display
from pydm.exception import raise_to_operator
from pydm.widgets import PyDMLabel
from pydm.widgets.channel import PyDMChannel
from qtpy import QtCore, QtWidgets

from beamclass_table import bc_table, get_desc_for_bc, get_tooltip_for_bc
from data_bounds import VALID_RATES, get_valid_rate
from utils import morph_into_vertical


class LineBeamParametersControl(Display):
    """
    Class to handle display for the Line Beam Parameters Control tab.
    """
    # object names for all energy range bits checkboxes, set them all
    # to unchecked to start with
    _bits = {f'bit{num}': False for num in reversed(range(32))}

    # signal to emit when energy range is changed
    energy_range_signal = QtCore.Signal(int)

    # this is a gate to break an infinite loop of
    # - Update from channel value
    # - Write back to channel
    _setting_bits = False
    energy_channel = None

    # Monitor the rate readback for use in the zero rate button
    rate_channel = None

    # Signal to set a new rate from the combobox or from zero rate button
    update_rate_signal = QtCore.Signal(int)
    # Signal to set a new beamclass from the combobox or from zero rate button
    update_beamclass_signal = QtCore.Signal(int)

    def __init__(self, parent=None, args=None, macros=None):
        super(LineBeamParametersControl, self).__init__(parent=parent,
                                                        args=args,
                                                        macros=macros)
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
        self.setup_zero_rate()
        self.setup_rate_combo()
        self.setup_beamclass_combo()
        self.rate_channel.connect()

    def setup_bits_connections(self):
        """
        Connect all the check boxes bits with the calc_energy_range method to
        calculate the range upon changing a bit state.
        """
        for key, item in self._bits.items():
            cb = self.findChild(QtWidgets.QCheckBox, key)
            cb.stateChanged.connect(functools.partial(
                self.calc_energy_range, key))

    def setup_bit_indicators(self):
        """
        Borrowed function from fast_faults, to help morph the labels vertically
        """
        for key in self._bits.keys():
            label = self.findChild(PyDMLabel, f"label_{key}")
            if label is not None:
                morph_into_vertical(label)

    def calc_energy_range(self, key, state):
        """
        Catch when a check box is checked/unchecked and calculate
        the current bitmask.

        Parameters
        ----------
        key : str
            The check box object name.
        state : int
            The state of the check box.
            0 = unchecked
            2 = checked

        Note
        ----
        The checkboxes can be tri-states - here we use the states 0 and 2
        for unchecked and checked respectively.
        """
        status = state == 2
        self._bits[key] = status
        decimal_value = functools.reduce(
            (lambda x, y: (x << 1) | y),
            map(int, [item for key, item in self._bits.items()])
        )

        if not self._setting_bits:
            # emit the decimal value to the PhotonEnergyRange
            self.energy_range_signal.emit(decimal_value)

    def setup_energy_range_channel(self):
        prefix = self.config.get('line_arbiter_prefix')

        ch_macros = dict(PREFIX=prefix)
        ch = Template(
            'ca://${PREFIX}BeamParamCntl:ReqBP:PhotonEnergyRanges').safe_substitute(**ch_macros)
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
        self._setting_bits = True
        for key, status in zip(self._bits.keys(), binary_list):
            self._bits[key] = bool(status)
            cb = self.findChild(QtWidgets.QCheckBox, f"{key}")
            state = 2 if status == 1 else 0
            cb.setCheckState(state)
        # set this value back to false so we don't create a infinite
        # loop between this slot and the energy_range_signal signal.
        self._setting_bits = False

    def setup_rate_channel(self):
        prefix = self.config.get('line_arbiter_prefix')
        self.rate_channel = PyDMChannel(
            f'ca://{prefix}BeamParamCntl:ReqBP:Rate',
            value_slot=self.watch_rate_update,
            value_signal=self.update_rate_signal,
        )
        self.beamclass_channel = PyDMChannel(
            f'ca://{prefix}BeamParamCntl:ReqBP:BeamClass',
            value_slot=self.watch_beamclass_update,
            value_signal=self.update_beamclass_signal,
        )
        self.beamclass_rbv_channel = PyDMChannel(
            f'ca://{prefix}BeamParamCntl:ReqBP:BeamClass_RBV',
            value_slot=self.watch_beamclass_rbv_update,
        )
        self._channels.append(self.rate_channel)
        self._channels.append(self.beamclass_channel)
        self._channels.append(self.beamclass_rbv_channel)

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

    def watch_beamclass_update(self, value):
        """
        Watch the beamclass channel so we know the most recent value.

        This is also used to update the beamclass selection combobox on
        one GUI after another GUI makes a selection, as well as the tooltip
        with the most recent beamclass summary information.
        """
        self.beamclass_req = value
        self.update_beamclass_combobox_value(value)

    def watch_beamclass_rbv_update(self, value):
        """
        Watch the beamclass channel so we know the most recent value.

        This is also used to update the rbv tooltip with the most recent
        beamclass summary information.
        """
        self.ui.beamclass_rbv_label.PyDMToolTip = get_tooltip_for_bc(value)

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
            if desc == 'Spare':
                continue
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
        self.ui.beamclassCombobox.setCurrentIndex(value)
