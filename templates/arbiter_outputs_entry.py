from __future__ import annotations

from pydm import Display
from pydm.widgets.channel import PyDMChannel
from qtpy.QtCore import QObject, QTimer, Signal


class ArbiterRow(Display):
    fault_summaries: list[FaultSummary]
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
        self.fault_summaries = []
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
        # Use the bypass channel to get the bypass counts
        bypass_counter = CounterElement(
            pvname=f"ca://{self.prefix}FFO:{self.ffo}:FF:{fault_num_str}:Ovrd:Active_RBV",
            index=self.loop_count,
            value_cache=self.bypasses,
            parent=self,
        )
        bypass_dest = PyDMChannel(
            address=f"loc://{self.prefix}{self.ffo}:BypassCount?type=int&init=0",
            value_slot=self.new_bypass_count,
            value_signal=bypass_counter.value_sig,
        )
        self.bypass_counters.append(bypass_counter)
        self.bypasses.append(0)
        bypass_dest.connect()
        self._channels.append(bypass_dest)
        bypass_ch = bypass_counter.create_channel()
        bypass_ch.connect()
        self._channels.append(bypass_ch)

        # Use the in_use channel to get the registered and connected counts
        in_use_counter = CounterElement(
            pvname=f"ca://{self.prefix}FFO:{self.ffo}:FF:{fault_num_str}:Info:InUse_RBV",
            index=self.loop_count,
            value_cache=self.in_uses,
            conn_cache=self.is_connected,
            parent=self,
        )
        in_use_dest = PyDMChannel(
            address=f"loc://{self.prefix}{self.ffo}:RegCount?type=int&init=0",
            value_slot=self.show_loc_connected,
            value_signal=in_use_counter.value_sig,
        )
        in_use_conn_dest = PyDMChannel(
            address=f"loc://{self.prefix}{self.ffo}:ConnCount?type=int&init=0",
            value_slot=self.show_loc_connected,
            value_signal=in_use_counter.conn_sig,
        )
        self.in_use_counters.append(in_use_counter)
        self.in_uses.append(0)
        self.is_connected.append(0)
        in_use_dest.connect()
        in_use_conn_dest.connect()
        self._channels.append(in_use_dest)
        self._channels.append(in_use_conn_dest)
        ic_ch = in_use_counter.create_channel()
        ic_ch.connect()
        self._channels.append(ic_ch)

        # Combine the ok and in_use channels to get the fault counts
        # We are fauling if ok=False and in_use=True
        # Summarize this as a combined local channel
        fault_summary = FaultSummary(
            ok_pvname=f"ca://{self.prefix}FFO:{self.ffo}:FF:{fault_num_str}:OK_RBV",
            in_use_pvname=f"ca://{self.prefix}FFO:{self.ffo}:FF:{fault_num_str}:Info:InUse_RBV",
            parent=self,
        )
        fault_summary_ch1, fault_summary_ch2 = fault_summary.create_channels()
        fault_summary_ch3 = PyDMChannel(
            address=f"loc://{self.prefix}{self.ffo}{fault_num_str}:SUMMARY?type=int&init=0",
            value_signal=fault_summary.value_sig,
            value_slot=self.show_loc_connected,
        )
        fault_counter = CounterElement(
            pvname=f"loc://{self.prefix}{self.ffo}{fault_num_str}:SUMMARY?type=int&init=0",
            index=self.loop_count,
            value_cache=self.faults,
            parent=self,
        )
        fault_counter_ch = fault_counter.create_channel()
        fault_dest_ch = PyDMChannel(
            address=f"loc://{self.prefix}{self.ffo}:FaultCount?type=int&init=0",
            value_slot=self.new_fault_count,
            value_signal=fault_counter.value_sig,
        )
        self.fault_summaries.append(fault_summary)
        self.fault_counters.append(fault_counter)
        self.faults.append(0)
        # Connect from the last in the chain to the first
        for ch in (
            fault_dest_ch,
            fault_counter_ch,
            fault_summary_ch3,
            fault_summary_ch2,
            fault_summary_ch1,
        ):
            ch.connect()
            self._channels.append(ch)

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
            self.ui.bypass_label.alarm_severity_changed(1)
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
        parent: QObject | None = None,
    ):
        super().__init__(parent=parent)
        self.pvname = pvname
        self.index = index
        self.value_cache = value_cache
        self.conn_cache = conn_cache

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
        self.value_cache[self.index] = value
        self.value_sig.emit(sum(self.value_cache))

    def new_conn(self, conn: int) -> None:
        self.conn_cache[self.index] = conn
        self.conn_sig.emit(sum(self.conn_cache))


class FaultSummary(QObject):
    value_sig = Signal(int)
    is_ok: int
    is_in_use: int

    def __init__(
        self,
        ok_pvname: str,
        in_use_pvname: str,
        parent: QObject | None,
    ):
        super().__init__(parent=parent)
        self.ok_pvname = ok_pvname
        self.in_use_pvname = in_use_pvname
        self.is_ok = 0
        self.is_in_use = 0

    def create_channels(self) -> tuple[PyDMChannel, PyDMChannel]:
        return PyDMChannel(
            address=self.ok_pvname,
            value_slot=self.new_ok,
        ), PyDMChannel(
            address=self.in_use_pvname,
            value_slot=self.new_in_use,
        )

    def new_ok(self, value: int):
        self.is_ok = value
        self.new_fault()

    def new_in_use(self, value: int):
        self.is_in_use = value
        self.new_fault()

    def new_fault(self):
        if self.is_in_use:
            self.value_sig.emit(1 - self.is_ok)
        else:
            self.value_sig.emit(0)
