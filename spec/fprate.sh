#!/usr/bin/env bash
cd /usr/cpu2017
. ./shrc
runcpu --action=build --config=enzo.cfg --size=test fprate
runcpu --action=run --config=enzo.cfg --size=test --nobuild fprate
