"""
This module contains the interface to convert the session nifti source-files into BIDS-valid nifti-files in the corresponding bidsfolder.
"""

import logging
import dateutil.parser
import json
import ast
import shutil
import pandas as pd
import nibabel as nib
from typing import Union
from pathlib import Path
try:
    from bidscoin import bids
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger(__name__)

# The default/fallback options that are set when installing/using the plugin
OPTIONS = {'ext': '.nii.gz',
           'meta': ['.json', '.tsv', '.bval', '.bvec']}


def test(options) -> bool:
    """
    Performs a nibabel test

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins']['nibabel2bids']
    :return:        True if the tool generated the expected result, False if there was a tool error
    """

    LOGGER.info('Testing the nibabel2bids installation:')

    # Test the nibabel installation
    try:
        LOGGER.info(f"Nibabel version: {nib.info.VERSION}")
        return True
    except Exception as nibabelerror:
        LOGGER.error(f"Nibabel error:\n{nibabelerror}")
        return False


def is_sourcefile(file: Path) -> str:
    """
    This plugin function supports assessing whether the file is a valid sourcefile

    :param file:    The file that is assessed
    :return:        The valid dataformat of the file for this plugin
    """

    ext = ''.join(file.suffixes)
    if file.is_file() and ext.lower() in list(nib.ext_map.keys()) + ['.nii.gz']:
        return 'Nibabel'

    return ''


def get_attribute(dataformat: str, sourcefile: Path, attribute: str, options: dict) -> Union[str, int, float]:
    """
    This plugin supports reading attributes from DICOM and PAR dataformats

    :param dataformat:  The bidsmap-dataformat of the sourcefile, e.g. DICOM of PAR
    :param sourcefile:  The sourcefile from which the attribute value should be read
    :param attribute:   The attribute key for which the value should be read
    :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
    :return:            The attribute value
    """

    if dataformat == 'Nibabel':
        return nib.load(str(sourcefile)).header.get(attribute)


def bidsmapper_plugin(session: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict) -> None:
    """
    All the logic to map the Nibabel header fields onto bids labels go into this function

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap_new: The new study bidsmap that we are building
    :param bidsmap_old: The previous study bidsmap that has precedence over the template bidsmap
    :param template:    The template bidsmap with the default heuristics
    :param store:       The paths of the source- and target-folder
    :return:
    """

    # Get started
    plugin     = {'nibabel2bids': bidsmap_new['Options']['plugins']['nibabel2bids']}
    datasource = bids.get_datasource(session, plugin, recurse=2)
    if not datasource.dataformat == 'Nibabel':
        return
    if not (template[datasource.dataformat] or bidsmap_old[datasource.dataformat]):
        LOGGER.error(f"No {datasource.dataformat} source information found in the bidsmap and template")
        return

    # Collect the different DICOM/PAR source files for all runs in the session
    for sourcefile in [file for file in session.rglob('*') if is_sourcefile(file)]:
        datasource = bids.DataSource(sourcefile, plugin, datasource.dataformat)

        # See if we can find a matching run in the old bidsmap
        run, index = bids.get_matching_run(datasource, bidsmap_old)

        # If not, see if we can find a matching run in the template
        if index is None:
            run, _ = bids.get_matching_run(datasource, template)

        # See if we have collected the run somewhere in our new bidsmap
        if not bids.exist_run(bidsmap_new, '', run):

            # Communicate with the user if the run was not present in bidsmap_old or in template, i.e. that we found a new sample
            LOGGER.info(f"Found '{run['datasource'].datatype}' {datasource.dataformat} sample: {sourcefile}")

            # Now work from the provenance store
            if store:
                targetfile             = store['target']/sourcefile.relative_to(store['source'])
                targetfile.parent.mkdir(parents=True, exist_ok=True)
                run['provenance']      = str(shutil.copy2(sourcefile, targetfile))
                run['datasource'].path = targetfile

            # Copy the filled-in run over to the new bidsmap
            bids.append_run(bidsmap_new, run)

        else:
            # Communicate with the user if the run was already present in bidsmap_old or in template
            LOGGER.debug(f"Known '{run['datasource'].datatype}' {datasource.dataformat} sample: {sourcefile}")


def bidscoiner_plugin(session: Path, bidsmap: dict, bidsses: Path) -> None:
    """
    The bidscoiner plugin to convert the session Nibabel source-files into BIDS-valid nifti-files in the
    corresponding bids session-folder

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsses:     The full-path name of the BIDS output `sub-/ses-` folder
    :return:            Nothing
    """

    # Get the subject identifiers and the BIDS root folder from the bidsses folder
    if bidsses.name.startswith('ses-'):
        bidsfolder = bidsses.parent.parent
        subid      = bidsses.parent.name
        sesid      = bidsses.name
    else:
        bidsfolder = bidsses.parent
        subid      = bidsses.name
        sesid      = ''

    # Get started
    options    = bidsmap['Options']['plugins']['nibabel2bids']
    ext        = options.get('ext', '.nii.gz')
    meta       = options.get('meta')
    datasource = bids.get_datasource(session, {'nibabel2bids':options}, recurse=2)
    if not datasource.dataformat == 'Nibabel':
        return
    if not bidsmap[datasource.dataformat]:
        LOGGER.error(f"No {datasource.dataformat} source information found in the bidsmap")
        return

    # Read or create a scans_table and tsv-file
    scans_tsv = bidsses/f"{subid}{bids.add_prefix('_', sesid)}_scans.tsv"
    if scans_tsv.is_file():
        scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
    else:
        scans_table = pd.DataFrame(columns=['acq_time'], dtype='str')
        scans_table.index.name = 'filename'

    # Collect the different Nibabel source files for all files in the session
    for sourcefile in [file for file in session.rglob('*') if is_sourcefile(file)]:

        datasource          = bids.DataSource(sourcefile, {'nibabel2bids':options}, datasource.dataformat)
        run, index          = bids.get_matching_run(datasource, bidsmap, runtime=True)
        datasource          = run['datasource']
        datasource.path     = sourcefile
        datasource.plugins  = {'nibabel2bids': options}
        datatype            = datasource.datatype

        # Check if we should ignore this run
        if datatype in bidsmap['Options']['bidscoin']['ignoretypes']:
            LOGGER.info(f"Leaving out: {sourcefile}")
            continue

        # Check if we already know this run
        if index is None:
            LOGGER.error(f"Skipping unknown '{datatype}' run: {sourcefile}\n-> Re-run the bidsmapper and delete {bidsses} to solve this warning")
            continue

        LOGGER.info(f"Processing: {sourcefile}")

        # Create the BIDS session/datatype output folder
        outfolder = bidsses/datatype
        outfolder.mkdir(parents=True, exist_ok=True)

        # Compose the BIDS filename using the matched run
        bidsname = bids.get_bidsname(subid, sesid, run, runtime=True)
        runindex = run['bids'].get('run', '')
        if runindex.startswith('<<') and runindex.endswith('>>'):
            bidsname = bids.increment_runindex(outfolder, bidsname)
        bidsfile = (outfolder/bidsname).with_suffix(ext)

        # Check if file already exists (-> e.g. when a static runindex is used)
        if bidsfile.is_file():
            LOGGER.warning(f"{bidsfile}.* already exists and will be deleted -- check your results carefully!")
            bidsfile.with_suffix('').with_suffix(ext).unlink()

        # Save the sourcefile as a BIDS nifti file and copy the associated metadata files
        nib.save(nib.load(sourcefile), bidsfile)
        for suffix in meta:
            if sourcefile.with_suffix('').with_suffix(suffix).is_file():
                bidsfile.with_suffix('').with_suffix(suffix).unlink(missing_ok=True)
                shutil.copy2(sourcefile.with_suffix('').with_suffix(suffix), bidsfile.with_suffix('').with_suffix(suffix))

        # Load the json meta-data
        jsonfile = bidsfile.with_suffix('').with_suffix('.json')
        if jsonfile.is_file():
            with jsonfile.open('r') as json_fid:
                jsondata = json.load(json_fid)
        else:
            jsondata = {}

        # Add all the meta data to the meta-data. NB: the dynamic `IntendedFor` value is handled separately later
        for metakey, metaval in run['meta'].items():
            if metakey != 'IntendedFor':
                metaval = datasource.dynamicvalue(metaval, cleanup=False, runtime=True)
                try: metaval = ast.literal_eval(str(metaval))
                except (ValueError, SyntaxError): pass
                LOGGER.info(f"Adding '{metakey}: {metaval}' to: {jsonfile}")
            if not metaval:
                metaval = None
            jsondata[metakey] = metaval

        # Remove unused (but added from the template) B0FieldIdentifiers/Sources
        if not jsondata.get('B0FieldSource'):     jsondata.pop('B0FieldSource', None)
        if not jsondata.get('B0FieldIdentifier'): jsondata.pop('B0FieldIdentifier', None)

        # Save the meta-data to the json sidecar-file
        with jsonfile.open('w') as json_fid:
            json.dump(jsondata, json_fid, indent=4)

        # Add an entry to the scans_table (we typically don't have useful data to put there)
        acq_time = dateutil.parser.parse(f"1925-01-01T{jsondata.get('AcquisitionTime', '')}")
        scans_table.loc[bidsfile.relative_to(bidsses).as_posix(), 'acq_time'] = acq_time.isoformat()

    # Write the scans_table to disk
    LOGGER.info(f"Writing data to: {scans_tsv}")
    scans_table.replace('','n/a').to_csv(scans_tsv, sep='\t', encoding='utf-8', na_rep='n/a')

    # Add an (empty) entry to the participants_table (we don't have useful data to put there)
    participants_tsv = bidsfolder/'participants.tsv'
    if participants_tsv.is_file():
        participants_table = pd.read_csv(participants_tsv, sep='\t', dtype=str)
        participants_table.set_index(['participant_id'], verify_integrity=True, inplace=True)
    else:
        participants_table = pd.DataFrame()
        participants_table.index.name = 'participant_id'
    if subid in participants_table.index and 'session_id' in participants_table.keys() and participants_table.loc[subid, 'session_id']:
        return                                          # Only take data from the first session -> BIDS specification
    participants_table.loc[subid, 'session_id'] = sesid if sesid else None

    # Write the collected data to the participants tsv-file
    LOGGER.info(f"Writing {subid} subject data to: {participants_tsv}")
    participants_table.replace('','n/a').to_csv(participants_tsv, sep='\t', encoding='utf-8', na_rep='n/a')
