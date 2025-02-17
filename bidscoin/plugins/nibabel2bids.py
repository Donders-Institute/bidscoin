"""The nibabel2bids plugin wraps around the flexible nibabel (https://nipy.org/nibabel) tool to convert a wide variety
of data formats into NIfTI-files. Currently, the default template bidsmap is tailored to NIfTI source data only
(but this can readily be extended), and BIDS sidecar files are not automatically produced by nibabel"""

import logging
import dateutil.parser
import json
import pandas as pd
import nibabel as nib
from bids_validator import BIDSValidator
from typing import Union
from pathlib import Path
from bidscoin import bids, is_hidden
from bidscoin.bids import BidsMap, DataFormat, Plugin
from bidscoin.plugins import PluginInterface

try:
    from nibabel.testing import data_path
except ImportError:
    from importlib.resources import files           # PY38: from importlib_resources import files ???
    data_path = files('nibabel')/'tests'/'data'

LOGGER = logging.getLogger(__name__)

# The default/fallback options that are set when installing/using the plugin
OPTIONS = Plugin({'ext': '.nii.gz',                                         # The (nibabel) file extension of the output data, i.e. ``.nii.gz`` or ``.nii``
                  'meta': ['.json', '.tsv', '.tsv.gz', '.bval', '.bvec']})  # The file extensions of the equally named metadata sourcefiles that are copied over as BIDS sidecar files


class Interface(PluginInterface):

    def test(self, options: Plugin=OPTIONS) -> int:
        """
        Performs a nibabel test

        :param options: A dictionary with the plugin options, e.g. taken from the bidsmap.plugins['nibabel2bids']
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
            assert self.has_support(niifile) == 'Nibabel'
            assert str(self.get_attribute('Nibabel', niifile, 'descrip', options)) == "b'spm - 3D normalized'"

        except Exception as nibabelerror:

            LOGGER.error(f"Nibabel error:\n{nibabelerror}")
            return 1

        return 0

    def has_support(self, file: Path, dataformat: Union[DataFormat, str]='') -> str:
        """
        This plugin function assesses whether a sourcefile is of a supported dataformat

        :param file:        The sourcefile that is assessed
        :param dataformat:  The requested dataformat (optional requirement)
        :return:            The valid/supported dataformat of the sourcefile
        """

        if dataformat and dataformat != 'Nibabel':
            return ''

        if file.is_file() and file.suffix.lower() in sum((klass.valid_exts for klass in nib.imageclasses.all_image_classes), ('.nii',)) or file.name.endswith('.nii.gz'):
            return 'Nibabel'

        return ''

    def get_attribute(self, dataformat: Union[DataFormat, str], sourcefile: Path, attribute: str, options: Plugin) -> Union[str, int, float, list]:
        """
        This plugin supports reading attributes from DICOM and PAR dataformats

        :param dataformat:  The bidsmap-dataformat of the sourcefile, e.g. DICOM of PAR
        :param sourcefile:  The sourcefile from which the attribute value should be read
        :param attribute:   The attribute key for which the value should be read
        :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap.plugins['nibabel2bids']
        :return:            The retrieved attribute value
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

    def bidscoiner(self, session: Path, bidsmap: BidsMap, bidsses: Path) -> None:
        """
        The bidscoiner plugin to convert the session Nibabel source-files into BIDS-valid NIfTI-files in the
        corresponding bids session-folder

        :param session: The full-path name of the subject/session source folder
        :param bidsmap: The full mapping heuristics from the bidsmap YAML-file
        :param bidsses: The full-path name of the BIDS output `sub-/ses-` folder
        """

        # Get the subject identifiers from the bidsses folder
        subid   = bidsses.name if bidsses.name.startswith('sub-') else bidsses.parent.name
        sesid   = bidsses.name if bidsses.name.startswith('ses-') else ''
        options = bidsmap.plugins['nibabel2bids']
        runid   = ''

        # Read or create a scans_table and tsv-file
        scans_tsv = bidsses/f"{subid}{'_'+sesid if sesid else ''}_scans.tsv"
        if scans_tsv.is_file():
            scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
        else:
            scans_table = pd.DataFrame(columns=['acq_time'], dtype='str').rename_axis('filename')

        # Collect the different Nibabel source files for all files in the session
        for sourcefile in session.rglob('*'):

            # Check if the sourcefile is of a supported dataformat
            if is_hidden(sourcefile.relative_to(session)) or not (dataformat := self.has_support(sourcefile)):
                continue

            # Get a matching run from the bidsmap
            run, runid = bidsmap.get_matching_run(sourcefile, dataformat, runtime=True)

            # Check if we should ignore this run
            if run.datatype in bidsmap.options['ignoretypes']:
                LOGGER.info(f"--> Leaving out: {run.datasource}")
                bids.bidsprov(bidsses, sourcefile, run)                     # Write out empty provenance logging data
                continue

            # Check if we already know this run
            if not runid:
                LOGGER.error(f"Skipping unknown run: {run.datasource}\n-> Re-run the bidsmapper and delete {bidsses} to solve this warning")
                bids.bidsprov(bidsses, sourcefile)                          # Write out empty provenance logging data
                continue

            LOGGER.info(f"--> Coining: {run.datasource}")

            # Create the BIDS session/datatype output folder
            outfolder = bidsses/run.datatype
            outfolder.mkdir(parents=True, exist_ok=True)

            # Compose the BIDS filename using the matched run
            bidsignore = bids.check_ignore(run.datatype, bidsmap.options['bidsignore'])
            bidsname   = run.bidsname(subid, sesid, not bidsignore, runtime=True)
            bidsignore = bidsignore or bids.check_ignore(bidsname+'.json', bidsmap.options['bidsignore'], 'file')
            bidsname   = run.increment_runindex(outfolder, bidsname, scans_table)
            target     = (outfolder/bidsname).with_suffix(options.get('ext', ''))

            # Check if the bidsname is valid
            bidstest = (Path('/')/subid/sesid/run.datatype/bidsname).with_suffix('.nii').as_posix()
            isbids   = BIDSValidator().is_bids(bidstest)
            if not isbids and not bidsignore:
                LOGGER.warning(f"The '{bidstest}' output name did not pass the bids-validator test")

            # Check if file already exists (-> e.g. when a static runindex is used)
            if target.is_file():
                LOGGER.warning(f"{target} already exists and will be deleted -- check your results carefully!")
                target.unlink()

            # Save the sourcefile as a BIDS NIfTI file and write out provenance logging data
            nib.save(nib.load(sourcefile), target)
            bids.bidsprov(bidsses, sourcefile, run, [target] if target.is_file() else [])

            # Check the output
            if not target.is_file():
                LOGGER.error(f"Output file not found: {target}")
                continue

            # Load/copy over the source metadata
            sidecar  = target.with_suffix('').with_suffix('.json')
            metadata = bids.poolmetadata(run.datasource, sidecar, run.meta, options.get('meta', []))
            if metadata:
                with sidecar.open('w') as json_fid:
                    json.dump(metadata, json_fid, indent=4)

            # Add an entry to the scans_table (we typically don't have useful data to put there)
            acq_time = dateutil.parser.parse(f"1925-01-01T{metadata.get('AcquisitionTime', '')}")
            scans_table.loc[target.relative_to(bidsses).as_posix(), 'acq_time'] = acq_time.isoformat()

        if not runid:
            LOGGER.info(f"--> No {__name__} sourcedata found in: {session}")
            return

        # Write the scans_table to disk
        LOGGER.verbose(f"Writing data to: {scans_tsv}")
        scans_table.replace('','n/a').to_csv(scans_tsv, sep='\t', encoding='utf-8', na_rep='n/a')
