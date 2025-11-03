import textwrap

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
        for col_index, description in enumerate(bc_header_full_descriptions):
            self.ui.table.horizontalHeaderItem(col_index).setToolTip(
                textwrap.fill(
                    description,
                    width=40,
                )
            )
        for row_index, row_list in enumerate(bc_table):
            for col_index, text in enumerate(row_list):
                self.ui.table.setItem(
                    row_index,
                    col_index,
                    QTableWidgetItem(text),
                )
        self.ui.table.resizeColumnsToContents()
        self.ui.table.setFixedSize(
            self.ui.table.horizontalHeader().length()
            + self.ui.table.verticalHeader().width(),
            self.ui.table.verticalHeader().length()
            + self.ui.table.horizontalHeader().height(),
        )
        self.ui.source_links_text.setFixedWidth(self.ui.table.width())

    def ui_filename(self):
        return 'ui/beamclass_table.ui'


# Copied from https://confluence.slac.stanford.edu/pages/viewpage.action?pageId=341246543 and tweaked
bc_header = """
Index	Display Name	∆T (s)	dt (s)	Q (pC)	Rate max (Hz)	Current (nA)	Power @ 4 GeV (W)	Int. Energy @ 4 GeV (J)	Notes
""".strip().split('\t')
bc_table = """
0	Beam Off	0.5	-	0	0	0	0	0	Beam off, Kickers off
1	Kicker STBY	0.5	-	0	0	0	0	0	Beam off, Kickers standby
2	BC1Hz	1	1	350	1	0.35	1.4	1.4	350 pC x 1 Hz
3	BC10Hz	1	0.1	3500	10	3.5	14	14	350 pC X 10 Hz
4	BC120Hz	0.2	0.0083	2000	120	10	40	8	83 pC x 120 Hz
5	Diagnostic	0.2	-	3000	-	15	60	12	150 pC x 100 Hz
6	Tuning	0.2	-	7000	-	35	140	28	100 pC X 350 Hz
7	1% MAP	0.01	-	3000	-	300	1200	12	100 pC X 3 kHz
8	5% MAP	0.003	-	4500	-	1500	6000	18	100 pC x 15 kHz
9	10% MAP	0.001	-	3000	-	3000	12000	12	100 pC X 30 kHz
10	25% MAP	4e-4	-	3000	-	7500	30000	12	100 pC x 75 kHz
11	50% MAP	2e-1	-	3000	-	15000	60000	12	100 pC x 150 kHz
12	100% MAP	2e-4	-	6000	-	30000	120000	24	100 pC x 300 kHz
13	Unlimited	-	-	-	-	-	-	-	-
14	Unlimited	-	-	-	-	-	-	-	-
15	Unlimited	-	-	-	-	-	-	-	-
""".strip().split('\n')
for index, row in enumerate(bc_table):
    bc_table[index] = row.split('\t')


bc_header_full_descriptions = [
    (
        'Index is the beamclass number. '
        'When we say "beamclass 10", we are referring to index 10 on this table.'
    ),
    (
        'Display name is a short, human-readable name '
        'that is a minimal description of how the beamclass behaves.'
    ),
    (
        '∆T (s) is the integration time window used for the Q (pC) charge measurement. '
        'A beamclass limits the amount of integrated electron charge during a time interval.'
    ),
    (
        'dt (s) is the the minimum bunch spacing (including non-periodic bunch patterns). '
        'When included, this effectively limits the rep rate of the beam for periodic bunch patterns. '
        'When omitted, any rep rate could be allowed if it passes the integrated electron charge measurement.'
    ),
    (
        'Q (pC) is the the maximum beam charge integrated in ∆T (s). '
        'A beamclass limits the amount of integrated electron charge during a time interval.'
    ),
    (
        'Rate max (Hz) is a field calculated from dt (s) if present '
        'and is the effective rep rate limit of the beam.'
    ),
    (
        'Current (nA) is a calculated field and is the equivalent '
        'maximum electron beam current at the beamclass.'
    ),
    (
        'Power @ 4 GeV (W) is a calculated field and is the equivalent '
        'maximum electron beam wattage at 4 GeV at the beamclass.'
    ),
    (
        'Int. Energy @ 4 GeV (J) is a calculated field and is the equivalent '
        'maximum integrated electron energy at 4 GeV during the ∆T (s) integration window.'
    ),
    (
        'Notes is an advisory field that gives an example of '
        'what this beam class might look like at a particular bunch charge or rep rate.'
    ),
]


def get_table_row(row: int) -> list[str]:
    """
    Grab a row from the table, or invalid if out of range.
    """
    try:
        return bc_table[row]
    except IndexError:
        return [row, 'Invalid'] + (['?'] * 8)


def get_desc_for_bc(beamclass: int) -> str:
    """
    Get just the short description of a beamclass.
    """
    return get_table_row(beamclass)[1]


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
    Given a beamclass bitmask, get the highest beamclass.
    """
    max_bc = 0
    while bitmask > 0:
        bitmask = bitmask >> 1
        max_bc += 1
    return max_bc
