cd /usr/
cd cpu2017/
source shrc
cd config
cp Example-gcc-linux-x86.cfg my_test.cfg
runcpu --fake --loose --size test --tune base --config my_test 644.nab_s
cd $SPEC
cd result/
go 644.nab build
spectar -cf - build_base_mytest-m64.0000/ | specxz > mybuild.tar.xz
cd build_base_mytest-m64.0000/
specmake clean
specmake SPECLANG=/usr/bin/
go result
grep 'Setting up' CPU2017.001.log
go 644.nab run
go 644.nab run run_base_test_mytest-m64.0000
cp ../../build/build_base_mytest-m64.0000/nab_s .
echo "Testing nab_s avoiding runspec..."
cp -r /usr/cpu2017/benchspec/CPU/544.nab_r/data/test/input/hkrdenq /usr/cpu2017/benchspec/CPU/644.nab_s/build/build_base_mytest-m64.0000
cd /usr/cpu2017/benchspec/CPU/644.nab_s/build/build_base_mytest-m64.0000
/opt/valgrind/inst/bin/valgrind \
  --tool=memcheck \
  --leak-check=no \
  --track-origins=no \
  --log-file=/tmp/memlog.log \
  --undef-value-errors=no \
  -- ./nab_s hkrdenq 20140317 1
echo "Done. Analyze /tmp/memlog.log"
