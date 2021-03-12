import functools
from string import Template

from pydm.widgets.channel import PyDMChannel
from pydm import Display
from pydm.widgets import PyDMLabel
from qtpy import QtCore, QtWidgets
from pmps import morph_into_vertical
from fast_faults import clear_channel


class LineBeamParametersControl(Display):
    """
    Class to handle display for the Line Beam Parameters Control tab.
    """
    # object names for all energy range bits checkboxes, set them all
    # to checked to start with
    _bits = {'bit15': False, 'bit14': False, 'bit13': False, 'bit12': False,
             'bit11': False, 'bit10': False, 'bit9': False, 'bit8': False,
             'bit7': False, 'bit6': False, 'bit5': False, 'bit4': False,
             'bit3': False, 'bit2': False, 'bit1': False, 'bit0': False}

    # signal to emit when energy range is changed
    energy_range_signal = QtCore.Signal(int)

    energy_channel = None

    def __init__(self, parent=None, args=None, macros=None):
        super(LineBeamParametersControl, self).__init__(parent=parent,
                                                        args=args,
                                                        macros=macros)
        self.config = macros
        self.setup_ui()

        if self.energy_channel:
            self.destroyed.connect(functools.partial(clear_channel,
                                                     self.energy_channel))

    def setup_ui(self):
        self.setup_bits_connections()
        self.setup_bit_indicators()
        self.setup_energy_range_channel()
        self.energy_range_changed(47103)

    def setup_bits_connections(self):
        """
        Connect all the check boxes bits with the calc_energy_range method to
        calculate the range upon changing a bit state.
        """
        for key, item in self._bits.items():
            cb = self.findChild(QtWidgets.QCheckBox, f"{key}")
            cb.stateChanged.connect(functools.partial(self.calc_energy_range, key))

    def setup_bit_indicators(self):
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
        if self.energy_range_groupBox.isChecked():
            status = True if state == 2 else False
            self._bits[key] = status

            bit_map = list(map(int, [item for key, item in self._bits.items()]))
            out = 0
            for bit in bit_map:
                # Shift left by pushing zeros in
                # from the right and let the leftmost bits fall off
                # Sets each bit to 1 if one of two bits is 1
                out = (out << 1) | bit
            # This would set the value of this PV:
            # 'ca://${PREFIX}BeamParamCntl:ReqBP:PhotonEnergyRanges' to out
            self.energy_range_signal.emit(out)
        else:
            # we don't want to update this if the combo box is not checked
            return

    def setup_energy_range_channel(self):
        prefix = self.config.get('line_arbiter_prefix')

        ch_macros = dict(PREFIX=prefix)
        ch = Template(
            'ca://${PREFIX}BeamParamCntl:ReqBP:PhotonEnergyRanges').safe_substitute(**ch_macros)
        self.energy_channel = PyDMChannel(
            ch,
            connection_slot=self.connected_energy_range,
            value_slot=self.energy_range_changed,
            value_signal=self.energy_range_signal
        )
        self.energy_channel.connect()
        # TODO: remove this - only for testing
        self.energy_range_signal.connect(self.catch_the_signal)

    def connected_energy_range(self):
        # getting in here when the connection of energy_range changes
        # TODO: probably don't need this method at all
        ...

    # TODO: remove this - only for testing
    @QtCore.Slot(int)
    def catch_the_signal(self, energy_range):
        print(energy_range)

    def energy_range_changed(self, energy_range):
        """
        Connect to this slot only ones - at first, then disconnect.
        """
        # TODO i might need this at first to set the bits initially - not sure yet.
        # can i connect this ones and then disconnect it right away?
        print(f'checked: {self.energy_range_groupBox.isChecked()}')
        if self.energy_range_groupBox.isChecked() is False:
            print(f'The range changed {energy_range}')

            binary_range = list(bin(energy_range).replace("0b", ""))
            binary_list = list(map(int, binary_range))
            print(binary_list)
            # status = True if state == 2 else False
            for key, status in zip(self._bits.keys(), binary_list):
                self._bits[key] = bool(status)
                cb = self.findChild(QtWidgets.QCheckBox, f"{key}")
                state = 2 if status == 1 else 0
                print(state)
                cb.setCheckState(state)
            print(self._bits)
        else:
            # do nothing here if it is checked...
            # TODO: it would be nice to disconnect this guy here after it got the first value
            return

    def ui_filename(self):
        return 'line_beam_parameters.ui'
