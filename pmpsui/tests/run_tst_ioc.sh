#!/usr/bin/bash
# Run a test IOC to simulate some PMPS PVs for TST_config.yml
THIS_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
cd "${THIS_DIR}" || exit

softIoc -d tst.db
