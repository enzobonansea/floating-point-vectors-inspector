# Setup
FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y build-essential wget gcc make libncurses5-dev libncursesw5-dev autotools-dev automake autoconf libtool nano libc6-dbg grep blender alsa-utils libarchive-tools

# SPEC
COPY cpu2017-1.1.9.iso /opt/spec/cpu2017.iso
RUN mkdir -p /usr/cpu2017 \
    && bsdtar -C /usr/cpu2017 -xf /opt/spec/cpu2017.iso \
    && echo -e "/usr/cpu2017\nyes" | /usr/cpu2017/install.sh \
    && rm /opt/spec/cpu2017.iso

# Add test programs
COPY alloc.c /tmp/alloc.c
RUN gcc -O0 -g -o /tmp/alloc /tmp/alloc.c
COPY example.py /tmp/example.py

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

# Copy meny
COPY menu.sh /usr/local/bin/menu.sh
RUN sed -i 's/\r$//' /usr/local/bin/menu.sh
RUN chmod +x /usr/local/bin/menu.sh

# Run menu on container init
CMD ["/usr/local/bin/menu.sh"]
