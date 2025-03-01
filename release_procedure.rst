=================
Release procedure
=================

This document describes how to prepare a new BIDScoin release from within the DCCN + from a local Linux VM

1. Delete the ``.bidscoin`` config folder and manually run the tox, bidscoin, bidsmapper, bidscoiner, bids-validator and other integration tests::

    rm -rf ~/.bidscoin
    cd ~/python/bidscoin
    git pull
    module load anaconda3
    source activate tox
    tox
    conda deactivate
    module load bidscoin/dev
    source activate /opt/bidscoin
    bidscoin -t
    # Perform integration tests from the command line and PyCharm

2. Build & test the apptainer container from GitHub in the Linux VM::

    rm -rf ~/.bidscoin
    cd ~/PycharmProjects/bidscoin
    vi apptainer.def    # -> Use `pip install github`
    sudo apptainer build bidscoin.sif apptainer.def
    xhost +
    apptainer exec --cleanenv --env DISPLAY=:0 bidscoin.sif bidscoin -t
    apptainer exec --cleanenv bidscoin.sif bidscoin -v
    apptainer exec --cleanenv bidscoin.sif pngappend
    apptainer cache clean
    vi apptainer.def    # Restore `pip install pypi`

3. Inspect the git history and update the CHANGELOG (including the links)
4. Update the cli help texts and RTD files
5. Update the version string everywhere (i.e. search without word matching) and COPYRIGHT
6. Add and push a git version tag if everything is OK

DCCN deployment
---------------

1. Copy the dev folder, update the bidsmaps and module::

    VERSION="4.5.0"
    cp -r /opt/bidscoin/dev /opt/bidscoin/$VERSION
    cd /opt/_modules/bidscoin
    ln -s .common $VERSION
    vi .version

3. Run a test::

    module load bidscoin
    source activate /opt/bidscoin
    bidscoin -v
    bidscoin -t
    conda deactivate

4. Post a release message on the MM data management channel

GitHub
------

Publish a new release. This will trigger a RTD build and run GitHub Actions for publishing on PyPI, GHCR and DockerHub

Neurodesk
---------

1. Pull and edit the bidscoin neurocontainer in a separate release branch
2. In the VM, build and test a neurodocker image::

    VERSION="4.5.0"
    cd ~/PycharmProjects/neurocontainers/recipes/bidscoin
    conda activate neurodocker
    ./build.sh -ds
    sudo docker image list         # Checkout the TAG
    sudo docker run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix bidscoin_${VERSION}:TAG bidscoin -t
    sudo docker system prune -a

3. Create a neurocontainers PR from the release branch

Neurostars/X/MM
---------------

1. Post a release message
