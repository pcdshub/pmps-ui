import functools
from string import Template

from pydm import Display
from pydm.exception import raise_to_operator
from pydm.widgets import PyDMLabel
from pydm.widgets.channel import PyDMChannel
from qtpy import QtCore, QtWidgets

from fast_faults import clear_channel
from pmps import morph_into_vertical


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

    def __init__(self, parent=None, args=None, macros=None):
        super(LineBeamParametersControl, self).__init__(parent=parent,
                                                        args=args,
                                                        macros=macros)
        self.config = macros
        self.setup_ui()

        if self.energy_channel is not None:
            self.destroyed.connect(functools.partial(clear_channel,
                                                     self.energy_channel))
        if self.rate_channel is not None:
            self.destroyed.connect(functools.partial(clear_channel,
                                                     self.rate_channel))

    def setup_ui(self):
        self.setup_bits_connections()
        self.setup_bit_indicators()
        self.setup_energy_range_channel()
        self.setup_zero_rate()

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

    def setup_zero_rate(self):
        self.ui.zeroRate.clicked.connect(self.set_zero_rate)
        self.ui.placeholder.hide()
        self.rate_req = None
        self.apply_attempts = 0
        self.rate_channel = PyDMChannel(
            self.ui.rateEdit.channel,
            value_slot=self.watch_rate_update,
        )
        self.rate_channel.connect()
        self.zero_rate_timer = QtCore.QTimer()
        self.zero_rate_timer.timeout.connect(self.apply_zero_rate)
        self.zero_rate_timer.setSingleShot(True)
        self.zero_rate_timer.setInterval(100)

    def watch_rate_update(self, value):
        """
        Watch the rate channel so we know the most recent value.
        """
        self.rate_req = value

    def set_zero_rate(self):
        """
        Slot activated when the zero rate button is pressed.

        Modify the rate edit, emit a signal for the apply step.
        """
        self.apply_attempts = 0
        self.rateEdit.setText('0 Hz')
        self.rateEdit.send_value()
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

    def ui_filename(self):
        return 'line_beam_parameters.ui'
