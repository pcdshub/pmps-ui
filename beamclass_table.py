import prettytable
from pydm import Display
from qtpy.QtWidgets import QLabel, QTableWidgetItem


class BeamclassTable(Display):
    """
    The Display that handles the beamclass table tab.

    This is a static, informative display.
    """
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.setup_ui()

    def setup_ui(self):
        """Do all steps to prepare the inner workings of the display."""
        self.ui.table.setColumnCount(len(bc_header))
        self.ui.table.setRowCount(len(bc_table))
        self.ui.table.setHorizontalHeaderLabels(bc_header)
        for row_index, row_list in enumerate(bc_table):
            for col_index, text in enumerate(row_list):
                self.ui.table.setItem(
                    row_index,
                    col_index,
                    QTableWidgetItem(text),
                )
        self.ui.table.resizeColumnsToContents()

    def ui_filename(self):
        return 'beamclass_table.ui'


# Copied from https://confluence.slac.stanford.edu/pages/viewpage.action?pageId=341246543 and tweaked
bc_header = """
Index	Display Name	∆T (s)	dt (s)	Q (pC)	Rate max (Hz)	Current (nA)	Power @ 4 GeV (W)	Int. Energy @ 4 GeV (J)	Notes
""".strip().split('\t')
bc_table = """
0	Beam Off	0.5	-	0	0	0	0	0	Beam off, Kickers off
1	Kicker STBY	0.5	-	0	0	0	0	0	Beam off, Kickers standby
2	BC1Hz	1	1	350	1	0.35	1.4	1.4	350 pC x 1 Hz
3	BC10Hz	1	0.1	3500	10	3.5	14	14	350 pC X 10 Hz
4	Diagnostic	0.5	-	5000	-	10	40	20	50 pC x 200 Hz
5	BC120Hz	0.2	0.0083	6000	120	30	120	24	250 pC x 120 Hz
6	Tuning	0.2	-	7000	-	35	140	28	100 pC X 350 Hz
7	1% MAP	0.01	-	3000	-	300	1200	12	100 pC X 3 kHz
8	5% MAP	0.003	-	4500	-	1500	6000	18	100 pC x 15 kHz
9	10% MAP	0.001	-	3000	-	3000	12000	12	100 pC X 30 kHz
10	25% MAP	4e-4	-	3000	-	7500	30000	12	100 pC x 75 kHz
11	50% MAP	2e-1	-	3000	-	15000	60000	12	100 pC x 150 kHz
12	100% MAP	2e-4	-	6000	-	30000	120000	24	100 pC x 300 kHz
13	Unlimited	-	-	-	-	-	-	-	-
14	Spare	-	-	-	-	-	-	-	-
15	Spare	-	-	-	-	-	-	-	-
""".strip().split('\n')
for index, row in enumerate(bc_table):
    bc_table[index] = row.split('\t')


def get_full_bc_table() -> str:
    """
    Show the full table
    """
    table = prettytable.PrettyTable()
    table.field_names = bc_header
    for row in bc_table:
        table.add_row(row)
    return str(table)


def get_tooltip_for_bc(beamclass: int) -> str:
    """
    Create a mini 2-row table suitable for a beam class tooltip.
    """
    table = prettytable.PrettyTable()
    table.field_names = bc_header
    table.add_row(bc_table[beamclass])
    return '<pre>' + str(table) + '</pre>'


def get_tooltip_for_bc_bitmask(bitmask: int) -> str:
    """
    Create a partial table suitable for a bitmask tooltip.
    """
    table = prettytable.PrettyTable()
    table.field_names = bc_header
    table.add_row(bc_table[0])
    count = 0
    while bitmask > 0:
        count += 1
        if bitmask % 2:
            table.add_row(bc_table[count])
        bitmask = bitmask >> 1
    return '<pre>' + str(table) + '</pre>'


def get_desc_for_bc(beamclass: int) -> str:
    """
    Get just the short description of a beamclass.
    """
    return bc_table[beamclass][1]


def install_bc_setText(widget: QLabel):
    """
    Replace QLabel.setText to get the description too.

    Without this, the labels display:
    13
    With this, you get:
    13: Unlimited
    """
    def bc_setText(text: str) -> None:
        try:
            text = f'{text}: {get_desc_for_bc(int(text))}'
        except Exception:
            pass
        return widget._original_setText(text)

    widget._original_setText = widget.setText
    widget.setText = bc_setText


def get_max_bc_from_bitmask(bitmask: int) -> int:
    """
    Given a beamclass bitmask, get the highest non-spare beamclass.
    """
    max_bc = 0
    while bitmask > 0:
        bitmask = bitmask >> 1
        max_bc += 1
    while bc_table[max_bc][1] == 'Spare':
        max_bc -= 1
    return max_bc
