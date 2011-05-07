#!/bin/bash
# This simple script will start autosync.py daemons for all configs found in $XDG_CONF_HOME/autosync/,
# stopping any existing daemons with that config first.
conf=${XDG_CONF_HOME:-$HOME/.config}/autosync
data=${XDG_DATA_HOME:-$HOME/.local/share}/autosync
mkdir -p $data/log
for i in $conf/*
do
    pkill -f "python.*autosync.py .*autosync/$(basename $i)"
    autosync.py $i &> $data/log/$(basename $i).$(date '+%F-%T').log &
done
