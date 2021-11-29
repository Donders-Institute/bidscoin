"""
This module contains the interface with phys2bids for converting physiological data to BIDS:

- test:                 A test routine for the plugin + its bidsmap options. Can also be called by the user from the bidseditor GUI
- is_sourcefile:        A routine to assess whether the file is of a valid dataformat for this plugin
- get_attribute:        A routine for reading an attribute from a sourcefile
- bidsmapper_plugin:    A routine that can be called by the bidsmapper to make a bidsmap of the source data
- bidscoiner_plugin:    A routine that can be called by the bidscoiner to convert the source data to bids

See also:
- https://github.com/physiopy/phys2bids
- https://github.com/ohbm/hackathon2021/issues/12
"""

try:
    from phys2bids.phys2bids import phys2bids
    from phys2bids.utils import SUPPORTED_FTYPES
except ImportError:
    SUPPORTED_FTYPES = ()   # TODO: handle gracefully
try:
    from bidscoin import bids
except ImportError:
    import bids             # This should work if bidscoin was not pip-installed
import logging
import shutil
import json
import tempfile
import pandas as pd
import ast
from pathlib import Path
from functools import lru_cache

LOGGER = logging.getLogger(__name__)

# The default options that are set when installing the plugin
OPTIONS = {}


def test(options: dict) -> bool:
    """
    This plugin function tests the working of the plugin + its bidsmap options

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins']['phys2bidscoin']
    :return:        True if the test was successful
    """

    LOGGER.debug(f'This is the phys2bids-plugin test routine, validating its working with options: {options}')

    return True


def is_sourcefile(file: Path) -> str:
    """
    This plugin function assesses whether a sourcefile is of a supported dataformat

    :param file:    The sourcefile that is assessed
    :return:        The valid / supported dataformat of the sourcefile
    """

    if file.suffix[1:] in SUPPORTED_FTYPES:
        if file.suffix == '.txt':
            try:
                phys2bids(file, info=True)
            except (RuntimeError, AttributeError):
                LOGGER.debug(f'This is the phys2bids-plugin is_sourcefile routine, assessing whether "{file}" has a valid dataformat')
                return ''
        return 'Physio'

    return ''


@lru_cache(maxsize=4096)
def phys2bids_cache(sourcefile: Path):
    """
    A chached version of phys2bids that reads the info structure

    :param sourcefile:  The sourcefile from which the info needs to be read
    :return:            The retrieved phys2bids info structure
    """

    return phys2bids(str(sourcefile), info=True)


def get_attribute(dataformat: str, sourcefile: Path, attribute: str, options: dict) -> str:
    """
    This plugin function reads attributes from the supported sourcefile

    :param dataformat:  The dataformat of the sourcefile, e.g. DICOM of PAR
    :param sourcefile:  The sourcefile from which key-value data needs to be read
    :param attribute:   The attribute key for which the value needs to be retrieved
    :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
    :return:            The retrieved attribute value
    """

    if dataformat == 'Physio':
        LOGGER.debug(f'This is the phys2bids-plugin get_attribute routine, reading the {dataformat} "{attribute}" attribute value from "{sourcefile}"')
    else:
        return ''

    if not sourcefile.is_file():
        LOGGER.error(f"Could not find {sourcefile}")
        return ''

    phys_info = phys2bids_cache(sourcefile)

    return phys_info.get(attribute, '')


def bidsmapper_plugin(session: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict) -> None:
    """
    All the heuristics format phys2bids attributes and properties onto bids labels and meta-data go into this plugin function.
    The function is expected to update / append new runs to the bidsmap_new data structure. The bidsmap options for this plugin
    are stored in:

    bidsmap_new['Options']['plugins']['phys2bidscoin']

    See also the dcm2niix2bids plugin for reference implementation

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap_new: The study bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure (with all options, BIDS labels and attributes, etc) that was created previously
    :param template:    The template bidsmap with the default heuristics
    :param store:       The paths of the source- and target-folder
    :return:
    """

    # Get the plugin settings
    plugin = {'phys2bidscoin': bidsmap_new['Options']['plugins']['phys2bidscoin']}

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
    This wrapper funtion around phys2bids converts the physio data in the session folder and saves it in the bidsfolder.
    Each saved datafile should be accompanied with a json sidecar file. The bidsmap options for this plugin can be found in:

    bidsmap_new['Options']['plugins']['phys2bidscoin']

    See also the dcm2niix2bids plugin for reference implementation

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :return:            Nothing
    """

    # Get started and see what dataformat we have
    plugin     = {'phys2bidscoin': bidsmap['Options']['plugins']['phys2bidscoin']}
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

        # Get an ordered list of the func runs from the scans.tsv file (which should have a standardized datetime format)
        scans_tsv = bidsses/f"{subid}{bids.add_prefix('_', sesid)}_scans.tsv"
        if scans_tsv.is_file():
            scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
            scans_table.sort_values(by=['acq_time', 'filename'], inplace=True)
        else:
            LOGGER.error(f"Could not read the TR's for phys2bids due to a missing '{scans_tsv}' file")
            continue
        funcscans = []
        for index, row in scans_table.iterrows():
            if index.startswith('func/'):
                funcscans.append(index)

        # Then read the TR's from the associated func sidecar files
        tr = []
        for funcscan in funcscans:
            with (bidsses/funcscan).with_suffix('.json').open('r') as json_fid:
                jsondata = json.load(json_fid)
            tr.append(jsondata['RepetitionTime'])

        # Create a heuristic function for phys2bids
        heur_str = ('def heur(physinfo, run=""):\n'
                    '    info = {}\n'
                   f'    if physinfo == "{sourcefile.name}":')
        for key, val in run['bids'].items():
            heur_str = (f'{heur_str}'
                        f'\n        info["{key}"] = "{val}"')
        heur_str = f'{heur_str}\n    return info'

        # Write heuristic function as file in temporary folder
        heur_file = Path(tempfile.mkdtemp())/f'heuristic_sub-{subid}_ses-{sesid}.py'
        heur_file.write_text(heur_str)

        # Run phys2bids
        physiofiles = phys2bids(filename                = str(sourcefile),
                                outdir                  = str(bidsfolder),
                                heur_file               = str(heur_file),
                                sub                     = subid,
                                ses                     = sesid,
                                chtrig                  = int(run['meta'].get('TriggerChannel', 0)),
                                num_timepoints_expected = run['meta'].get('ExpectedTimepoints', None),
                                tr                      = tr,
                                pad                     = run['meta'].get('Pad', 9),
                                ch_name                 = run['meta'].get('ChannelNames', []),
                                yml                     = '',
                                debug                   = True,
                                quiet                   = False)

        # Add user-specified meta-data to the newly produced json files (NB: assumes every physio-file comes with a json-file)
        for physiofile in physiofiles:
            jsonfile = Path(physiofile).with_suffix('.json')
            if not jsonfile.is_file():
                LOGGER.error(f"Could not find the expected json sidecar-file: '{jsonfile}'")
                continue
            with jsonfile.open('r') as json_fid:
                jsondata = json.load(json_fid)
            for metakey, metaval in run['meta'].items():
                metaval = datasource.dynamicvalue(metaval, cleanup=False, runtime=True)
                try:
                    metaval = ast.literal_eval(metaval)
                except ValueError:
                    pass
                LOGGER.info(f"Adding '{metakey}: {metaval}' to: {jsonfile}")
                jsondata[metakey] = metaval
            with jsonfile.open('w') as json_fid:
                json.dump(jsondata, json_fid, indent=4)
