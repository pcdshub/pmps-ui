from typing import Iterable

import prettytable

from beamclass_table import bc_header, bc_table


def preformatted(text: str) -> str:
    """Return a rich text preformatted version of input."""
    return f'<pre>{text}</pre>'


def get_ev_range_tooltip(bitmask: int, range_def: Iterable[int]) -> str:
    """Return a suitable tooltip for an eV range bitmask."""
    ok_bounds = []
    bad_bounds = []
    curr_ok_bound = None
    curr_bad_bound = None
    prev = 0

    for bit, ev in enumerate(range_def):
        ok = (bitmask >> bit) % 2
        if ok:
            if curr_ok_bound is None:
                curr_ok_bound = (prev, ev)
            else:
                curr_ok_bound = (curr_ok_bound[0], ev)
            if curr_bad_bound is not None:
                bad_bounds.append(curr_bad_bound)
                curr_bad_bound = None
        else:
            if curr_bad_bound is None:
                curr_bad_bound = (prev, ev)
            else:
                curr_bad_bound = (curr_bad_bound[0], ev)
            if curr_ok_bound is not None:
                ok_bounds.append(curr_ok_bound)
                curr_ok_bound = None
        prev = ev

    if curr_ok_bound is not None:
        ok_bounds.append(curr_ok_bound)
    if curr_bad_bound is not None:
        bad_bounds.append(curr_bad_bound)

    left_width = 0
    right_width = 0
    lines = []
    if not bad_bounds or len(ok_bounds) < len(bad_bounds):
        for left, right in ok_bounds:
            left_width = max(left_width, len(str(left)))
            right_width = max(right_width, len(str(right)))
        for under, over in ok_bounds:
            line = f'Allow {under:{left_width}}eV &lt; energy &lt; {over:{right_width}}eV'
            lines.append(line)
    else:
        for left, right in bad_bounds:
            left_width = max(left_width, len(str(left)))
            right_width = max(right_width, len(str(right)))
        for under, over in bad_bounds:
            line = f'Block {under:{left_width}}eV &lt; energy &lt; {over:{right_width}}eV'
            lines.append(line)
    return preformatted('\n'.join(lines))


def get_tooltip_for_bc(beamclass: int) -> str:
    """
    Create a mini 2-row table suitable for a beam class tooltip.
    """
    table = prettytable.PrettyTable()
    table.field_names = bc_header
    table.add_row(bc_table[beamclass])
    return preformatted(str(table))


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
    return preformatted(str(table))
