PMPS - User Interface
=====================

The main entry point for the PMPS UI is the `pmps.py` file.
This display takes a macro called `CFG` which specify the prefix for the
configuration file to be loaded, e.g. LFE_config.yml.

By default to ensure backwards compatibility, if one launches the `pmps.py` file
without specifying macros, the `LFE` configuration is loaded and the screen is
launched.

To launch a different configuration do:

```bash
pydm -m "CFG=KFE" pmps.py
```

Configuration File
==================

The configuration file provides information to render properly the screen and
expand the number of Fast Faults and Preemptive Requests displayed without the
need to modify other files or have a custom screen for each line.

Here is an example of a configuration file:

```yaml
# This is the prefix to be used for the arbiter
line_arbiter_prefix: "PMPS:KFE:"
# This is the undulator Kicker Rate PV provided by the Accelerator
undulator_kicker_rate_pv: "IOC:BSY0:MP01:BYKIKS_RATE"
# This is the URL to the Grafana dashboard to be displayed
dashboard_url: "http://ctl-logsrv01:3000/ctl/grafana/d/PRr2cuGGz/k-pmps-events?viewPanel=2&orgId=1&refresh=10s&kiosk"

# fastfaults is an array of fast faults to be configured.
fastfaults:
  - prefix: "PMPS:KFE:"
    ffo_start: 1
    ffo_end: 2
    ff_start: 1
    ff_end: 50

# preemptive_requests is an array of Preemptive Requests to be configured
preemptive_requests:
  - prefix: "PMPS:KFE:"
    arbiter_instance: "Arbiter:01"
    assertion_pool_start: 0
    assertion_pool_end: 20
```
