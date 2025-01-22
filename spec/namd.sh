cd /usr/
cd cpu2017/
source shrc
cd config
cp Example-gcc-linux-x86.cfg my_test.cfg
runcpu --fake --loose --size test --tune base --config my_test 508.namd_r
cd $SPEC
cd result/
go 508.namd build
spectar -cf - build_base_mytest-m64.0000/ | specxz >mybuild.tar.xz
cd build_base_mytest-m64.0000/
specmake clean
specmake SPECLANG=/usr/bin/
go result
grep 'Setting up' CPU2017.001.log
go 508.namd run
go 508.namd run run_base_test_mytest-m64.0000
cp ../../build/build_base_mytest-m64.0000/namd_r .
echo "Testing namd avoiding runspec..."
/opt/valgrind/inst/bin/valgrind \
  --tool=memcheck \
  --leak-check=no \
  --track-origins=no \
  --log-file=/tmp/memlog.log \
  --undef-value-errors=no \
  --time-stamp=yes \
  -- ./namd_r --input apoa1.input --iterations 1 --output namd.out
echo "Done. Analyze /tmp/memlog.log"