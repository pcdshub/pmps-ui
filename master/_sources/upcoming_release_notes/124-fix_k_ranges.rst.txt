124 fix_k_ranges
#################

API Breaks
----------
- N/A

Features
--------
- Set the maximum value on K bar indicators to the maximum K value as determined by PV.
  Use the old hard-coded value of 6.0 as the default if the PV does not connect.
  If the PV has a value less than 6.0, use 6.0 instead as the minimum allowable max K.

Bugfixes
--------
- N/A

Maintenance
-----------
- N/A

Contributors
------------
- zllentz
