cd /usr/
cd cpu2017/
source shrc
cd config
cp Example-gcc-linux-x86.cfg my_test.cfg
runcpu --fake --loose --size test --tune base --config my_test 503.bwaves_r
cd $SPEC
cd result/
go 503.bwaves_r build
spectar -cf - build_base_mytest-m64.0000/ | specxz >mybuild.tar.xz
cd build_base_mytest-m64.0000/
specmake clean
specmake SPECLANG=/usr/bin/
go result
grep 'Setting up' CPU2017.001.log
go 503.bwaves_r run
go 503.bwaves_r run run_base_test_mytest-m64.0000
cp ../../build/build_base_mytest-m64.0000/bwaves_r .
echo "Testing bwaves avoiding runspec..."
/opt/valgrind/inst/bin/valgrind \
  --tool=memcheck \
  --leak-check=no \
  --track-origins=no \
  --log-file=/tmp/memlog.log \
  --undef-value-errors=no \
  -- ./bwaves_r bwaves_2 < bwaves_2.in > bwaves_2.out
echo "Done. Analyze /tmp/memlog.log"
