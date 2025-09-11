import functools
import math

from pydm import Display
from pydm.exception import raise_to_operator
from pydm.widgets import PyDMLabel
from pydm.widgets.channel import PyDMChannel
from qtpy import QtCore, QtWidgets

from .beamclass_table import bc_table, bc_power, get_desc_for_bc, install_bc_setText
from .data_bounds import VALID_RATES, get_valid_rate
from .tooltips import get_tooltip_for_bc
from .utils import morph_into_vertical


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

    # Signal to set a new transmission, adjusted by the jf
    new_transmission_signal = QtCore.Signal(float)

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.config = macros
        self._channels = []
        self.setup_ui()

    def channels(self):
        "Make sure PyDM can find the channels we set up for cleanup."
        return self._channels

    def ui_filename(self):
        return 'ui/line_beam_parameters.ui'

    def setup_ui(self):
        self.setup_bits_connections()
        self.setup_bit_indicators()
        self.setup_energy_range_channel()
        self.setup_rate_channel()
        self.setup_bc_bits_connections()
        self.setup_bc_range_channel()
        self.setup_bc_rbv_channel()
        self.setup_zero_rate()
        self.setup_rate_combo()
        install_bc_setText(self.ui.max_bc_label)
        self.setup_beamclass_combo()
        self.rate_channel.connect()
        self.setup_transmission_jf()

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

    def setup_bc_rbv_channel(self):
        prefix = self.config.get('line_arbiter_prefix')
        ch = f'ca://{prefix}BeamParamCntl:ReqBP:BeamClassRanges_RBV'
        self.bc_range_rbv_channel = PyDMChannel(
            ch,
            value_slot=self.on_bc_range_rbv_update,
        )
        self.cached_bc_value = 0
        self.bc_range_rbv_channel.connect()
        self._channels.append(self.bc_range_rbv_channel)

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
        if not self.cached_jf_on_off:
            self.update_beamclass_signal.emit(index)
            return
        # Inverted adjustment for judgement factor
        # Pick a number -> send the number that would result in this number given jf
        goal_bc = 0
        eff_bc = 0
        for bc_old, bc_new in self.bc_jf_mapping.items():
            if bc_new > index:
                # Unsafe, no more to check
                break
            if eff_bc < bc_new:
                # Different result than previous loop
                # Favors lowest BC that is safe
                goal_bc = bc_old
                eff_bc = bc_new
        self.update_beamclass_signal.emit(goal_bc)

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
        # Adjust for judgement factor
        bc_value = self.bc_jf_mapping[count]
        self.update_beamclass_combobox_value(bc_value)

    def on_bc_range_rbv_update(self, value):
        # Update the max bc label
        self.cached_bc_value = value
        count = 0
        while value > 0:
            count += 1
            value = value >> 1
        # Adjust for judgement factor
        bc_value = self.bc_jf_mapping[count]
        self.ui.max_bc_label.setText(str(bc_value))
        self.ui.max_bc_label.setToolTip(get_tooltip_for_bc(bc_value))

    def live_power_with_jf(self, p_old: float) -> float:
        """
        Calculate the new beamclass power level after applying the judgement factor override.

        Uses the active judgment factor and other values known by this display.
        """
        return calc_bc_jf_power(p_old=p_old, j_factor=self.get_jf(), t_old=self.cached_transmission_rbv)

    def live_bc_for_power(self, power: float) -> int:
        """
        Calculate the highest beamclass that ensures we don't exceed a given power level.

        Uses the active judgment factor and other values known by this display.
        """
        return calc_bc_for_power(self.live_power_with_jf(p_old=power))

    def update_bc_rbv(self):
        """
        Refresh the visible beamclass summary readbacks.
        """
        self.update_beamclass_max_from_bitmask(self.cached_bc_value)
        self.on_bc_range_rbv_update(self.cached_bc_value)

    def update_bc_jf_mapping(self):
        """
        Update the mapping of old to new beamclass for the judgement factor override.

        Run this whenever the judgement factor or the transmission rbv changes.
        """
        if self.cached_jf_on_off:
            self.bc_jf_mapping = {idx: self.live_bc_for_power(pwr) for idx, pwr in bc_power.items()}
        else:
            self.reset_bc_jf_mapping()
        self.update_bc_rbv()

    def reset_bc_jf_mapping(self):
        """
        Reset the bc_jf_mapping variable to the initial value (no jf active).
        """
        self.bc_jf_mapping = {num: num for num in range(16)}

    def setup_transmission_jf(self) -> None:
        """
        PyDMChannel and signal/slot setup for the transmission values.

        This has special handling due to the introduction of the
        "jugement factor" transmission override. The line beam parameter
        transmission values are also subject to rescaling due to the
        judgement factor, but it is convenient for the user to be able
        to express their line beam parameter transmission request
        in terms of an absolute number instead of as a pre-override
        number.

        This intercepts the user's desired transmission before sending
        it to the IOC, and acts as a multiplier on the incoming
        transmission rbv so things work as expected.

        Note: this only applies when the user selects a new
        transmission, if a transmission is already applied then
        the judgement factor cannot be changed immediately. The user
        will need to supply a new transmission value. In these cases,
        the readback will always reflect the reality of the "effective"
        transmission for the current maximum credible beam energy
        judgement factor.
        """
        try:
            line_arbiter_prefix = self.config["line_arbiter_prefix"]
        except KeyError:
            return
        # Values to use prior to various PV connections
        self.cached_transmission_rbv = 1
        self.cached_jf_setting = 5
        self.cached_jf_on_off = False
        self.reset_bc_jf_mapping()
        # If we emit from self.new_transmission_signal, put to the real PV
        self.trans_set_channel = PyDMChannel(
            f"ca://{line_arbiter_prefix}BeamParamCntl:ReqBP:Transmission",
            value_signal=self.new_transmission_signal,
        )
        # We get inputs from the user via a local channel
        # I do this to take advantage of PyDMLineEdit's input handling
        self._remaining_init_trans_sets = 2
        self.gui_trans_set_channel = PyDMChannel(
            "loc://trans_set?type=float&init=1&precision=2",
            value_slot=self.gui_trans_set,
        )
        # If we get a new value, show the scaled value
        self.trans_get_channel = PyDMChannel(
            f"ca://{line_arbiter_prefix}BeamParamCntl:ReqBP:Transmission_RBV",
            value_slot=self.new_trans_value,
        )
        # If we get a new JF, cache it and show the scaled value
        self.new_jf_channel = PyDMChannel(
            f"ca://{line_arbiter_prefix}IntensityJF_RBV",
            value_slot=self.new_jf_value,
        )
        # If JF starts/expires, cache it and show the scaled value
        self.jf_on_off_channel = PyDMChannel(
            f"ca://{line_arbiter_prefix}ApplyJF_RBV",
            value_slot=self.new_jf_on_off,
        )
        self.trans_set_channel.connect()
        self.gui_trans_set_channel.connect()
        self.trans_get_channel.connect()
        self.new_jf_channel.connect()
        self.jf_on_off_channel.connect()
        self._channels.append(self.trans_set_channel)
        self._channels.append(self.gui_trans_set_channel)
        self._channels.append(self.trans_get_channel)
        self._channels.append(self.new_jf_channel)
        self._channels.append(self.jf_on_off_channel)

    def new_trans_value(self, value: float) -> None:
        """
        Slot to recieve and use a new transmission readback.

        This is combined with the incoming jf data to update
        the effective transmission readback.
        """
        self.cached_transmission_rbv = value
        self.update_trans_rbv()
        self.update_bc_jf_mapping()

    def new_jf_value(self, value: float) -> None:
        """
        Slot to recieve and use a new judgement factor readback.

        This is used to adjust the raw transmission to
        update the effective transmission readback.
        """
        self.cached_jf_setting = value
        self.update_trans_rbv()
        self.update_bc_jf_mapping()

    def new_jf_on_off(self, value: bool) -> None:
        """
        Slot to recieve and use a new jugement factor on/off readback.

        Ths value is True if the judgement factor is active, and
        False otherwise. We can use this to know whether or not to
        consider the judgement factor value.
        """
        self.cached_jf_on_off = value
        self.update_trans_rbv()
        self.update_bc_jf_mapping()

    def get_jf(self) -> float:
        """
        Helper function to get the current effective judgement factor.

        This is a quantity less than or equal to 5mJ.
        """
        if self.cached_jf_on_off:
            return self.cached_jf_setting or 5
        else:
            return 5

    def update_trans_rbv(self) -> None:
        """
        Use the cached values to update the displayed transmission RBV.

        The displayed RBV will be adjusted based on the current
        effective judgement factor.
        """
        value = min(self.cached_transmission_rbv * 5 / self.get_jf(), 1)
        self.ui.trans_get.setText(f"{value:.2e}")

    def gui_trans_set(self, value: float) -> None:
        """
        Set a new transmission.

        This recieved a value from the user's input and does a calculation
        to write the correct value to the transmission setter based on
        the current judgement factor.
        """
        # On init: avoid writes. This gets called twice before user input.
        # These come from the loc initialization, which is done twice:
        # - once, here
        # - another, from the loc:// channel in the ui xml
        if self._remaining_init_trans_sets > 0:
            self._remaining_init_trans_sets -= 1
            return
        if value == 1.0:
            # Special case: no attenuation requested, request none
            setpoint = 1.0
        else:
            # Normal case: specific attenuation requested, modify it
            setpoint = value * self.get_jf() / 5
        self.new_transmission_signal.emit(setpoint)


def calc_bc_jf_power(p_old: float, j_factor: float, t_old: float) -> float:
    """
    Calculate the new beamclass power level after applying the judgement factor override.

    Follows the formula:
    p_new = p_old * (5mj / e_max) * t_old

    Parameters
    ----------
    p_old : float
        The original beamclass power before applying the judgement factor.
    j_factor : float
        The judgement factor, is expected to be above 0 and less than 5.
    t_old : float
        The transmission request prior to overriding with the judgement factor.

    Returns
    -------
    float
        The updated beamclass power level.
    """
    return p_old * (5 / j_factor) * t_old


def calc_bc_for_power(power: float) -> int:
    """
    Given a power level, calculate the highest beamclass that ensures we don't exceed it.
    """
    bc_idx = 0
    for idx, power_of_bc in bc_power.items():
        # Duplicate logic from PLC
        if math.floor(power) + 1 >= power_of_bc:
            bc_idx = idx
        else:
            break
    return bc_idx