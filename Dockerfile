FROM python:3.10-slim
# FROM delameter/pyqt5  # Not official and older, but it results in a smaller image (and already has the apt-get pyqt5 packages)

# Install the latest dcm2niix release (= typically outdated on the base image)
# RUN apt-get update && apt-get install -y dcm2niix

# Install the latest dcm2niix from sources
RUN apt-get update && apt-get -y install git build-essential cmake; \
    git clone https://github.com/rordenlab/dcm2niix.git; \
    cd dcm2niix; \
    mkdir build && cd build; \
    cmake --target clean -DZLIB_IMPLEMENTATION=Cloudflare -DUSE_JPEGLS=ON -DUSE_OPENJPEG=ON ..; \
    make install; \
    cd ..; rm -rf build

# Install pigz (to speed up dcm2niix) and curl (sometimes needed by dcm2niix)
RUN apt-get install -y pigz curl python3-pyqt5 python3-pyqt5.qtx11extras && rm -rf /var/cache/apt/archives

# Install the latest stable BIDScoin release from Python repository
RUN pip install --upgrade pip; \
    pip install bidscoin[all]
