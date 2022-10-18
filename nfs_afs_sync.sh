#!/bin/bash
# rsync the files in the deployed directory to afs to be picked up by acr
HERE="$(readlink -f "$(dirname -- "${BASH_SOURCE[0]}")")"
LOG="${HERE}/sync_log.txt"
SOURCE="${HERE}"
DEST="/afs/slac/g/lcls/tools/pydm/display/xray/pmps-ui"

echo "Sync at $(date)" | tee -a "${LOG}"
echo "from ${SOURCE}" | tee -a "${LOG}"
echo "to ${DEST}" | tee -a "${LOG}"
# Pick up permissions to write to afs
aklog
# Avoid git repo + random junk like screenshots
rsync -rv ${SOURCE}/*.py ${SOURCE}/*.ui ${SOURCE}/*.yml ${SOURCE}/*.sh ${SOURCE}/templates "${DEST}" 2>&1 | tee -a "${LOG}"
echo "---------------------------" >> "${LOG}"
