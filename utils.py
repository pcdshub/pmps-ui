from qtpy import QtCore, QtGui, QtWidgets


def morph_into_vertical(label: QtWidgets.QLabel):
    def minimumSizeHint(*args, **kwargs):
        s = QtWidgets.QLabel.minimumSizeHint(label)
        return QtCore.QSize(s.height(), s.width())

    def sizeHint(*args, **kwargs):
        s = QtWidgets.QLabel.sizeHint(label)
        return QtCore.QSize(s.height(), s.width())

    def paintEvent(*args, **kwargs):
        painter = QtGui.QPainter(label)
        painter.translate(label.sizeHint().width(), label.sizeHint().height())
        painter.rotate(270)

        # size of text inside the label widget
        text_w = label.fontMetrics().boundingRect(label.text()).width()
        text_h = label.fontMetrics().boundingRect(label.text()).height()
        # size of label widget
        label_h = label.sizeHint().height()
        label_w = label.sizeHint().width()
        # this will make it look like it is right (or top) justified
        pos_x = label_h - text_w
        # center the text on the bitmask
        pos_y = -(label_w - text_h)
        painter.drawText(pos_x, pos_y, label.text())

    # Unbind the size restrictions from the ui file that make it viewable in designer
    label.setMaximumWidth(label.maximumHeight())

    label.minimumSizeHint = minimumSizeHint
    label.sizeHint = sizeHint
    label.paintEvent = paintEvent
    label.update()
