"""The 'spec2nii2bids' plugin is a wrapper around the recent spec2nii (https://github.com/wexeee/spec2nii) Python
library to interact with and convert MR spectroscopy source data. Presently, the spec2nii2bids plugin is a first
implementation that supports the conversion of Philips SPAR/SDAT files, Siemens Twix files and GE P-files to NIfTI,
in conjunction with BIDS sidecar files"""

import logging
import json
import pandas as pd
import dateutil.parser
from typing import Union
from bids_validator import BIDSValidator
from pathlib import Path
from bidscoin import run_command, is_hidden, bids, due, Doi
from bidscoin.bids import BidsMap, DataFormat, Plugin
from bidscoin.plugins import PluginInterface
from bidscoin.utilities import is_dicomfile, get_twixfield, get_sparfield, get_p7field

LOGGER = logging.getLogger(__name__)

# The default options that are set when installing the plugin
OPTIONS = Plugin({'command': 'spec2nii',    # Command to run spec2nii, e.g. "module add spec2nii; spec2nii" or "PATH=/opt/spec2nii/bin:$PATH; spec2nii" or /opt/spec2nii/bin/spec2nii or 'C:\"Program Files"\spec2nii\spec2nii.exe' (note the quotes to deal with the whitespace)
                  'args': None,             # Argument string that is passed to spec2nii (see spec2nii -h for more information)
                  'meta': ['.json', '.tsv', '.tsv.gz'],  # The file extensions of the equally named metadata source files that are copied over as BIDS sidecar files
                  'multiraid': 2})          # The mapVBVD argument for selecting the multiraid Twix file to load (default = 2, i.e. 2nd file)


class Interface(PluginInterface):

    def test(self, options: Plugin=OPTIONS) -> int:
        """
        This plugin shell tests the working of the spec2nii2bids plugin + given options

        :param options: A dictionary with the plugin options, e.g. taken from the bidsmap.plugins['spec2nii2bids']
        :return:        The errorcode (e.g 0 if the tool generated the expected result, > 0 if there was a tool error)
        """

        LOGGER.info('Testing the spec2nii2bids installation:')

        if 'command' not in {**OPTIONS, **options}:
            LOGGER.error(f"The expected 'command' key is not defined in the spec2nii2bids options")
            return 1
        if 'args' not in {**OPTIONS, **options}:
            LOGGER.warning(f"The expected 'args' key is not defined in the spec2nii2bids options")

        # Test the spec2nii installation
        return run_command(f"{options.get('command',OPTIONS['command'])} -v")

    def has_support(self, file: Path, dataformat: Union[DataFormat, str]='') -> str:
        """
        This plugin function assesses whether a sourcefile is of a supported dataformat

        :param file:        The sourcefile that is assessed
        :param dataformat:  The requested dataformat (optional requirement)
        :return:            The valid/supported dataformat of the sourcefile
        """

        if dataformat and dataformat not in ('Twix', 'SPAR', 'Pfile'):
            return ''

        suffix = file.suffix.lower()
        if suffix == '.dat':
            return 'Twix'
        elif suffix == '.spar':
            return 'SPAR'
        elif suffix == '.7' and not is_dicomfile(file):
            return 'Pfile'

        return ''

    def get_attribute(self, dataformat: Union[DataFormat, str], sourcefile: Path, attribute: str, options: Plugin) -> str:
        """
        This plugin function reads attributes from the supported sourcefile

        :param dataformat:  The dataformat of the sourcefile, e.g. DICOM of PAR
        :param sourcefile:  The sourcefile from which key-value data needs to be read
        :param attribute:   The attribute key for which the value needs to be retrieved
        :param options:     The bidsmap.plugins['spec2nii2bids'] dictionary with the plugin options
        :return:            The retrieved attribute value
        """

        if dataformat not in ('Twix', 'SPAR', 'Pfile'):
            return ''

        if not sourcefile.is_file():
            LOGGER.error(f"Could not find {sourcefile}")
            return ''

        if dataformat == 'Twix':

            return get_twixfield(attribute, sourcefile, options.get('multiraid', OPTIONS['multiraid']))

        if dataformat == 'SPAR':

            return get_sparfield(attribute, sourcefile)

        if dataformat == 'Pfile':

            return get_p7field(attribute, sourcefile)

        LOGGER.error(f"Unsupported MRS data-format: {dataformat}")

    @due.dcite(Doi('10.1002/mrm.29418'), description='Multi-format in vivo MR spectroscopy conversion to NIFTI', tags=['reference-implementation'])
    def bidscoiner(self, session: Path, bidsmap: BidsMap, bidsses: Path) -> None:
        """
        This wrapper function around spec2nii converts the MRS data in the session folder and saves it in the bidsfolder.
        Each saved datafile should be accompanied by a json sidecar file. The bidsmap options for this plugin can be found in:

        bidsmap.plugins['spec2nii2bids']

        :param session: The full-path name of the subject/session raw data source folder
        :param bidsmap: The full mapping heuristics from the bidsmap YAML-file
        :param bidsses: The full-path name of the BIDS output `sub-/ses-` folder
        """

        # Get started
        subid   = bidsses.name if bidsses.name.startswith('sub-') else bidsses.parent.name
        sesid   = bidsses.name if bidsses.name.startswith('ses-') else ''
        options = bidsmap.plugins['spec2nii2bids']
        runid   = ''

        # Read or create a scans_table and tsv-file
        scans_tsv = bidsses/f"{subid}{'_'+sesid if sesid else ''}_scans.tsv"
        if scans_tsv.is_file():
            scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
        else:
            scans_table = pd.DataFrame(columns=['acq_time'], dtype='str')
            scans_table.index.name = 'filename'

        # Loop over all MRS source data files and convert them to BIDS
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
            target     = (outfolder/bidsname).with_suffix('.nii.gz')

            # Check if the bidsname is valid
            bidstest = (Path('/')/subid/sesid/run.datatype/bidsname).with_suffix('.nii').as_posix()
            isbids   = BIDSValidator().is_bids(bidstest)
            if not isbids and not bidsignore:
                LOGGER.warning(f"The '{bidstest}' output name did not pass the bids-validator test")

            # Check if file already exists (-> e.g. when a static runindex is used)
            if target.is_file():
                LOGGER.warning(f"{outfolder/bidsname}.* already exists and will be deleted -- check your results carefully!")
                for ext in ('.nii.gz', '.nii', '.json', '.tsv', '.tsv.gz', '.bval', '.bvec'):
                    target.with_suffix('').with_suffix(ext).unlink(missing_ok=True)

            # Run spec2nii to convert the source-files in the run folder to NIfTI's in the BIDS-folder
            arg  = ''
            args = options.get('args', OPTIONS['args']) or ''
            if dataformat == 'SPAR':
                dformat = 'philips'
                arg     = f'"{sourcefile.with_suffix(".SDAT")}"'
            elif dataformat == 'Twix':
                dformat = 'twix'
                arg     = '-e image'
            elif dataformat == 'Pfile':
                dformat = 'ge'
            else:
                LOGGER.error(f"Unsupported dataformat: {dataformat}")
                return
            command = options.get('command', 'spec2nii')
            errcode = run_command(f'{command} {dformat} -j -f "{bidsname}" -o "{outfolder}" {args} {arg} "{sourcefile}"')
            bids.bidsprov(bidsses, sourcefile, run, [target] if target.is_file() else [])
            if not target.is_file():
                if not errcode:
                    LOGGER.error(f"Output file not found: {target}")
                continue

            # Load/copy over and adapt the newly produced json sidecar-file
            sidecar  = target.with_suffix('').with_suffix('.json')
            metadata = bids.poolmetadata(run.datasource, sidecar, run.meta, options.get('meta',[]))
            if metadata:
                with sidecar.open('w') as json_fid:
                    json.dump(metadata, json_fid, indent=4)

            # Parse the acquisition time from the source header or else from the json file (NB: assuming the source file represents the first acquisition)
            if not bidsignore:
                acq_time   = ''
                attributes = run.datasource.attributes
                if dataformat == 'SPAR':
                    acq_time = attributes('scan_date')
                elif dataformat == 'Twix':
                    acq_time = f"{attributes('AcquisitionDate')}T{attributes('AcquisitionTime')}"
                elif dataformat == 'Pfile':
                    acq_time = f"{attributes('rhr_rh_scan_date')}T{attributes('rhr_rh_scan_time')}"
                if not acq_time or acq_time == 'T':
                    acq_time = f"1925-01-01T{metadata.get('AcquisitionTime','')}"
                try:
                    acq_time = dateutil.parser.parse(acq_time)
                    if bidsmap.options.get('anon','y') in ('y','yes'):
                        acq_time = acq_time.replace(year=1925, month=1, day=1)      # Privacy protection (see BIDS specification)
                    acq_time = acq_time.isoformat()
                except Exception as jsonerror:
                    LOGGER.warning(f"Could not parse the acquisition time from: {sourcefile}\n{jsonerror}")
                    acq_time = 'n/a'
                scans_table.loc[target.relative_to(bidsses).as_posix(), 'acq_time'] = acq_time

        if not runid:
            LOGGER.info(f"--> No {__name__} sourcedata found in: {session}")
            return

        # Write the scans_table to disk
        LOGGER.verbose(f"Writing acquisition time data to: {scans_tsv}")
        scans_table.sort_values(by=['acq_time', 'filename'], inplace=True)
        scans_table.replace('','n/a').to_csv(scans_tsv, sep='\t', encoding='utf-8', na_rep='n/a')
