"""The nibabel2bids plugin wraps around the flexible nibabel (https://nipy.org/nibabel) tool to convert a wide variety
of data formats into NIfTI-files. Currently, the default template bidsmap is tailored to NIfTI source data only
(but this can readily be extended), and BIDS sidecar files are not automatically produced by nibabel"""

import logging
import dateutil.parser
import json
import shutil
import pandas as pd
import nibabel as nib
from bids_validator import BIDSValidator
from typing import Union
from pathlib import Path
from bidscoin import bids
from bidscoin.bids import Bidsmap, Plugin

try:
    from nibabel.testing import data_path
except ImportError:
    from importlib.resources import files           # PY38: from importlib_resources import files ???
    data_path = files('nibabel')/'tests'/'data'

LOGGER = logging.getLogger(__name__)

# The default/fallback options that are set when installing/using the plugin
OPTIONS = Plugin({'ext': '.nii.gz',                                         # The (nibabel) file extension of the output data, i.e. ``.nii.gz`` or ``.nii``
                  'meta': ['.json', '.tsv', '.tsv.gz', '.bval', '.bvec']})  # The file extensions of the equally named metadata sourcefiles that are copied over as BIDS sidecar files


def test(options: Plugin=OPTIONS) -> int:
    """
    Performs a nibabel test

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins']['nibabel2bids']
    :return:        The errorcode: 0 for successful execution, 1 for general tool errors, 2 for `ext` option errors, 3 for `meta` option errors
    """

    LOGGER.info('Testing the nibabel2bids installation:')

    # Test the nibabel installation
    try:

        LOGGER.info(f"Nibabel version: {nib.__version__}")
        if options.get('ext',OPTIONS['ext']) not in ('.nii', '.nii.gz'):
            LOGGER.error(f"The 'ext: {options.get('ext')}' value in the nibabel2bids options is not '.nii' or '.nii.gz'")
            return 2

        if not isinstance(options.get('meta',OPTIONS['meta']), list):
            LOGGER.error(f"The 'meta: {options.get('meta')}' value in the nibabel2bids options is not a list")
            return 3

        niifile = Path(data_path)/'anatomical.nii'
        assert is_sourcefile(niifile) == 'Nibabel'
        assert str(get_attribute('Nibabel', niifile, 'descrip', options)) == "b'spm - 3D normalized'"

    except Exception as nibabelerror:

        LOGGER.error(f"Nibabel error:\n{nibabelerror}")
        return 1

    return 0


def is_sourcefile(file: Path) -> str:
    """
    This plugin function supports assessing whether the file is a valid sourcefile

    :param file:    The file that is assessed
    :return:        The valid dataformat of the file for this plugin
    """

    ext = ''.join(file.suffixes)
    if file.is_file() and ext.lower() in sum((klass.valid_exts for klass in nib.imageclasses.all_image_classes),()) + ('.nii.gz',):
        return 'Nibabel'

    return ''


def get_attribute(dataformat: str, sourcefile: Path, attribute: str, options: Plugin) -> Union[str, int, float, list]:
    """
    This plugin supports reading attributes from DICOM and PAR dataformats

    :param dataformat:  The bidsmap-dataformat of the sourcefile, e.g. DICOM of PAR
    :param sourcefile:  The sourcefile from which the attribute value should be read
    :param attribute:   The attribute key for which the value should be read
    :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins']
    :return:            The attribute value
    """

    value = None

    if dataformat == 'Nibabel':

        try:
            value = nib.load(sourcefile).header.get(attribute)
            if value is not None:
                value = value.tolist()

        except Exception:
            LOGGER.exception(f"Could not get the nibabel '{attribute}' attribute from {sourcefile} -> {value}")

    return value


def bidsmapper_plugin(session: Path, bidsmap_new: Bidsmap, bidsmap_old: Bidsmap, template: Bidsmap, store: dict) -> None:
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
    plugins    = {'nibabel2bids': Plugin(bidsmap_new['Options']['plugins']['nibabel2bids'])}
    datasource = bids.get_datasource(session, plugins, recurse=2)
    if not datasource.dataformat:
        return
    if not (template[datasource.dataformat] or bidsmap_old[datasource.dataformat]):
        LOGGER.error(f"No {datasource.dataformat} source information found in the bidsmap and template")
        return

    # Collect the different DICOM/PAR source files for all runs in the session
    for sourcefile in [file for file in session.rglob('*') if is_sourcefile(file)]:

        # See if we can find a matching run in the old bidsmap
        datasource = bids.DataSource(sourcefile, plugins, datasource.dataformat)
        run, match = bids.get_matching_run(datasource, bidsmap_old)

        # If not, see if we can find a matching run in the template
        if not match:
            run, _ = bids.get_matching_run(datasource, template)

        # See if we have collected the run somewhere in our new bidsmap
        if not bids.exist_run(bidsmap_new, '', run):

            # Communicate with the user if the run was not present in bidsmap_old or in template, i.e. that we found a new sample
            if not match:
                LOGGER.info(f"Discovered '{datasource.datatype}' {datasource.dataformat} sample: {sourcefile}")

            # Now work from the provenance store
            if store:
                targetfile             = store['target']/sourcefile.relative_to(store['source'])
                targetfile.parent.mkdir(parents=True, exist_ok=True)
                LOGGER.verbose(f"Storing the discovered {datasource.dataformat} sample as: {targetfile}")
                run['provenance']      = str(shutil.copyfile(sourcefile, targetfile))
                run['datasource'].path = targetfile

            # Copy the filled-in run over to the new bidsmap
            bids.append_run(bidsmap_new, run)


def bidscoiner_plugin(session: Path, bidsmap: Bidsmap, bidsses: Path) -> None:
    """
    The bidscoiner plugin to convert the session Nibabel source-files into BIDS-valid NIfTI-files in the
    corresponding bids session-folder

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsses:     The full-path name of the BIDS output `sub-/ses-` folder
    :return:            Nothing
    """

    # Get the subject identifiers and the BIDS root folder from the bidsses folder
    if bidsses.name.startswith('ses-'):
        subid = bidsses.parent.name
        sesid = bidsses.name
    else:
        subid = bidsses.name
        sesid = ''

    # Get started
    options     = bidsmap['Options']['plugins']['nibabel2bids']
    ext         = options.get('ext', '')
    meta        = options.get('meta', [])
    sourcefiles = [file for file in session.rglob('*') if is_sourcefile(file)]
    if not sourcefiles:
        LOGGER.info(f"--> No {__name__} sourcedata found in: {session}")
        return

    # Read or create a scans_table and tsv-file
    scans_tsv = bidsses/f"{subid}{'_'+sesid if sesid else ''}_scans.tsv"
    if scans_tsv.is_file():
        scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
    else:
        scans_table = pd.DataFrame(columns=['acq_time'], dtype='str')
        scans_table.index.name = 'filename'

    # Collect the different Nibabel source files for all files in the session
    for source in sourcefiles:

        datasource = bids.DataSource(source, {'nibabel2bids':options})
        run, runid = bids.get_matching_run(datasource, bidsmap, runtime=True)

        # Check if we should ignore this run
        if datasource.datatype in bidsmap['Options']['bidscoin']['ignoretypes']:
            LOGGER.info(f"--> Leaving out: {source}")
            bids.bidsprov(bidsses, source, runid, datasource.datatype)              # Write out empty provenance data
            continue

        # Check if we already know this run
        if not runid:
            LOGGER.error(f"Skipping unknown '{datasource.datatype}' run: {source}\n-> Re-run the bidsmapper and delete {bidsses} to solve this warning")
            bids.bidsprov(bidsses, source)                      # Write out empty provenance data
            continue

        LOGGER.info(f"--> Coining: {source}")

        # Create the BIDS session/datatype output folder
        outfolder = bidsses/datasource.datatype
        outfolder.mkdir(parents=True, exist_ok=True)

        # Compose the BIDS filename using the matched run
        bidsignore = bids.check_ignore(datasource.datatype, bidsmap['Options']['bidscoin']['bidsignore'])
        bidsname   = bids.get_bidsname(subid, sesid, run, not bidsignore, runtime=True)
        bidsignore = bidsignore or bids.check_ignore(bidsname+'.json', bidsmap['Options']['bidscoin']['bidsignore'], 'file')
        bidsname   = bids.increment_runindex(outfolder, bidsname, run, scans_table)
        target     = (outfolder/bidsname).with_suffix(ext)

        # Check if the bidsname is valid
        bidstest = (Path('/')/subid/sesid/datasource.datatype/bidsname).with_suffix('.json').as_posix()
        isbids   = BIDSValidator().is_bids(bidstest)
        if not isbids and not bidsignore:
            LOGGER.warning(f"The '{bidstest}' output name did not pass the bids-validator test")

        # Check if file already exists (-> e.g. when a static runindex is used)
        if target.is_file():
            LOGGER.warning(f"{target} already exists and will be deleted -- check your results carefully!")
            target.unlink()

        # Save the sourcefile as a BIDS NIfTI file and out provenance data
        nib.save(nib.load(source), target)
        bids.bidsprov(bidsses, source, runid, datasource.datatype, [target] if target.is_file() else [])

        # Check the output
        if not target.is_file():
            LOGGER.error(f"Output file not found: {target}")
            continue

        # Load/copy over the source meta-data
        sidecar  = target.with_suffix('').with_suffix('.json')
        metadata = bids.updatemetadata(datasource, sidecar, run['meta'], meta)
        if metadata:
            with sidecar.open('w') as json_fid:
                json.dump(metadata, json_fid, indent=4)

        # Add an entry to the scans_table (we typically don't have useful data to put there)
        if 'derivatives' not in bidsses.parts:
            acq_time = dateutil.parser.parse(f"1925-01-01T{metadata.get('AcquisitionTime', '')}")
            scans_table.loc[target.relative_to(bidsses).as_posix(), 'acq_time'] = acq_time.isoformat()

    # Write the scans_table to disk
    LOGGER.verbose(f"Writing data to: {scans_tsv}")
    scans_table.replace('','n/a').to_csv(scans_tsv, sep='\t', encoding='utf-8', na_rep='n/a')
