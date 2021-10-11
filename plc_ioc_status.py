import functools
import itertools
from string import Template

from pydm import Display
from pydm.widgets import PyDMLabel
from pydm.widgets.byte import PyDMBitIndicator
from pydm.widgets.channel import PyDMChannel
from qtpy import QtWidgets
from qtpy.QtGui import QColor

from fast_faults import clear_channel


class PLCIOCStatus(Display):
    _on_color = QColor(0, 255, 0)
    _off_color = QColor(100, 100, 100)
    plc_status_ch = None

    def __init__(self, parent=None, args=None, macros=None):
        super(PLCIOCStatus, self).__init__(
            parent=parent, args=args, macros=macros)
        self.config = macros
        self.ffs_count_map = {}
        self.ffs_label_map = {}
        self.setup_ui()
        for ch in (
            self.plc_status_ch,
            self.plc_task1_vis_ch,
            self.plc_task2_vis_ch,
            self.plc_task3_vis_ch,
        ):
            self.destroyed.connect(functools.partial(clear_channel, ch))

    def setup_ui(self):
        self.setup_plc_ioc_status()

    def setup_plc_ioc_status(self):
        ffs = self.config.get('fastfaults')
        if not ffs:
            return
        if self.plc_ioc_container is None:
            return

        grid = self.ui.plc_ioc_container.layout()
        self.task_vis_data = {}

        for row, ff in enumerate(ffs):
            prefix = ff.get('prefix')
            ffo_start = ff.get('ffo_start')
            ffo_end = ff.get('ffo_end')
            ff_start = ff.get('ff_start')
            ff_end = ff.get('ff_end')

            ffos_zfill = len(str(ffo_end)) + 1
            ffs_zfill = len(str(ff_end)) + 1
            entries = itertools.product(
                range(ffo_start, ffo_end + 1),
                range(ff_start, ff_end + 1)
            )

            plc_name = prefix.strip(':')
            plc_macros = dict(P=prefix)
            # get the heartbeat of the IOC to
            ico_heart_ch = Template(
                'ca://${P}HEARTBEAT').safe_substitute(**plc_macros)
            # the get PLC process cycle count
            plc_task_info_1 = Template(
               'ca://${P}TaskInfo:1:CycleCount').safe_substitute(**plc_macros)
            plc_task_info_2 = Template(
               'ca://${P}TaskInfo:2:CycleCount').safe_substitute(**plc_macros)
            plc_task_info_3 = Template(
                'ca://${P}TaskInfo:3:CycleCount').safe_substitute(**plc_macros)

            label_name = QtWidgets.QLabel(str(plc_name))
            label_online = QtWidgets.QLabel()
            label_in_use = QtWidgets.QLabel()
            label_alarmed = QtWidgets.QLabel()
            label_heartbeat = PyDMLabel(init_channel=ico_heart_ch)
            label_plc_task_info_1 = PyDMLabel(init_channel=plc_task_info_1)
            label_plc_task_info_2 = PyDMLabel(init_channel=plc_task_info_2)
            label_plc_task_info_3 = PyDMLabel(init_channel=plc_task_info_3)

            # if alarm of plc_task_info_1 == INVALID => plc down
            # if the count does not update and alarm == NO_ALARM =>
            # plc online but stopped
            self.plc_status_ch = PyDMChannel(
                    plc_task_info_1,
                    severity_slot=functools.partial(
                        self.plc_cycle_count_severity_changed, plc_name))
            self.plc_status_ch.connect()

            # if we can get the plc_cycle_count the PLC should be ON, if not OFF
            # if we get the plc_cycle_count and the .SERV is INVALID, the PLC is OFF
            plc_status_indicator = PyDMBitIndicator(circle=True)
            plc_status_indicator.setColor(self._off_color)
            # TODO - maybe add the case where PLC On but stopped

            # Handle the visibility of task 2 and 3 info
            # Not every PLC has tasks 2 and 3
            # These should be shown if they are valid or if they are nonzero
            # These should be hidden if they are both 0 and invalid while
            # task1 is still valid
            # If task1 is invalid display all 3 (val of task1 irrelevant)
            # I need to collect/cache a value and then show/hide appropriately
            self.task_vis_data[plc_name] = {
                'task1': {
                    'value': 0,
                    'sevr': 3,
                },
                'task2': {
                    'value': 0,
                    'sevr': 3,
                },
                'task3': {
                    'value': 0,
                    'sevr': 3,
                },
            }
            self.plc_task1_vis_ch = PyDMChannel(
                plc_task_info_1,
                severity_slot=functools.partial(
                    self.update_task_visibility,
                    plc_name=plc_name,
                    task='task1',
                    value_type='sevr',
                    widget=None,
                ),
            )
            self.plc_task1_vis_ch.connect()
            self.plc_task2_vis_ch = PyDMChannel(
                plc_task_info_2,
                value_slot=functools.partial(
                    self.update_task_visibility,
                    plc_name=plc_name,
                    task='task2',
                    value_type='value',
                    widget=label_plc_task_info_2,
                ),
                severity_slot=functools.partial(
                    self.update_task_visibility,
                    plc_name=plc_name,
                    task='task2',
                    value_type='sevr',
                    widget=label_plc_task_info_2,
                ),
            )
            self.plc_task2_vis_ch.connect()
            self.plc_task3_vis_ch = PyDMChannel(
                plc_task_info_3,
                value_slot=functools.partial(
                    self.update_task_visibility,
                    plc_name=plc_name,
                    task='task3',
                    value_type='value',
                    widget=label_plc_task_info_3,
                ),
                severity_slot=functools.partial(
                    self.update_task_visibility,
                    plc_name=plc_name,
                    task='task3',
                    value_type='sevr',
                    widget=label_plc_task_info_3,
                ),
            )
            self.plc_task3_vis_ch.connect()

            # total initial number of ffs to initialize the dictionaries with
            # num_ffo * num_ff
            all_ffos = ((ffo_end - ffo_start) + 1) * (ff_end - ff_start + 1)
            self.ffs_count_map[plc_name] = {'online': [False]*all_ffos,
                                            'in_use': [False]*all_ffos,
                                            'alarmed': [False]*all_ffos,
                                            'plc_status': False}
            self.ffs_label_map[plc_name] = {'online': label_online,
                                            'in_use': label_in_use,
                                            'alarmed': label_alarmed,
                                            'plc_status': plc_status_indicator}

            count = 0
            for _ffo, _ff in entries:
                s_ffo = str(_ffo).zfill(ffos_zfill)
                s_ff = str(_ff).zfill(ffs_zfill)
                ch_macros = dict(index=count, P=prefix, FFO=s_ffo, FF=s_ff)

                ch = Template(
                    'ca://${P}FFO:${FFO}:FF:${FF}:Info:InUse_RBV').safe_substitute(**ch_macros)
                channel = PyDMChannel(
                    ch,
                    connection_slot=functools.partial(
                        self.ffo_connection_callback, plc_name, count),
                    value_slot=functools.partial(
                        self.ffo_value_changed, plc_name, count),
                    severity_slot=functools.partial(
                        self.ffo_severity_changed, plc_name, count))
                # should not be adding a new connection because this address
                # already exists in the connections,
                # instead should just add a listener
                channel.connect()
                count += 1

            # this is the same width as the labels in the plc_ioc_header
            max_width = 150
            min_width = 130
            max_height = 30
            min_height = 30
            widget_list = [label_name, label_online, label_in_use,
                           label_alarmed, label_heartbeat,
                           label_plc_task_info_1, label_plc_task_info_2,
                           label_plc_task_info_3, plc_status_indicator]

            self.setup_widget_size(
                max_width=max_width,
                min_width=min_width,
                max_height=max_height,
                min_height=min_height,
                widget_list=widget_list,
            )

            grid.addWidget(label_name, row, 0)
            grid.addWidget(label_online, row, 1)
            grid.addWidget(label_in_use, row, 2)
            grid.addWidget(label_alarmed, row, 3)
            grid.addWidget(label_heartbeat, row, 4)
            grid.addWidget(label_plc_task_info_1, row, 5)
            grid.addWidget(label_plc_task_info_2, row, 6)
            grid.addWidget(label_plc_task_info_3, row, 7)
            grid.addWidget(plc_status_indicator, row, 8)

        b_vertical_spacer = (
            QtWidgets.QSpacerItem(20, 20,
                                  QtWidgets.QSizePolicy.Preferred,
                                  QtWidgets.QSizePolicy.Expanding))
        grid.addItem(b_vertical_spacer, row + 1, 0)
        self.plc_ioc_container.setSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                             QtWidgets.QSizePolicy.Preferred)

    def setup_widget_size(self,
        max_width,
        min_width,
        max_height,
        min_height,
        widget_list,
    ):
        for widget in widget_list:
            widget.setMinimumWidth(min_width)
            widget.setMaximumWidth(max_width)
            widget.setMinimumHeight(min_height)
            widget.setMaximumHeight(max_height)

    def plc_cycle_count_severity_changed(self, key, alarm):
        """
        Process PLC Cycle Count PV severity change.

        This targets only the first cycle counter. When the first
        cycle counter goes "Invalid", mark PLC status as bad.
        Otherwise, PLC status is good.

        Parameters
        ----------
        key : str
            Prefix of PLC
        alarm : int
            New alarm.

        Note
        ----
        alarm == 0 => NO_ALARM, if NO_ALARM and counter does not change,
        PLC is till online but stopped
        alarm == 3 => INVALID - PLC is Offline
        """
        plc = self.ffs_count_map.get(key)
        if alarm == 3:
            plc['plc_status'] = False
        else:
            plc['plc_status'] = True
        self.update_status_labels(key)

    def update_task_visibility(
        self,
        value,
        plc_name,
        task,
        value_type,
        widget,
    ):
        """
        Check if tasks 2 or 3 are valid to be shown.

        The goal is that we shouldn't show invalid channels unless
        they are true errors. The conditions for a non-error
        expected "bad" state on counts 2 or 3 are:

        - Task count 1 is valid
        - Task counts 2 or 3 are 0 and invalid

        Task 1 being invalid is always a bad state.
        Task 2 or 3 being nonzero and invalid is also a bad state.
        These usually means the PLC has crashed.
        """
        plc_data = self.task_vis_data[plc_name]
        task_data = plc_data[task]
        task_data[value_type] = value
        if widget is None:
            return
        if all((
            plc_data['task1']['sevr'] == 0,
            task_data['value'] == 0,
            task_data['sevr'] == 3,
        )):
            widget.hide()
        else:
            widget.show()

    def ffo_connection_callback(self, key, idx, conn):
        # Update ffos count for connected In_Use PVs
        plc = self.ffs_count_map.get(key)
        plc['online'][idx] = conn
        # Call routine to update proper label
        self.update_plc_labels(key)

    def ffo_value_changed(self, key, idx, value):
        # Update ffos count for In_Use == True Pvs
        plc = self.ffs_count_map.get(key)
        plc['in_use'][idx] = value
        self.update_plc_labels(key)

    def ffo_severity_changed(self, key, idx, alarm):
        # 0 = NO_ALARM, 1 = MINOR, 2 = MAJOR, 3 = INVALID
        plc = self.ffs_count_map.get(key)
        if alarm != 0:
            plc['alarmed'][idx] = True
        else:
            plc['alarmed'][idx] = False
        self.update_plc_labels(key)

    def update_plc_labels(self, key):
        # Fetch value from count
        # TODO maybe have some checks here....?
        counts = self.ffs_count_map.get(key)
        online_cnt = sum(counts['online'])
        in_use_cnt = sum(counts['in_use'])
        alarmed_cnt = sum(counts['alarmed'])
        # Pick the label from the map
        # Update label with new count
        labels = self.ffs_label_map.get(key)
        labels['online'].setText(str(online_cnt))
        labels['in_use'].setText(str(in_use_cnt))
        labels['alarmed'].setText(str(alarmed_cnt))

    def update_status_labels(self, key):
        status = self.ffs_count_map.get(key)
        plc_status = status['plc_status']
        labels = self.ffs_label_map.get(key)
        if plc_status is True:
            labels['plc_status'].setColor(self._on_color)
        else:
            labels['plc_status'].setColor(self._off_color)

    def ui_filename(self):
        return 'plc_ioc_status.ui'
