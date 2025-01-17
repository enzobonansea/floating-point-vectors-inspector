cd /usr/
cd cpu2017/
source shrc
cd config
cp Example-gcc-linux-x86.cfg my_test.cfg
runcpu --fake --loose --size test --tune base --config my_test 519.lbm_r
cd $SPEC
cd result/
go 519.lbm build
spectar -cf - build_base_mytest-m64.0000/ | specxz >mybuild.tar.xz
cd build_base_mytest-m64.0000/
specmake clean
specmake SPECLANG=/usr/bin/
go result
grep 'Setting up' CPU2017.001.log
go 519.lbm run
go 519.lbm run run_base_test_mytest-m64.0000
cp ../../build/build_base_mytest-m64.0000/lbm_r .
echo "Testing lbm avoiding runspec..."
/opt/valgrind/inst/bin/valgrind --tool=memcheck --log-file=/tmp/memlog.log --undef-value-errors=no -- ./lbm_r 1 reference.dat 0 1 100_100_130_cf_a.of
echo "Done. Analyze /tmp/memlog.log"