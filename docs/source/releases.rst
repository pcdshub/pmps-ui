Release History
###############


v2.1.0 (2025-10-16)
===================

Features
--------
- Make transmission/beamclass overrides match reality again.
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
- Adding second arbiter to lfe-motion
- Increasing the number of fast faults per ffo on lfe motion
- Include recent config updates from live directory
- Add a partial test helper IOC for testing.

Contributors
------------
- KaushikMalapati
- ZLLentz



v2.0.0 (2025-05-13)
===================

API Breaks
----------
- Delete the defunct symbolic link at the root of the repo.
  Old scripts that launch using this are encouraged to either
  swap to pmpsui/pmps.py or switch to the python -m pmpsui entrypoint.
- Allow us to pass --area instead of --macros in pmpsui entrypoint

Bugfixes
--------
- Update the outdated beam class table to version 1.6
- Fix the broken --no-web arg on the pmpsui entrypoint
- Fix an issue where a blank main windows would appear early and be confusing

Maintenance
-----------
- Update the KFE configs from prod

Contributors
------------
- KaushikMalapati
- ZLLentz



v1.1.0 (2024-02-20)
===================

Features
--------
- adds a splash screen to show loading progress during startup

Maintenance
-----------
- re-organizes repository to support standard python package entrypoints

Contributors
------------
- tangkong
