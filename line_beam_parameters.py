import functools
from string import Template

from pydm.widgets.channel import PyDMChannel
from pydm import Display
from pydm.widgets import PyDMLabel
from qtpy import QtCore, QtWidgets
from pmps import morph_into_vertical


class LineBeamParametersControl(Display):
    """
    Class to handle display for the Line Beam Parameters Control tab.
    """
    # object names for all energy range bits checkboxes, set them all
    # to checked to start with
    _bits = {'bit15': True, 'bit14': True, 'bit13': True, 'bit12': True,
             'bit11': True, 'bit10': True, 'bit9': True, 'bit8': True,
             'bit7': True, 'bit6': True, 'bit5': True, 'bit4': True,
             'bit3': True, 'bit2': True, 'bit1': True, 'bit0': True}

    # signal to emit when energy range is changed
    energy_range_signal = QtCore.Signal(int)

    def __init__(self, parent=None, args=None, macros=None):
        super(LineBeamParametersControl, self).__init__(parent=parent,
                                                        args=args,
                                                        macros=macros)
        self.config = macros
        self.setup_ui()

    def setup_ui(self):
        self.setup_bits_connections()
        self.setup_bit_indicators()
        self.setup_energy_range_channel()

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
        status = True if state == 2 else False
        self._bits[key] = status

        bit_map = list(map(int, [item for key, item in self._bits.items()]))
        out = 0
        for bit in bit_map:
            # Shift left by pushing zeros in
            # from the right and let the leftmost bits fall off
            # Sets each bit to 1 if one of two bits is 1
            out = (out << 1) | bit
        print(out)
        # TODO: comment out here because I don't know if this is what we want yet
        # This would set the value of this PV:
        # 'ca://${PREFIX}BeamParamCntl:ReqBP:PhotonEnergyRanges' to out
        # self.energy_range_signal.emit(out)

    def setup_energy_range_channel(self):
        prefix = self.config.get('line_arbiter_prefix')
        # TODO: comment this out for now because not sure if this is what I should be doing
        # ch_macros = dict(PREFIX=prefix)
        # ch = Template(
        #     'ca://${PREFIX}BeamParamCntl:ReqBP:PhotonEnergyRanges').safe_substitute(**ch_macros)
        # channel = PyDMChannel(
        #     ch,
        #     value_slot=self.energy_range_changed,
        #     value_signal=self.energy_range_signal
        # )
        # channel.connect()

    def energy_range_changed(self, range):
        # TODO i might need this at first to set the bits initially - not sure yet.
        print(f'Energy Changed: {range}')
        print(f'The range changed {range}')

    def ui_filename(self):
        return 'line_beam_parameters.ui'
