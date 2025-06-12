19 enh_bc_override
##################

API Breaks
----------
- N/A

Features
--------
- Add a "Beam Power Override" status to the main screen area.
- Change the name of the "Transmission Override" tab to "Beam Power Override"
- Update the text in the "Beam Power Override" tab to explain the beamclass override,
  including live calculation intermediates.
- The beamclass max helpers in the "Line Beam Parameters Control" tab now compensate
  for the beamclass power override.

Bugfixes
--------
- Fix an issue where text could get squished on the "Beam Power Override" tab by
  adding a scrollbar to the explanation content area.

Maintenance
-----------
- Add a partial test helper IOC for testing.

Contributors
------------
- ZLLentz
