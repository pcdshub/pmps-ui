from __future__ import annotations

from pydm import Display
from pydm.widgets.channel import PyDMChannel
from qtpy.QtCore import QObject, QTimer, Signal


class ArbiterRow(Display):
    fault_counters: list[CounterElement]
    faults: list[bool]
    bypass_counters: list[CounterElement]
    bypasses: list[bool]
    in_use_counters: list[CounterElement]
    in_uses: list[bool]
    is_connected: list[bool]

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.config = macros
        self._channels = []
        self.fault_counters = []
        self.bypass_counters = []
        self.in_use_counters = []
        self.faults = []
        self.bypasses = []
        self.in_uses = []
        self.is_connected = []
        self.setup_ui()

    def setup_ui(self):
        self.setup_counters()

    def setup_counters(self):
        self.prefix = self.config["P"]
        self.ffo = self.config["FFO"]
        self.ff_start = self.config["ff_start"]
        self.fault_num = self.ff_start
        self.ff_end = self.config["ff_end"]
        self.zfill = len(str(self.ff_end)) + 1
        self.loop_count = 0

        self.next_counter_soon()

    def next_counter_soon(self):
        self.setup_counter_timer = QTimer()
        self.setup_counter_timer.singleShot(1, self.setup_next_counter)

    def setup_next_counter(self):
        fault_num_str = str(self.fault_num).zfill(self.zfill)
        # Use the ok channel to get the faulting counts
        fc = CounterElement(
            pvname=f"ca://{self.prefix}FFO:{self.ffo}:FF:{fault_num_str}:OK_RBV",
            index=self.loop_count,
            value_cache=self.faults,
            invert=True,
        )
        fc_dest = PyDMChannel(
            address=f"loc://{self.prefix}{self.ffo}:FaultCount?type=int&init=0",
            value_slot=self.new_fault_count,
            value_signal=fc.value_sig,
        )
        self.fault_counters.append(fc)
        self.faults.append(0)
        fc_dest.connect()
        self._channels.append(fc_dest)
        fc_ch = fc.create_channel()
        fc_ch.connect()
        self._channels.append(fc_ch)

        # Use the bypass channel to get the bypass counts
        bc = CounterElement(
            pvname=f"ca://{self.prefix}FFO:{self.ffo}:FF:{fault_num_str}:Ovrd:Active_RBV",
            index=self.loop_count,
            value_cache=self.bypasses,
        )
        bc_dest = PyDMChannel(
            address=f"loc://{self.prefix}{self.ffo}:BypassCount?type=int&init=0",
            value_slot=self.new_bypass_count,
            value_signal=bc.value_sig,
        )
        self.bypass_counters.append(bc)
        self.bypasses.append(0)
        bc_dest.connect()
        self._channels.append(bc_dest)
        bc_ch = bc.create_channel()
        bc_ch.connect()
        self._channels.append(bc_ch)

        # Use the in_use channel to get the registered and connected counts
        ic = CounterElement(
            pvname=f"ca://{self.prefix}FFO:{self.ffo}:FF:{fault_num_str}:Info:InUse_RBV",
            index=self.loop_count,
            value_cache=self.in_uses,
            conn_cache=self.is_connected,
        )
        ic_dest = PyDMChannel(
            address=f"loc://{self.prefix}{self.ffo}:RegCount?type=int&init=0",
            value_slot=self.show_loc_connected,
            value_signal=ic.value_sig,
        )
        ic_conn_dest = PyDMChannel(
            address=f"loc://{self.prefix}{self.ffo}:ConnCount?type=int&init=0",
            value_slot=self.show_loc_connected,
            value_signal=ic.conn_sig,
        )
        self.in_use_counters.append(ic)
        self.in_uses.append(0)
        self.is_connected.append(0)
        ic_dest.connect()
        ic_conn_dest.connect()
        self._channels.append(ic_dest)
        self._channels.append(ic_conn_dest)
        ic_ch = ic.create_channel()
        ic_ch.connect()
        self._channels.append(ic_ch)

        self.loop_count += 1
        self.fault_num += 1

        if self.fault_num <= self.ff_end:
            self.next_counter_soon()

    def show_loc_connected(self, *args, **kwargs):
        ...

    def new_fault_count(self, count: int):
        if count:
            self.ui.fault_label.alarm_severity_changed(2)
        else:
            self.ui.fault_label.alarm_severity_changed(0)

    def new_bypass_count(self, count: int):
        if count:
            self.ui.bypass_label.alarm_severity_changed(2)
        else:
            self.ui.bypass_label.alarm_severity_changed(0)

    def channels(self):
        return self._channels

    def ui_filename(self):
        return 'arbiter_outputs_entry.ui'


class CounterElement(QObject):
    value_sig = Signal(int)
    conn_sig = Signal(int)

    def __init__(
        self,
        pvname: str,
        index: int,
        value_cache: list[int],
        conn_cache: list[int] | None = None,
        invert: bool = False,
        parent: QObject | None = None,
    ):
        super().__init__(parent=parent)
        self.pvname = pvname
        self.index = index
        self.value_cache = value_cache
        self.conn_cache = conn_cache
        self.invert = invert

    def create_channel(self) -> PyDMChannel:
        if self.conn_cache is None:
            return PyDMChannel(
                address=self.pvname,
                value_slot=self.new_value,
            )
        else:
            return PyDMChannel(
                address=self.pvname,
                value_slot=self.new_value,
                connection_slot=self.new_conn,
            )

    def new_value(self, value: int) -> None:
        if self.invert:
            value = 1 - value
        self.value_cache[self.index] = value
        self.value_sig.emit(sum(self.value_cache))

    def new_conn(self, conn: int) -> None:
        self.conn_cache[self.index] = conn
        self.conn_sig.emit(sum(self.conn_cache))
