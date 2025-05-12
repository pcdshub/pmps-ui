115 misc
#################

API Breaks
----------
- Delete the defunct symbolic link at the root of the repo.
  Old scripts that launch using this are encouraged to either
  swap to pmpsui/pmps.py or switch to the python -m pmpsui entrypoint.

Features
--------
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
- ZLLentz
- KaushikMalapati
