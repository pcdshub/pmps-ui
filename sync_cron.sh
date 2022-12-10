#!/bin/bash
# run the rsync and log it properly for cron
HERE="$(readlink -f "$(dirname -- "${BASH_SOURCE[0]}")")"
LOG="${HERE}/sync_log.txt"
SCRIPT="${HERE}/nfs_afs_sync.sh"

# Stdout and stderr must both go to the logfile
# Stderr must also go to the screen to trigger the cron email
# Stdout must not go to the screen to avoid the cron email
# 2>&1 redirects stderr to stdout so it goes through the pipe to tee's stdin
# >> redirects stdout (without stderr) to the logfile in append mode so it does not go through the pipe
${SCRIPT} 2>&1 1>>"${LOG}" | tee -a "${LOG}"
