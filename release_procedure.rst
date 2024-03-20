=================
Release procedure
=================

This document describes how to prepare a new BIDScoin release from within the DCCN + a Linux VM

1. Inspect the git history and update the release notes (including the links)
2. Delete the the bidscoin config folder
3. Update the version string everywhere (i.e. search without word matching)
4. Add a git version tag
5. Backport to PyQt5 in a v4.#.#+qt5 branch
6. Manually run the bidscoin, bidsmapper, bidscoiner, bids-validator and other integration tests
7. Run tox@DCCN::

    VERSION="4.3.1"
    cd ~/python/bidscoin
    git checkout v${VERSION}+qt5
    module load bidscoin/dev
    source activate tox
    tox
    conda deactivate
    source activate /opt/bidscoin
    ~/python/bidscoin/bidscoin/bcoin.py -t

8. Push the qt5-branch
9. Build & test the containers in a Linux VM::

    cd ~/PycharmProjects/bidscoin
    sudo apptainer build bidscoin.sif apptainer.def
    xhost +
    apptainer exec --cleanenv --env DISPLAY=:0 bidscoin.sif bidscoin -t
    apptainer exec --cleanenv --env DISPLAY=:0 bidscoin.sif pngappend
    apptainer cache clean

DCCN deployment
---------------

1. Copy the dev folder, checkout the Qt5 branch, update the bidsmaps and module::

    cp -r /opt/bidscoin/dev /opt/bidscoin/$VERSION
    cd /opt/bidscoin/$VERSION
    git checkout v${VERSION}+qt5 -f
    for TEMPLATE in bidscoin/heuristics/*.yaml; do
        sed -i 's/command: dcm2niix/command: module add dcm2niix; dcm2niix/' $TEMPLATE
    done
    cd /opt/_modules/bidscoin
    ln -s .common $VERSION
    vi .version

3. Run a test::

    module load bidscoin
    source activate /opt/bidscoin
    bidscoin -v
    bidscoin -t
    conda deactivate bidscoin

4. Post a release message on the MM data management channel

Dockerhub
---------

1. In the VM, build, test and push a Docker image::

    sudo docker build -t marcelzwiers/bidscoin:$VERSION .
    sudo docker run --rm marcelzwiers/bidscoin:$VERSION bidscoin -v
    sudo docker run --rm marcelzwiers/bidscoin:$VERSION pngappend
    sudo docker run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix marcelzwiers/bidscoin:$VERSION bidscoin -t
    sudo docker push marcelzwiers/bidscoin:$VERSION
    sudo docker system prune -a

Github
------

1. Publish a new release

Pypi
----

1. Temporarily remove the raw html logo markup
2. Build and upload the new release::

    conda deactivate
    source activate tox
    cd ~/python/bidscoin
    git checkout master
    rm dist/*
    python3 -m pip install --upgrade build twine
    python3 -m build
    python3 -m twine upload --repository testpypi dist/*
    python3 -m twine upload dist/*

3. Restore raw html logo markup

Neurodesk
---------

1. Pull and edit the bidscoin neurocontainer in a separate release branch
2. Build and test a neurodocker image::

    cd ~/PycharmProjects/neurocontainers/recipes/bidscoin
    conda activate neurodocker
    ./build.sh -ds
    sudo docker image list         # Checkout the TAG
    sudo docker run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix bidscoin_$(VERSION}:TAG bidscoin -t

3. Create a neurocontainers PR from the release branch

Neurostars/X/MM
---------------

1. Post a release message
