# Setup
FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y build-essential wget gcc make libncurses5-dev libncursesw5-dev autotools-dev automake autoconf libtool nano libc6-dbg grep libarchive-tools gfortran

# SPEC
COPY cpu2017-1.1.9.iso /opt/spec/cpu2017.iso
RUN mkdir -p /usr/cpu2017 \
    && bsdtar -C /usr/cpu2017 -xf /opt/spec/cpu2017.iso \
    && echo -e "/usr/cpu2017\nyes" | /usr/cpu2017/install.sh \
    && rm /opt/spec/cpu2017.iso

# Add test programs
COPY alloc.c /usr/alloc.c
RUN gcc -mavx -mavx2 -O0 -g -o /usr/alloc /usr/alloc.c

# Install custom valgrind
ADD valgrind /opt/valgrind
WORKDIR /opt/valgrind
RUN sed -i -e 's/\r$//' autogen.sh && find . -type f -exec sed -i -e 's/\r$//' {} \;
RUN chmod +x ./auxprogs/*
RUN chmod +x autogen.sh
RUN ./autogen.sh && ./configure --prefix=`pwd`/inst && make install

# Copy SPEC tools' runners
COPY spec/lbm.sh /usr/local/bin/spec/lbm.sh
RUN sed -i 's/\r$//' /usr/local/bin/spec/lbm.sh
RUN chmod +x /usr/local/bin/spec/lbm.sh

COPY spec/namd.sh /usr/local/bin/spec/namd.sh
RUN sed -i 's/\r$//' /usr/local/bin/spec/namd.sh
RUN chmod +x /usr/local/bin/spec/namd.sh

COPY spec/bwaves.sh /usr/local/bin/spec/bwaves.sh
RUN sed -i 's/\r$//' /usr/local/bin/spec/bwaves.sh
RUN chmod +x /usr/local/bin/spec/bwaves.sh

COPY spec/nab.sh /usr/local/bin/spec/nab.sh
RUN sed -i 's/\r$//' /usr/local/bin/spec/nab.sh
RUN chmod +x /usr/local/bin/spec/nab.sh

COPY spec/wrf.sh /usr/local/bin/spec/wrf.sh
RUN sed -i 's/\r$//' /usr/local/bin/spec/wrf.sh
RUN chmod +x /usr/local/bin/spec/wrf.sh

COPY spec/fotonik.sh /usr/local/bin/spec/fotonik.sh
RUN sed -i 's/\r$//' /usr/local/bin/spec/fotonik.sh
RUN chmod +x /usr/local/bin/spec/fotonik.sh

COPY spec/memlog-monitor.cfg /usr/cpu2017/config/memlog-monitor.cfg
RUN sed -i 's/\r$//' /usr/cpu2017/config/memlog-monitor.cfg


# Copy menu
COPY menu.sh /usr/local/bin/menu.sh
RUN sed -i 's/\r$//' /usr/local/bin/menu.sh
RUN chmod +x /usr/local/bin/menu.sh

# Install memlog_parser.py
RUN apt-get update && apt-get install -y python-is-python3 pip
RUN pip install tqdm
COPY memlog_parser.py /usr/memlog_parser.py

# TODO: install /usr/mmu_compressor

# Run menu on container init
CMD ["/usr/local/bin/menu.sh"]
