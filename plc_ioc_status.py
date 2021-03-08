import functools
import itertools
from string import Template

from pydm import Display
from qtpy import QtWidgets
from pydm.widgets.channel import PyDMChannel
from pydm.widgets import PyDMByteIndicator, PyDMLabel


class PLCIOCStatus(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super(PLCIOCStatus, self).__init__(
            parent=parent, args=args, macros=macros)
        self.config = macros
        self.ffs_count_map = {}
        self.ffs_label_map = {}
        self.setup_ui()

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
            heart_ch = Template(
                'ca://${P}HEARTBEAT').safe_substitute(**plc_macros)
            # serv_record = Template(
            #   'ca://${P}HEARTBEAT.SERV').safe_substitute(**plc_macros)

            label_name = QtWidgets.QLabel(str(plc_name))
            label_online = QtWidgets.QLabel()
            label_in_use = QtWidgets.QLabel()
            label_alarmed = QtWidgets.QLabel()
            label_heartbeat = PyDMLabel(init_channel=heart_ch)
            # label_ioc_status = PyDMLabel(init_channel=serv_record)

            # if we can get the heartbeat the IOC should be ON, if not OFF
            # if we get the heartbeat and the .SERV is invalid, the PLC is OFF
            ioc_status_indicator = PyDMByteIndicator()
            ioc_status_indicator.circles = True
            ioc_status_indicator.showLabels = False
            plc_status_indicator = PyDMByteIndicator()
            plc_status_indicator.circles = True
            plc_status_indicator.showLabels = False

            # total initial number of ffs to initialize the dictionaries with
            # num_ffo * num_ff
            all_ffos = ((ffo_end - ffo_start) + 1) * (ff_end - ff_start + 1)
            self.ffs_count_map[plc_name] = {'online': [False]*all_ffos,
                                            'in_use': [False]*all_ffos,
                                            'alarmed': [False]*all_ffos}
            self.ffs_label_map[plc_name] = {'online': label_online,
                                            'in_use': label_in_use,
                                            'alarmed': label_alarmed}

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
                # TODO: do i need to disconnect somewhere too?
                channel.connect()
                count += 1

            widget = QtWidgets.QWidget()
            widget_layout = QtWidgets.QHBoxLayout()

            widget.setLayout(widget_layout)
            widget.layout().addWidget(label_name)
            widget.layout().addWidget(label_online)
            widget.layout().addWidget(label_in_use)
            widget.layout().addWidget(label_alarmed)
            widget.layout().addWidget(label_heartbeat)
            widget.layout().addWidget(ioc_status_indicator)
            widget.layout().addWidget(plc_status_indicator)

            self.plc_ioc_container.layout().addWidget(widget)
        vertical_spacer = (
            QtWidgets.QSpacerItem(20, 40,
                                  QtWidgets.QSizePolicy.Preferred,
                                  QtWidgets.QSizePolicy.MinimumExpanding))
        self.plc_ioc_container.layout().addItem(vertical_spacer)

    def ffo_connection_callback(self, key, idx, conn):
        # Update ffos count dictionary information
        plc = self.ffs_count_map.get(key)
        plc['online'][idx] = conn
        plc['in_use'][idx] = conn
        # Call routine to update proper label
        self.update_plc_labels(key)

    def ffo_value_changed(self, key, idx, conn):
        plc = self.ffs_count_map.get(key)
        plc['in_use'][idx] = conn
        self.update_plc_labels(key)

    def ffo_severity_changed(self, key, idx, conn):
        plc = self.ffs_count_map.get(key)
        plc['alarmed'][idx] = conn
        self.update_plc_labels(key)

    def update_plc_labels(self, key):
        # Fetch value from count
        counts = self.ffs_count_map.get(key)
        if counts:
            online_cnt = sum(counts['online'])
            in_use_cnt = sum(counts['in_use'])
            alarmed_cnt = sum(counts['alarmed'])
        # Pick the label from the map
        # Update label with new count
        labels = self.ffs_label_map.get(key)
        if labels:
            labels['online'].setText(str(online_cnt))
            labels['in_use'].setText(str(in_use_cnt))
            labels['alarmed'].setText(str(alarmed_cnt))

    def ui_filename(self):
        return 'plc_ioc_status.ui'
