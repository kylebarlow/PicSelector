# syntax=docker/dockerfile:1

# as ffmpeg_build if multi-stage build
FROM ubuntu:22.04

RUN apt update
RUN apt -y install \
  autoconf \
  automake \
  build-essential \
  cmake \
  git-core \
  libass-dev \
  libfreetype6-dev \
  libgnutls28-dev \
  libmp3lame-dev \
  libsdl2-dev \
  libtool \
  libva-dev \
  libvdpau-dev \
  libvorbis-dev \
  libxcb1-dev \
  libxcb-shm0-dev \
  libxcb-xfixes0-dev \
  libx264-dev \
  libx265-dev libnuma-dev \
  libvpx-dev \
  libfdk-aac-dev \
  libopus-dev \
  libdav1d-dev \
  meson \
  nasm \
  ninja-build \
  pkg-config \
  texinfo \
  wget \
  yasm \
  zlib1g-dev

RUN apt -y install gnutls-dev libunistring-dev

RUN mkdir -p ~/ffmpeg_sources ~/bin

RUN cd ~/ffmpeg_sources && \
git -C SVT-AV1 pull 2> /dev/null || git clone https://gitlab.com/AOMediaCodec/SVT-AV1.git && \
mkdir -p SVT-AV1/build && \
cd SVT-AV1/build && \
PATH="$HOME/bin:$PATH" cmake -G "Unix Makefiles" -DCMAKE_INSTALL_PREFIX="$HOME/ffmpeg_build" -DCMAKE_BUILD_TYPE=Release -DBUILD_DEC=OFF -DBUILD_SHARED_LIBS=OFF .. && \
PATH="$HOME/bin:$PATH" make && \
make install

RUN cd ~/ffmpeg_sources && \
wget -O ffmpeg-snapshot.tar.bz2 https://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2 && \
tar xjvf ffmpeg-snapshot.tar.bz2 && \
cd ffmpeg && \
PATH="$HOME/bin:$PATH" PKG_CONFIG_PATH="$HOME/ffmpeg_build/lib/pkgconfig" ./configure \
  --prefix="$HOME/ffmpeg_build" \
  --pkg-config-flags="--static" \
  --extra-cflags="-I$HOME/ffmpeg_build/include" \
  --extra-ldflags="-L$HOME/ffmpeg_build/lib" \
  --extra-libs="-lpthread -lm" \
  --ld="g++" \
  --bindir="$HOME/bin" \
  --enable-gpl \
  --enable-gnutls \
  --enable-libass \
  --enable-libfdk-aac \
  --enable-libfreetype \
  --enable-libmp3lame \
  --enable-libopus \
  --enable-libsvtav1 \
  --enable-libdav1d \
  --enable-libvorbis \
  --enable-libvpx \
  --enable-libx264 \
  --enable-libx265 \
  --enable-nonfree && \
PATH="$HOME/bin:$PATH" make && \
make install && \
hash -r

# Theoretically good to do this as a multi-stage build, but static ffmpeg isn't working - it complains about missing libraries
# FROM ubuntu:22.04

# RUN apt update
RUN apt install -y libpq-dev python3-pip nginx

WORKDIR /python_docker

COPY library/Flask_User-1.0.2.3-py2.py3-none-any.whl /python_docker
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

# COPY --from=ffmpeg_build /root/bin/ffmpeg /usr/local/bin
# COPY --from=ffmpeg_build /root/bin/ffprobe /usr/local/bin
RUN ln -s /root/bin/ffmpeg /usr/local/bin/ffmpeg
RUN ln -s /root/bin/ffprobe /usr/local/bin/ffprobe

WORKDIR /webwork
# Python code
COPY . .

# Server config
# COPY wsgi.py .
# COPY pic_selector.ini .
COPY system_config/flask_docker_run_services.sh .
COPY system_config/pic_selector.site /etc/nginx/sites-available/pic_selector

RUN ln -s /etc/nginx/sites-available/pic_selector /etc/nginx/sites-enabled/pic_selector

# CMD [ "python3", "-m" , "flask", "--app", "pic_selector_app", "run", "--host=0.0.0.0", "--port=5000"]
CMD /webwork/flask_docker_run_services.sh