#!/usr/bin/env bash
cd /usr/cpu2017
. ./shrc
runcpu --action=build --config=enzo.cfg --size=test 549.fotonik3d
runcpu --action=run --config=enzo.cfg --size=test --nobuild 549.fotonik3d
