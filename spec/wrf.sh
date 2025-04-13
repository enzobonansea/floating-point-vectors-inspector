cd /usr/
cd cpu2017/
source shrc
cd config
cp Example-gcc-linux-x86.cfg my_test.cfg
runcpu --fake --loose --size test --tune base --config my_test 521.wrf_r
cd $SPEC
cd result/
go 521.wrf build
spectar -cf - build_base_mytest-m64.0000/ | specxz > mybuild.tar.xz
cd build_base_mytest-m64.0000/
specmake clean TARGET=wrf_r
specmake SPECLANG=/usr/bin/ TARGET=wrf_r
go result
grep 'Setting up' CPU2017.001.log
go 521.wrf run
go 521.wrf run run_base_test_mytest-m64.0000
cp ../../build/build_base_mytest-m64.0000/wrf_r .
echo "Testing wrf_r avoiding runspec..."
cd /usr/cpu2017/benchspec/CPU/521.wrf_r/build/build_base_mytest-m64.0000
cp /usr/cpu2017/benchspec/CPU/521.wrf_r/run/run_base_test_mytest-m64.0000/* .
/opt/valgrind/inst/bin/valgrind \
  --tool=memcheck \
  --leak-check=no \
  --track-origins=no \
  --log-file=/tmp/memlog.log \
  --undef-value-errors=no \
  -- ./wrf_r
echo "Done. Analyze /tmp/memlog.log"
