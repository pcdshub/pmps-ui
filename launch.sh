#!/bin/bash
config="${1}"
shift
pydm --hide-nav-bar --hide-status-bar -m "CFG=${config}" pmps.py $@
