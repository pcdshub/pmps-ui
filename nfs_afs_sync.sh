#!/bin/bash
# rsync the files in the deployed directory to afs to be picked up by acr
LOG="$(readlink -f "$(dirname -- "${BASH_SOURCE[0]}")")/sync_log.txt"
SOURCE="/cds/group/pcds/epics-dev/screens/pydm/pmps-ui"
DEST="/afs/slac/g/lcls/tools/pydm/display/xray/pmps-ui"

echo "Sync at $(date)" >> "${LOG}"
echo "from ${SOURCE}" >> "${LOG}"
echo "to ${DEST}" >> "${LOG}"
# Avoid git repo + random junk like screenshots
rsync -rv ${SOURCE}/*.py ${SOURCE}/*.ui ${SOURCE}/*.yml ${SOURCE}/*.sh ${SOURCE}/*.sh ${SOURCE}/templates "${DEST}" >> "${LOG}"
echo "---------------------------" >> "${LOG}"
