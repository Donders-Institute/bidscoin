FROM python:3-slim AS builder

# Install the latest dcm2niix from sources
# Or install the latest dcm2niix release from the base repository (= typically outdated)
# RUN apt update && apt -y install dcm2niix
RUN apt update && apt -y install git build-essential cmake wget; \
    git clone https://github.com/rordenlab/dcm2niix.git; \
    cd dcm2niix; mkdir build && cd build; \
    cmake -DZLIB_IMPLEMENTATION=Cloudflare -DUSE_JPEGLS=ON -DUSE_OPENJPEG=ON ..; \
    make install

# Install the latest miniconda (needed for FSL install)
RUN mkdir -p /opt/miniconda3; \
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /opt/miniconda3/miniconda.sh; \
    bash /opt/miniconda3/miniconda.sh -b -u -p /opt/miniconda3; \
    export PATH=/opt/miniconda3/bin:$PATH; \
    conda init bash; \
    conda config --set channel_priority strict; \
    . /root/.bashrc; \
    \
# Create a conda env and install FSL tools needed for (me)deface and slicereport. NB: Keep the version the same as the Docker base image
    conda create -n fsl python=3.10; \
    conda install -n fsl -c https://fsl.fmrib.ox.ac.uk/fsldownloads/fslconda/public/ -c conda-forge fsl-libvis fsl-avwutils fsl-flirt; \
    \
# Pack the fsl environment into fsl.tar.gz and unpack it in /opt/fsl \
    conda install -c conda-forge conda-pack; \
    conda pack -n fsl; \
    mkdir /opt/fsl && tar -xzf fsl.tar.gz -C /opt/fsl; \
    /opt/fsl/bin/conda-unpack


FROM python:3-slim

# Install the dcm2niix build. NB: Obsolete with the new `pip install bidscoin[dcm2niix2bids]` extras option
COPY --from=builder /usr/local/bin/dcm2niix /usr/local/bin/dcm2niix
COPY --from=builder /opt/fsl /opt/fsl

ENV FSLDIR=/opt/fsl FSLOUTPUTTYPE=NIFTI_GZ \
    PATH=$PATH:/opt/fsl/bin \
    PIP_NO_CACHE_DIR=off

# First install pyqt as Debian package to solve dependencies issues occurring when installed with pip
# Then install the latest stable BIDScoin release (add build-essential for newer python:3-slim base images (pip needs gcc))
RUN apt update && apt -y --no-install-recommends install pigz curl python3-pyqt6 build-essential libgl1 libxcb-cursor0 && apt clean; \
    pip install bidscoin[spec2nii2bids,deface]
