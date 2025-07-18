#!/usr/bin/env bash
cd /usr/cpu2017
. ./shrc
runcpu --action=run --config=memlog-monitor.cfg --size=test fprate
