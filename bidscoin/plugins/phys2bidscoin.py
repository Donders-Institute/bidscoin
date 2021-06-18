"""
This module contains the interface with phys2bids, both for the bidsmapper and for the bidscoiner:

- test:                 A test routine for the plugin + its bidsmap options. Can also be called by the user from the bidseditor GUI
- is_sourcefile:        A routine to assess whether the file is of a valid dataformat for this plugin
- get_attribute:        A routine for reading an attribute from a sourcefile
- bidsmapper_plugin:    A routine that can be called by the bidsmapper to make a bidsmap of the source data
- bidscoiner_plugin:    A routine that can be called by the bidscoiner to convert the source data to bids

See also:
- https://github.com/ohbm/hackathon2021/issues/12
"""

try:
    from phys2bids.phys2bids import phys2bids
except ImportError:
    pass
try:
    from bidscoin import bids
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed
import logging
import shutil
import json
import tempfile
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def test(options: dict) -> bool:
    """
    This plugin function tests the working of the plugin + its bidsmap options

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
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

    try:
        phys2bids(file, info=True)
        return 'Physio'
    except Exception:
        LOGGER.debug(f'This is the phys2bids-plugin is_sourcefile routine, assessing whether "{file}" has a valid dataformat')

    return ''



def get_attribute(dataformat: str, sourcefile: Path, attribute: str) -> str:
    """
    This plugin function reads attributes from the supported sourcefile

    :param dataformat:  The dataformat of the sourcefile, e.g. DICOM of PAR
    :param sourcefile:  The sourcefile from which key-value data needs to be read
    :param attribute:   The attribute key for which the value needs to be retrieved
    :return:            The retrieved attribute value
    """

    if dataformat == 'Physio':
        LOGGER.debug(f'This is the phys2bids-plugin get_attribute routine, reading the {dataformat} "{attribute}" attribute value from "{sourcefile}"')
    else:
        return ''

    phys_info = phys2bids(sourcefile, info=True)

    return phys_info.get(attribute, '')


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

    # Get started
    plugin     = {'phys2bidscoin': bidsmap_new['Options']['plugins']['phys2bidscoin']}
    datasource = bids.get_datasource(session, plugin)
    dataformat = datasource.dataformat
    if not dataformat:
        return

    # Collect the different Physio source files (runs) in the session
    sourcefiles = [sourcefile for sourcefile in session.rglob('*') if is_sourcefile(sourcefile)]

    # Update the bidsmap with the info from the source files
    for sourcefile in sourcefiles:

        # Input checks
        if not sourcefile.name or (not template[dataformat] and not bidsmap_old[dataformat]):
            LOGGER.error(f"No {dataformat} source information found in the bidsmap and template")
            return

        datasource = bids.DataSource(sourcefile, plugin, dataformat)
        if not datasource.is_datasource():
            continue

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


def bidscoiner_plugin(session: Path, bidsmap: dict, bidsfolder: Path, personals: dict) -> None:
    """
    This wrapper funtion around phys2bids converts the physio data in the session folder and saves it in the bidsfolder.
    Each saved datafile should be accompanied with a json sidecar file. The bidsmap options for this plugin can be found in:

    bidsmap_new['Options']['plugins']['phys2bidscoin']

    See also the dcm2niix2bids plugin for reference implementation

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :return:            Nothing
    """

    # Get started and see what dataformat we have
    plugin     = {'phys2bidscoin': bidsmap['Options']['plugins']['phys2bidscoin']}
    datasource = bids.get_datasource(session, plugin)
    dataformat = datasource.dataformat
    if not dataformat:
        LOGGER.info(f"No {__name__} sourcedata found in: {session}")
        return

    # Make a list of all the data sources / runs
    sourcefiles = [sourcefile for sourcefile in session.rglob('*') if sourcefile.is_file()]

    # Get valid BIDS subject/session identifiers from the (first) DICOM- or PAR/XML source file
    subid, sesid = datasource.subid_sesid(bidsmap[dataformat]['subject'], bidsmap[dataformat]['session'])
    if not subid:
        return

    # Create the BIDS session-folder and a scans.tsv file
    bidsses = bidsfolder/subid/sesid
    bidsses.mkdir(parents=True, exist_ok=True)

    for sourcefile in sourcefiles:

        # Get a data source, a matching run from the bidsmap and update its run['datasource'] object
        datasource          = bids.DataSource(sourcefile, plugin, dataformat)
        run, index          = bids.get_matching_run(datasource, bidsmap)
        datasource          = run['datasource']
        datasource.path     = sourcefile
        datasource.plugins  = plugin
        datatype            = datasource.datatype

        # Check if we should ignore this run
        if datatype == bids.ignoredatatype:
            LOGGER.info(f"Leaving out: {sourcefile}")
            continue

        # Check that we know this run
        if index is None:
            LOGGER.error(f"Skipping unknown '{datatype}' run: {sourcefile}\n-> Re-run the bidsmapper and delete {bidsses} to solve this warning")
            continue

        LOGGER.info(f"Processing: {sourcefile}")

        outdir = bidsses/datatype
        outdir.mkdir(parents=True, exist_ok=True)

        # Compose the BIDS filename using the matched run
        bidsname = bids.get_bidsname(subid, sesid, run, runtime=True)
        runindex = run['bids'].get('run', '')
        if runindex.startswith('<<') and runindex.endswith('>>'):
            bidsname = bids.increment_runindex(outdir, bidsname)
        jsonfile = (outdir/bidsname).with_suffix('.json')

        # Check if file already exists (-> e.g. when a static runindex is used)
        if (outdir/bidsname).with_suffix('.json').is_file():
            LOGGER.warning(f"{outdir/bidsname}.* already exists and will be deleted -- check your results carefully!")
            for ext in ('.nii.gz', '.nii', '.json', '.bval', '.bvec', '.tsv.gz'):
                (outdir/bidsname).with_suffix(ext).unlink(missing_ok=True)

        heuristic_str = ('def heur(physinfo, run=''):\n'
                         '    info = {}\n'
                         f'    if physinfo == "{sourcefile.name}":'
        )

        for key, val in run['bids'].items:
            if key != '':
                heuristic_str = (f'{heuristic_str}'
                                 f'\n        info["{key}"] = "{val}"'
                )

        heuristic_str = f'{heuristic_str}\n    return info'

        # Write heuristic function as file in temporary folder
        workfolder = Path(tempfile.mkdtemp())
        heuristic_file = workfolder/f'heuristic_sub-{subid}_ses-{sesid}.py'
        with open(heuristic_file, 'w') as text_file:
            print(heuristic_str, file=text_file)

        # Run phys2bids
        phys2bids(sourcefile, outdir=outdir, heur_file=sourcefile.with_suffix('.py'), sub=subid, ses=sesid, chtrig=int(run['meta'].get('TriggerChannel', 0)),
                  num_timepoints_expected=run['meta'].get('VolumeNumbers', None), tr=TRs, pad=run['meta'].get('Pad', 9),
                  ch_name=run['meta'].get('ChannelNames', []), yml='', debug=False, quiet=False)

        # Adapt all the newly produced json files and add user-specified meta-data (NB: assumes every nifti-file comes with a json-file)
        with jsonfile.open('r') as json_fid:
            jsondata = json.load(json_fid)
        for metakey, metaval in run['meta'].items():
            LOGGER.info(f"Adding '{metakey}: {metaval}' to: {jsonfile}")
            metaval = datasource.dynamicvalue(metaval, cleanup=False, runtime=True)
            jsondata[metakey] = metaval
        with jsonfile.open('w') as json_fid:
            json.dump(jsondata, json_fid, indent=4)
