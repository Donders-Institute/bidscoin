FROM python:3.10-slim AS builder

# Make a dcm2niix build from the latest stable source code
RUN apt update && apt -y install git build-essential cmake; \
    git clone https://github.com/rordenlab/dcm2niix.git; \
    cd dcm2niix; mkdir build && cd build; \
    cmake -DZLIB_IMPLEMENTATION=Cloudflare -DUSE_JPEGLS=ON -DUSE_OPENJPEG=ON ..; \
    make install

# Or install the latest dcm2niix release from the base repository (= typically outdated)
# RUN apt update && apt -y install dcm2niix

FROM python:3.10-slim

# Install the dcm2niix build. NB: Obsolete with the new `pip install bidscoin[dcm2niix2bids]` extras option
COPY --from=builder /usr/local/bin/dcm2niix /usr/local/bin/dcm2niix

ENV PIP_NO_CACHE_DIR=off \
    FSLDIR=/opt/miniconda3 FSLOUTPUTTYPE=NIFTI_GZ \
    PATH=/opt/miniconda3/bin:$PATH

# First install pyqt5 as Debian package to solve dependencies issues occurring when installed with pip
# Then install the latest stable BIDScoin Qt5 release from Github (install the normal Qt6 branch from PyPi when using recent base images such as Ubuntu:22.04)
# Then install the latest miniconda (needed for FSL install) + FSL tools. NB: Keep the version the same as the Docker base image (currently Miniconda3-latest == py311)
# (see: https://github.com/NeuroDesk/neurocontainers/pull/598)
RUN apt update && apt -y --no-install-recommends install pigz curl python3-pyqt5 python3-pyqt5.qtx11extras git && apt clean; \
    pip install bidscoin[spec2nii2bids,deface]@git+https://github.com/Donders-Institute/bidscoin@v4.3.0+qt5; \
    mkdir -p /opt/miniconda3; \
    curl https://repo.anaconda.com/miniconda/Miniconda3-py310_23.11.0-2-Linux-x86_64.sh --output /opt/miniconda3/miniconda.sh; \
    bash /opt/miniconda3/miniconda.sh -b -u -p /opt/miniconda3; \
    rm -rf /opt/miniconda3/miniconda.sh; \
    export PATH=/opt/miniconda3/bin:$PATH; \
    conda config --set channel_priority strict; \
    conda install -c conda-forge -c https://fsl.fmrib.ox.ac.uk/fsldownloads/fslconda/public/ fsl-libvis fsl-avwutils fsl-flirt
