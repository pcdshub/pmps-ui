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
        if self.plc_status_ch:
            self.destroyed.connect(functools.partial(clear_channel, self.plc_status_ch))

    def setup_ui(self):
        self.setup_plc_ioc_status()

    def setup_plc_ioc_status(self):
        ffs = self.config.get('fastfaults')
        if not ffs:
            return
        if self.plc_ioc_container is None:
            return

        for ff in ffs:
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

            widget = QtWidgets.QWidget()
            widget_layout = QtWidgets.QHBoxLayout()

            # this is the same width as the labels in the plc_ioc_header
            max_width = 150
            min_width = 130
            widget_list = [label_name, label_online, label_in_use,
                           label_alarmed, label_heartbeat,
                           label_plc_task_info_1, label_plc_task_info_2,
                           label_plc_task_info_3, plc_status_indicator]
            widget.setLayout(widget_layout)

            # set minimum height of the widget
            widget.setMinimumHeight(40)
            self.setup_widget_size(max_width=max_width, min_width=min_width,
                                   widget_list=widget_list)
            widget.layout().addWidget(label_name)
            widget.layout().addWidget(label_online)
            widget.layout().addWidget(label_in_use)
            widget.layout().addWidget(label_alarmed)
            widget.layout().addWidget(label_heartbeat)
            widget.layout().addWidget(label_plc_task_info_1)
            widget.layout().addWidget(label_plc_task_info_2)
            widget.layout().addWidget(label_plc_task_info_3)
            widget.layout().addWidget(plc_status_indicator)

            self.plc_ioc_container.layout().addWidget(widget)
            vertical_spacer = (
                QtWidgets.QSpacerItem(20, 20,
                                      QtWidgets.QSizePolicy.Preferred,
                                      QtWidgets.QSizePolicy.Maximum))
            self.plc_ioc_container.layout().addItem(vertical_spacer)
        b_vertical_spacer = (
            QtWidgets.QSpacerItem(20, 20,
                                  QtWidgets.QSizePolicy.Preferred,
                                  QtWidgets.QSizePolicy.Expanding))
        self.plc_ioc_container.layout().addItem(b_vertical_spacer)
        self.plc_ioc_container.setSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                             QtWidgets.QSizePolicy.Preferred)

    def setup_widget_size(self, max_width, min_width, widget_list):
        for widget in widget_list:
            widget.setMinimumWidth(min_width)
            widget.setMaximumWidth(max_width)

    def plc_cycle_count_severity_changed(self, key, alarm):
        """
        Process PLC Cycle Count PV severity change.

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
