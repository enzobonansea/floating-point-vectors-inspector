#!/usr/bin/env bash
cd /usr/cpu2017
. ./shrc
runcpu --action=build --config=./enzo.cfg --size=test 549.fotonik3d
/opt/valgrind/inst/bin/valgrind --tool=memcheck --leak-check=no --track-origins=no --log-file=/tmp/memlog.log --undef-value-errors=no --trace-children=yes -- runcpu --action=run --config=enzo.cfg --size=test --nobuild 549.fotonik3d
