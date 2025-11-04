122 mnt_remove_lbp_override
###########################

API Breaks
----------
- N/A

Features
--------
- Update pmps-ui to reflect the "final" design of the beam power overrides
  (final through end of 2025).
- Remove all special judgement factor handling from the line beam parameters tab.
  In the next update, the line beam parameters will be applied after the override,
  not before it, so these inversions are no longer correct.
- Update the verbiage and layout on the beam power override tab to reflect that
  the beamclass override is returning and that there are no longer complications
  with the line beam parameters tab.
- Clean up beam power override formulas to be more readable.

Bugfixes
--------
- N/A

Maintenance
-----------
- Update the LFE and KFE configs to match the live configurations in dev.

Contributors
------------
- zllentz
