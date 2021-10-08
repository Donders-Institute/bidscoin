"""
This module contains the interface with sovabids, both for the bidsmapper and for the bidscoiner:

- test:                 A test routine for the plugin + its bidsmap options. Can also be called by the user from the bidseditor GUI
- is_sourcefile:        A routine to assess whether the file is of a valid dataformat for this plugin
- get_attribute:        A routine for reading an attribute from a sourcefile
- bidsmapper_plugin:    A routine that can be called by the bidsmapper to make a bidsmap of the source data
- bidscoiner_plugin:    A routine that can be called by the bidscoiner to convert the source data to bids

"""

from sovabids.utils import get_supported_extensions,flatten
from sovabids.rules import apply_rules_to_single_file,load_rules
from sovabids.convert import update_dataset_description
from sovabids import __path__ as sovapath
# TODO: Handle sovabids import errors gracefully
try:
    from bidscoin import bids
except ImportError:
    import bids             # This should work if bidscoin was not pip-installed
import logging
import shutil
import json
import tempfile
import os
import pandas as pd
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def test(options: dict) -> bool:
    """
    This plugin function tests the working of the plugin + its bidsmap options

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
    :return:        True if the test was successful
    """

    LOGGER.debug(f'This is the sova2coin-plugin test routine, validating its working with options: {options}')

    return True


def is_sourcefile(file: Path) -> str:
    """
    This plugin function assesses whether a sourcefile is of a supported dataformat

    :param file:    The sourcefile that is assessed
    :return:        The valid / supported dataformat of the sourcefile
    """

    if file.suffix in get_supported_extensions():
        return 'EEG'

    return ''


def get_attribute(dataformat: str, sourcefile: Path, attribute: str, options: dict) -> str:
    """
    This plugin function reads attributes from the supported sourcefile

    :param dataformat:  The dataformat of the sourcefile, e.g. DICOM of PAR
    :param sourcefile:  The sourcefile from which key-value data needs to be read
    :param attribute:   The attribute key for which the value needs to be retrieved
    :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
    :return:            The retrieved attribute value
    """

    if dataformat == 'EEG':
        LOGGER.debug(f'This is the sova2coin-plugin get_attribute routine, reading the {dataformat} "{attribute}" attribute value from "{sourcefile}"')
    else:
        return ''
    temp_folder = os.path.join(sovapath[0],'_temp')
    _,sova_info = apply_rules_to_single_file(sourcefile._str,options.get('rules',{}),temp_folder,write=False,preview=True)
    sova_info = flatten(sova_info)
    shutil.rmtree(temp_folder)

    return sova_info.get(attribute, '')


def bidsmapper_plugin(session: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict) -> None:
    """
    All the heuristics format phys2bids attributes and properties onto bids labels and meta-data go into this plugin function.
    The function is expected to update / append new runs to the bidsmap_new data structure. The bidsmap options for this plugin
    are stored in:

    bidsmap_new['Options']['plugins']['phys2bidscoin']

    See also the dcm2bidsmap plugin for reference implementation

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap_new: The study bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure (with all options, BIDS labels and attributes, etc) that was created previously
    :param template:    The template bidsmap with the default heuristics
    :param store:       The paths of the source- and target-folder
    :return:
    """

    # Get the plugin settings
    plugin = {'sova2coin': bidsmap_new['Options']['plugins']['sova2coin']}

    # Update the bidsmap with the info from the source files
    for sourcefile in [file for file in session.rglob('*') if is_sourcefile(file)]:

        datasource = bids.DataSource(sourcefile, plugin)
        dataformat = datasource.dataformat

        # Input checks
        if not template[dataformat] and not bidsmap_old[dataformat]:
            LOGGER.error(f"No {dataformat} source information found in the bidsmap and template")
            return

        # See if we can find a matching run in the old bidsmap
        run, index = bids.get_matching_run(datasource, bidsmap_old)

        # If not, see if we can find a matching run in the template
        if index is None:
            run, _ = bids.get_matching_run(datasource, template)

        # See if we have collected the run somewhere in our new bidsmap
        if not bids.exist_run(bidsmap_new, '', run):

            # Communicate with the user if the run was not present in bidsmap_old or in template, i.e. that we found a new sample
            LOGGER.info(f"Found '{run['datasource'].datatype}' {dataformat} sample: {sourcefile}")

            # Now work from the provenance store
            if store:
                targetfile             = store['target']/sourcefile.relative_to(store['source'])
                targetfile.parent.mkdir(parents=True, exist_ok=True)
                run['provenance']      = str(shutil.copy2(sourcefile, targetfile))
                run['datasource'].path = targetfile

            # Copy the filled-in run over to the new bidsmap
            bids.append_run(bidsmap_new, run)


def bidscoiner_plugin(session: Path, bidsmap: dict, bidsfolder: Path) -> None:
    """
    This wrapper funtion around sovabids converts the data in the session folder and saves it in the bidsfolder.
    Each saved datafile should be accompanied with a json sidecar file. The bidsmap options for this plugin can be found in:

    bidsmap_new['Options']['plugins']['sova2coin']

    See also the dcm2niix2bids plugin for reference implementation

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :return:            Nothing
    """

    # Get started and see what dataformat we have
    plugin     = {'sova2coin': bidsmap['Options']['plugins']['sova2coin']}
    datasource = bids.get_datasource(session, plugin)
    dataformat = datasource.dataformat
    if not dataformat:
        LOGGER.info(f"No {__name__} sourcedata found in: {session}")
        return

    # Get valid BIDS subject/session identifiers from the (first) DICOM- or PAR/XML source file
    subid, sesid = datasource.subid_sesid(bidsmap[dataformat]['subject'], bidsmap[dataformat]['session'])
    bidsses      = bidsfolder/subid/sesid
    if not subid:
        LOGGER.error(f"Could not get a subject-id for {bidsfolder/subid/sesid}")
        return

    #####################################################################
    # Delete modality agnostic files BIDSCOIN wrote as a safety measure
    # TODO : Make mne-bids more aware of what was already wrote
    #        so that this isnt needed
    for filename in ['dataset_description.json','README','.bidsignore']:
        _file = os.path.join(bidsfolder,filename)
        if os.path.isfile(_file):
            os.remove(_file)
    #####################################################################

    # Loop over all source data files and convert them to BIDS
    for sourcefile in [file for file in session.rglob('*') if is_sourcefile(file)]:

        # Get a data source, a matching run from the bidsmap and update its run['datasource'] object
        datasource         = bids.DataSource(sourcefile, plugin, dataformat)
        run, index         = bids.get_matching_run(datasource, bidsmap, runtime=True)
        datasource         = run['datasource']
        datasource.path    = sourcefile
        datasource.plugins = plugin

        # Check if we should ignore this run
        if datasource.datatype in bidsmap['Options']['bidscoin']['ignoretypes']:
            LOGGER.info(f"Leaving out: {sourcefile}")
            continue

        # Check that we know this run
        if index is None:
            LOGGER.error(f"Skipping unknown '{datasource.datatype}' run: {sourcefile}\n-> Re-run the bidsmapper and delete the physiological output data in {bidsses} to solve this warning")
            continue

        LOGGER.info(f"Processing: {sourcefile}")

        #####################################################################
        # Run sovabids
        rules = plugin['sova2coin'].get('rules',{})
        apply_rules_to_single_file(sourcefile.as_posix(),rules,bidsfolder.as_posix(),write=True)
        # Grab the info from the last file to make the dataset description
        rules = load_rules(rules)
        update_dataset_description(rules.get('dataset_description',{}),bidsfolder.as_posix())
        #####################################################################

