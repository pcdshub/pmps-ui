#!/bin/bash
config="${1}"
shift
python -m pmpsui --area "${config}" "$@"
