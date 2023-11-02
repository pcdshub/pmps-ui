"""
Embedded pydm screen for a single row in the Arbiter Outputs table.

Rather than putting this functionality into arbiter_outputs.py and reaching
into the embedded widgets, it is cleaner to include it here and apply the
behavior to the ui file in a more natural way.
"""
from __future__ import annotations

from pydm import Display
from pydm.widgets.channel import PyDMChannel
from qtpy.QtCore import QObject, QTimer, Signal


class ArbiterRow(Display):
    """
    PyDM display that represents one row in the Arbiter Outputs table.

    This class is responsible for adding PyDM connections to all of the
    fast fault PVs and keeping track of their status via counting.

    The ui file this class uses has additional widgets for indicator
    lights and text display that are paramterized via macros like normal
    code-free pydm screens.
    """
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

    def setup_ui(self) -> None:
        """Standard-use catch-all method name for qt startup actions."""
        self.setup_counters()

    def setup_counters(self) -> None:
        """
        Connect to the fast fault PVs and initialize the counters.

        This sets up the initial conditions for the async chain of
        next_counter_soon calls that split up the widget setup into
        multiple qt events. It is implemented in this way so that the
        render events and the user's input events can happen during
        setup while this tab loads in the background.

        You can think of this like a fancy for loop.
        """
        self.prefix = self.config["P"]
        self.ffo = self.config["FFO"]
        self.ff_start = self.config["ff_start"]
        self.fault_num = self.ff_start
        self.ff_end = self.config["ff_end"]
        self.zfill = len(str(self.ff_end)) + 1
        self.loop_count = 0

        self.next_counter_soon()

    def next_counter_soon(self) -> None:
        """
        Creates a counter by calling setup_next_counter on the qt event queue.

        Combined with setup_next_counter, this starts or continues a chain of
        counter instantiations that ends when we exhaust our list of
        configured PVs.

        The event will happen 1ms after this method call to give plenty
        of time for user input and rendering events, while not being so long
        as to drag out the chain of initialization.

        A reference is held to the QTimer to prevent garbage collection,
        but I'm not entirely sure this is needed.
        """
        self.setup_counter_timer = QTimer()
        self.setup_counter_timer.singleShot(1, self.setup_next_counter)

    def setup_next_counter(self) -> None:
        """
        Adds one additional counting source, then calls next_counter_soon.

        Combined with next_counter_soon, this starts or continues a chain of
        counter instantiations that ends when we exhaust our list of
        configured PVs.

        Each counting source is a group of PyDM channels that consume
        EPICS PVs with information pertaining to fast faults.
        These are then aggregated with all the other counting sources to get
        a total count of e.g. the number of faulting channels, etc.
        """
        fault_num_str = str(self.fault_num).zfill(self.zfill)
        # Use the bypass channel to get the bypass counts
        bypass_counter = CounterElement(
            address=f"ca://{self.prefix}FFO:{self.ffo}:FF:{fault_num_str}:Ovrd:Active_RBV",
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
            address=f"ca://{self.prefix}FFO:{self.ffo}:FF:{fault_num_str}:Info:InUse_RBV",
            index=self.loop_count,
            value_cache=self.in_uses,
            conn_cache=self.is_connected,
            parent=self,
        )
        in_use_dest = PyDMChannel(
            address=f"loc://{self.prefix}{self.ffo}:RegCount?type=int&init=0",
            value_slot=show_loc_connected,
            value_signal=in_use_counter.value_sig,
        )
        in_use_conn_dest = PyDMChannel(
            address=f"loc://{self.prefix}{self.ffo}:ConnCount?type=int&init=0",
            value_slot=show_loc_connected,
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
        # We are faulting if ok=False and in_use=True
        # Summarize this as a combined local channel
        fault_summary = FaultSummary(
            ok_address=f"ca://{self.prefix}FFO:{self.ffo}:FF:{fault_num_str}:OK_RBV",
            in_use_address=f"ca://{self.prefix}FFO:{self.ffo}:FF:{fault_num_str}:Info:InUse_RBV",
            dest_address=f"loc://{self.prefix}{self.ffo}{fault_num_str}:SUMMARY?type=int&init=0",
            parent=self,
        )
        fault_summary_ch1, fault_summary_ch2, fault_summary_ch3 = fault_summary.create_channels()
        fault_counter = CounterElement(
            address=fault_summary.dest_address,
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

    def new_fault_count(self, count: int) -> None:
        """
        Slot for all actions to take when we get a new fault count.
        """
        self.update_fault_label_severity(count)

    def update_fault_label_severity(self, count: int) -> None:
        """
        Show a "major" alarm when the total fault count is nonzero.
        """
        if count:
            self.ui.fault_label.alarm_severity_changed(2)
        else:
            self.ui.fault_label.alarm_severity_changed(0)

    def new_bypass_count(self, count: int) -> None:
        """
        Slot for all actions to take when we get a new bypass count.
        """
        self.update_bypass_label_severity(count)

    def update_bypass_label_severity(self, count: int) -> None:
        """
        Show a "minor" alarm when the total bypass count is nonzero.
        """
        if count:
            self.ui.bypass_label.alarm_severity_changed(1)
        else:
            self.ui.bypass_label.alarm_severity_changed(0)

    def channels(self) -> list[PyDMChannel]:
        """
        Callable method to return a list of open PyDMChannel instances.

        This is sometimes used by PyDM to find channels to clean up.
        """
        return self._channels

    def ui_filename(self) -> str:
        """
        Return the name of the ui file to load for PyDM.
        """
        return 'arbiter_outputs_entry.ui'


class CounterElement(QObject):
    """
    A helper object for including one channel's value in the shared counts.

    Each data source that contributes to a count should have one
    CounterElement that points to the unique channel address and to a shared
    value list and optionally a shared connection list.

    Then, whenever that value source updates (and optionally when the
    connection state changes), this class will update the shared list
    and emit the total count from its value_sig (and optionally the
    conn_sig too.) This design was chosen to avoid race conditions with
    counters and counter statuses. For example, if two counters increment at
    the same time, they will both emit the correct sum regardless of the
    order they reach the emit method call.

    The data source is expected to supply integers that are either 1 or 0.

    Parameters
    ----------
    address : str
        The PyDM channel address to use as the source of data.
    index : int
        The index in the various caches that this counter should write
        its state to.
    value_cache : list of int
        A shared list of all the values from all of the different counter
        elements that contribute to the shared count.
    conn_cache : list of int, optional
        If provided, this is the same as the value_cache except it is used
        to track connection status.
    parent : QObject, optional
        Standard qt parent argument. If provided, it makes this object
        a child object of the parent.
    """
    value_sig = Signal(int)
    conn_sig = Signal(int)

    def __init__(
        self,
        address: str,
        index: int,
        value_cache: list[int],
        conn_cache: list[int] | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent=parent)
        self.address = address
        self.index = index
        self.value_cache = value_cache
        self.conn_cache = conn_cache

    def create_channel(self) -> PyDMChannel:
        """
        Create and return the PyDMChannel object.

        Once connected, this channel will start collecting values
        for the shared lists and this object's signals will be
        active.

        It is best to create and connect the channels only after
        downstream consumers are ready to use the values from value_sig
        and conn_sig.
        """
        if self.conn_cache is None:
            return PyDMChannel(
                address=self.address,
                value_slot=self.new_value,
            )
        else:
            return PyDMChannel(
                address=self.address,
                value_slot=self.new_value,
                connection_slot=self.new_conn,
            )

    def new_value(self, value: int) -> None:
        """
        When a new value is recieved, stash it and emit the total count.
        """
        self.value_cache[self.index] = value
        self.value_sig.emit(sum(self.value_cache))

    def new_conn(self, conn: int) -> None:
        """
        When a new connection state is recieved, stash it and emit the total count.
        """
        self.conn_cache[self.index] = conn
        self.conn_sig.emit(sum(self.conn_cache))


class FaultSummary(QObject):
    """
    Summarize the fault state of a single fast fault.

    This is a combination of the OK signal and the IN_USE signal.
    A signal is faulting if it is "IN_USE" but "NOT OK".

    This is important because all faults that are "NOT IN_USE" are also
    "NOT OK" by default, creating a lot of false positives for the fault
    counter if we neglect to consider the IN_USE signal.

    Parameters
    ----------
    ok_address : str
        The PyDM channel associated with the "OK" fault signal, which is
        1 when the condition is OK and 0 when we are faulting.
    in_use_address : str
        The PyDM channel associated with the "IN_USE" fault signal,
        which is 1 when the fault's OK state is valid and is 0 when the
        fault's OK state is invalid.
    dest_address : str
        The PyDM channel that our values should be output to.
        This channel address can then be re-used for other PyDMChannel
        instances that are expecting values.
    parent : QObject, optional
        Standard qt parent argument. If provided, it makes this object
        a child object of the parent.
    """
    value_sig = Signal(int)
    is_ok: int
    is_in_use: int

    def __init__(
        self,
        ok_address: str,
        in_use_address: str,
        dest_address: str,
        parent: QObject | None,
    ):
        super().__init__(parent=parent)
        self.ok_address = ok_address
        self.in_use_address = in_use_address
        self.dest_address = dest_address
        self.is_ok = 0
        self.is_in_use = 0

    def create_channels(self) -> tuple[PyDMChannel, PyDMChannel, PyDMChannel]:
        """
        Create and return the channels associated with the fault summary.

        The first channel is the intake channel for the OK signal.
        The second channel is the intake channel for the IN_USE signal.
        The third channel is the output channel for the fault state.

        You should connect the output channel first, so that it is ready
        to consume the outputs of the intake channels.
        """
        return PyDMChannel(
            address=self.ok_address,
            value_slot=self.new_ok,
        ), PyDMChannel(
            address=self.in_use_address,
            value_slot=self.new_in_use,
        ), PyDMChannel(
            address=self.dest_address,
            value_signal=self.value_sig,
            value_slot=show_loc_connected,
        )

    def new_ok(self, value: int):
        """
        When we recieve a new value from the OK signal, stash and update.
        """
        self.is_ok = value
        self.new_fault()

    def new_in_use(self, value: int):
        """
        When we recieve a new value from the IN_USE signal, stash and update.
        """
        self.is_in_use = value
        self.new_fault()

    def new_fault(self):
        """
        Update consumers of value_sig with the current fault state.
        """
        if self.is_in_use:
            self.value_sig.emit(1 - self.is_ok)
        else:
            self.value_sig.emit(0)


def show_loc_connected(*args, **kwargs):
    """
    No-op slot to put on loc:// channels so that they show as connected.

    Otherwise, they can show as disconnected even if the value updates
    properly.
    """
    ...
