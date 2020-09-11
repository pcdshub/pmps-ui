import functools
import weakref

from qtpy import QtCore, QtGui, QtWidgets
from pydm.widgets.base import PyDMPrimitiveWidget, widget_destroyed
from pydm.widgets.channel import PyDMChannel
from pydm.widgets.label import PyDMLabel


class UndulatorWidget(QtWidgets.QWidget, PyDMPrimitiveWidget):
    CHANNELS = dict(
        seed_number='ca://{prefix}PE:UND:SeedUndulatorNumber_RBV',
        # upper_k='ca://{prefix}PE:UND:HiK_RBV', # Commented out. Requested to move to hardcoded value
        # lower_k='ca://{prefix}PE:UND:LowK_RBV', # Commented out. Requested to move to hardcoded value
        active='ca://{prefix}PE:UND:{segment}:Active_RBV',
        curr_k='ca://{prefix}PE:UND:{segment}:KAct_RBV',
        target_k='ca://{prefix}PE:UND:{segment}:KDes_RBV',
        severity='ca://{prefix}PE:UND:{segment}:KDesValid_RBV'
    )

    BASE_BRUSH = QtGui.QBrush(QtGui.QColor('white'), QtCore.Qt.SolidPattern)
    BASE_PEN = QtGui.QPen(QtCore.Qt.SolidLine)
    BASE_PEN.setColor(QtGui.QColor('black'))
    BASE_PEN.setWidth(1)

    INACTIVE_BRUSH = QtGui.QBrush(
        QtGui.QColor(148, 148, 148),
        QtCore.Qt.SolidPattern
    )
    NORMAL_BRUSH = QtGui.QBrush(
        QtGui.QColor(18, 158, 236),
        QtCore.Qt.SolidPattern
    )
    SEED_BRUSH = QtGui.QBrush(
        QtGui.QColor(241, 139, 69),
        QtCore.Qt.SolidPattern
    )
    BROKEN_BRUSH = QtGui.QBrush(
        QtGui.QColor(106, 45, 152),
        QtCore.Qt.DiagCrossPattern
    )

    def __init__(self, parent=None):
        super(UndulatorWidget, self).__init__(parent=parent)
        self._prefix = None
        self._segment = None
        self._channels = dict()
        self._values = dict()
        self._connections = dict()
        self._forward_texture = None
        self._backward_texture = None
        self.destroyed.connect(
            functools.partial(widget_destroyed, self.channels,
                              weakref.ref(self))
        )

    @QtCore.Property(str)
    def prefix(self):
        return self._prefix

    @prefix.setter
    def prefix(self, value):
        if self._prefix == value:
            return
        self._prefix = value
        self._setup_channels()

    @QtCore.Property(int)
    def segment(self):
        return self._segment

    @segment.setter
    def segment(self, value):
        if self._segment == value:
            return
        self._segment = value
        self._setup_channels()

    def minimumSizeHint(self):
        return QtCore.QSize(100, 32)

    def value_cb(self, entry, value):
        self._values[entry] = value
        if self.connected():
            self.update()

    def conn_cb(self, entry, connected):
        self._connections[entry] = connected
        if self.connected():
            self.update()

    def connected(self):
        if not len(self._connections):
            return False
        return all(self._connections.values())

    def is_seed(self):
        return self._segment == self._values.get('seed_number')

    def _setup_channels(self):
        if not self._prefix or not self._segment:
            return

        for entry, pv_format in UndulatorWidget.CHANNELS.items():
            pv = pv_format.format(prefix=self.prefix, segment=self.segment)
            conn_cb = functools.partial(self.conn_cb, entry)
            val_cb = functools.partial(self.value_cb, entry)
            ch = PyDMChannel(pv, value_slot=val_cb, connection_slot=conn_cb)
            self._channels[entry] = ch
            self._values[entry] = None
            self._connections[entry] = False

        for _, ch in self._channels.items():
            ch.connect()

    def channels(self):
        return [ch for ch in self._channels.values()]

    def _create_textures(self, backwards=False):
        size = max(self.height() / 10.0, 10)
        _texture = QtGui.QPixmap(QtCore.QSize(size, size))
        _texture.fill(QtGui.QColor("transparent"))

        pen = QtGui.QPen(QtCore.Qt.SolidLine)
        pen.setStyle(QtCore.Qt.SolidLine)
        pen.setWidth(1)

        zero = size * 0.1
        size = size - 2 * zero

        if backwards:
            pen.setColor(QtGui.QColor('white'))
            path = QtGui.QPainterPath(QtCore.QPointF(size, zero))
            path.lineTo(zero, size / 2.0)
            path.lineTo(size, size)
        else:
            pen.setColor(QtGui.QColor(57, 178, 239, 255))
            path = QtGui.QPainterPath(QtCore.QPointF(zero, zero))
            path.lineTo(size, size / 2.0)
            path.lineTo(zero, size)

        painter = QtGui.QPainter(_texture)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.end()

        return _texture

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        opt = QtWidgets.QStyleOption()
        opt.initFrom(self)
        self.style().drawPrimitive(QtWidgets.QStyle.PE_Widget, opt, painter,
                                   self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        w, h = self.width(), self.height()

        painter.setBrush(self.BASE_BRUSH)
        painter.setPen(self.BASE_PEN)
        painter.drawRect(0, 0, w, h)

        if not self.connected():
            return

        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))

        active = self._values['active']
        # upper_k = self._values['upper_k']
        # lower_k = self._values['lower_k']
        upper_k = 10.0
        lower_k = 0.0
        curr_k = self._values['curr_k']
        target_k = self._values['target_k']
        severity = self._values['severity']
        if severity == -1:
            painter.setBrush(self.BROKEN_BRUSH)
            painter.drawRect(0, 0, w, h)
            return
        curr_k = 0 if curr_k is None else curr_k
        target_k = 0 if target_k is None else target_k

        if not active:
            d_w = self._k_to_width(curr_k, upper_k, lower_k)
            painter.setBrush(self.INACTIVE_BRUSH)
            painter.drawRect(QtCore.QRectF(0.0, 0.0, d_w, h))
            return

        # Here we are active...
        # Let's decide if using the seed or normal brush for this widget
        brush = self.NORMAL_BRUSH if not self.is_seed() else self.SEED_BRUSH
        curr_w = self._k_to_width(curr_k, upper_k, lower_k)
        painter.setBrush(brush)
        painter.drawRect(QtCore.QRectF(0.0, 0.0, curr_w, h))

        if curr_k != target_k:
            rem_brush = QtGui.QBrush()
            # Set proper texture for forward/backward movement
            texture = self._create_textures(backwards=curr_k > target_k)
            rem_brush.setTexture(texture)
            target_w = self._k_to_width(target_k, upper_k, lower_k)
            rem_w = target_w - curr_w
            painter.setBrush(rem_brush)
            painter.drawRect(QtCore.QRectF(curr_w, 0.0, rem_w, h))
        painter.end()

    def _k_to_width(self, k, upper, lower):
        if not k:
            return 0
        w = self.width()
        corrected_k = k - lower
        return (w / (upper - lower)) * corrected_k


class UndulatorListWidget(QtWidgets.QWidget, PyDMPrimitiveWidget):

    def __init__(self, parent=None):
        super(UndulatorListWidget, self).__init__(parent=parent)
        self._prefix = None
        self._channels = dict()
        self._connections = dict()
        self._forward_texture = None
        self._backward_texture = None
        self._first_segment = 0
        self._last_segment = 0

        self.destroyed.connect(
            functools.partial(widget_destroyed, self.channels,
                              weakref.ref(self))
        )

        self.setLayout(QtWidgets.QVBoxLayout())
        self.scroll_area = QtWidgets.QScrollArea()
        self.layout().addWidget(self.scroll_area)
        self.widget = QtWidgets.QWidget()
        self.widget.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                  QtWidgets.QSizePolicy.Minimum)
        self.widget.setLayout(QtWidgets.QVBoxLayout())
        self.scroll_area.setWidget(self.widget)
        self.scroll_area.setWidgetResizable(True)

    @QtCore.Property(str)
    def prefix(self):
        return self._prefix

    @prefix.setter
    def prefix(self, value):
        if self._prefix == value:
            return
        self._prefix = value
        self._setup_channels()

    def value_cb(self, first_segment, value):
        if first_segment:
            self._first_segment = value
        else:
            self._last_segment = value
        if self.connected():
            self._setup_widgets()

    def conn_cb(self, entry, connected):
        self._connections[entry] = connected
        if self.connected():
            self._setup_widgets()

    def connected(self):
        if not len(self._connections):
            return False
        return all(self._connections.values())

    def _setup_channels(self):
        if not self._prefix:
            return

        pvs = {
            'first': 'ca://{prefix}PE:UND:FirstSegment_RBV',
            'last': 'ca://{prefix}PE:UND:LastSegment_RBV'
        }

        for entry, pv_format in pvs.items():
            pv = pv_format.format(prefix=self.prefix)
            conn_cb = functools.partial(self.conn_cb, entry)
            val_cb = functools.partial(self.value_cb, entry == 'first')
            ch = PyDMChannel(pv, value_slot=val_cb, connection_slot=conn_cb)
            self._channels[entry] = ch
            self._connections[entry] = False

        for _, ch in self._channels.items():
            ch.connect()

    def channels(self):
        return [ch for ch in self._channels.values()]

    def _setup_widgets(self):
        if (not self.connected() or not self._first_segment or
                not self._last_segment):
            return
        if self._first_segment > self._last_segment:
            return
        segments = range(self._first_segment, self._last_segment + 1)
        for seg in segments:
            self.widget.layout().addLayout(self._create_entry(seg))

    def _create_entry(self, segment):
        segment_label = QtWidgets.QLabel(str(segment))
        und_widget = UndulatorWidget()
        und_widget.prefix = self.prefix
        und_widget.segment = segment

        curr_pv = UndulatorWidget.CHANNELS['curr_k'].format(
            prefix=self.prefix, segment=segment
        )
        curr_label = PyDMLabel(init_channel=curr_pv)
        curr_label.setMinimumWidth(100)

        target_pv = UndulatorWidget.CHANNELS['target_k'].format(
            prefix=self.prefix, segment=segment
        )
        target_label = PyDMLabel(init_channel=target_pv)
        target_label.setMinimumWidth(100)

        k_values_layout = QtWidgets.QFormLayout()
        k_values_layout.setFormAlignment(QtCore.Qt.AlignCenter)
        k_values_layout.addRow("Current K:", curr_label)
        k_values_layout.addRow("Target K:", target_label)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(segment_label)
        layout.addWidget(und_widget)
        layout.addLayout(k_values_layout)
        layout.setStretch(0, 0)
        layout.setStretch(1, 1)
        layout.setStretch(2, 0)

        return layout
