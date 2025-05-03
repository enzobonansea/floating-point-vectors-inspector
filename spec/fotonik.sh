exec > fotonik.out 2>&1
cd /usr/
cd cpu2017/
source shrc
cd config
cp Example-gcc-linux-x86.cfg my_test.cfg
runcpu --fake --loose --size test --tune base --config my_test 549.fotonik3d_r
cd $SPEC
cd result/
go 549.fotonik3d build
spectar -cf - build_base_mytest-m64.0000/ | specxz >mybuild.tar.xz
cd build_base_mytest-m64.0000/
specmake clean
specmake SPECLANG=/usr/bin/
go result
grep 'Setting up' CPU2017.001.log
go 549.fotonik3d run
go 549.fotonik3d run run_base_test_mytest-m64.0000

# Create a directory for our custom run
mkdir -p /tmp/fotonik_custom_run
cd /tmp/fotonik_custom_run

# Copy the executable
cp $SPEC/build/build_base_mytest-m64.0000/fotonik3d_r .

# Copy all necessary input files (test dataset)
cp $SPEC/benchspec/CPU/549.fotonik3d_r/data/test/input/* .

echo "Testing fotonik3d avoiding runspec..."
/opt/valgrind/inst/bin/valgrind \
  --tool=memcheck \
  --leak-check=no \
  --track-origins=no \
  --log-file=/tmp/memlog.log \
  --undef-value-errors=no \
  -- ./fotonik3d_r 1 yee.dat 0 1 fotonik3d.out
echo "Done. Analyze /tmp/memlog.log"