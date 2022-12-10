#!/bin/bash
# rsync the files in the deployed directory to afs to be picked up by acr
HERE="$(readlink -f "$(dirname -- "${BASH_SOURCE[0]}")")"
SOURCE="${HERE}"
DEST="/afs/slac/g/lcls/tools/pydm/display/xray/pmps-ui"

echo "Sync at $(date)"
echo "from ${SOURCE}"
echo "to ${DEST}"
# Avoid git repo + random junk like screenshots
rsync -rv ${SOURCE}/*.py ${SOURCE}/*.ui ${SOURCE}/*.yml ${SOURCE}/*.sh ${SOURCE}/templates "${DEST}"
echo "---------------------------"
