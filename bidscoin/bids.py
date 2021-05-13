"""
Module with helper functions

Some functions are derived from dac2bids.py from Daniel Gomez 29.08.2016
https://github.com/dangom/dac2bids/blob/master/dac2bids.py

@author: Marcel Zwiers
"""
import re
import logging
import tempfile
import tarfile
import zipfile
from functools import lru_cache
from pydicom import dcmread, fileset, datadict
from nibabel.parrec import parse_PAR_header
from distutils.dir_util import copy_tree
from typing import Union, List, Tuple
from pathlib import Path
try:
    from bidscoin import bidscoin, dicomsort
except ImportError:
    import bidscoin, dicomsort  # This should work if bidscoin was not pip-installed
from ruamel.yaml import YAML
yaml = YAML()

LOGGER = logging.getLogger(__name__)

# Define BIDScoin datatypes
bidscoindatatypes = ('fmap', 'anat', 'func', 'perf', 'dwi', 'pet', 'meg', 'eeg', 'ieeg', 'beh')           # NB: get_matching_run() uses this order to search for a match. TODO: sync with the modalities.yaml schema
ignoredatatype    = 'exclude'
unknowndatatype   = 'extra_data'

# Define the default paths
schema_folder     = Path(__file__).parent/'schema'
heuristics_folder = Path(__file__).parent/'heuristics'
bidsmap_template  = heuristics_folder/'bidsmap_template.yaml'

# Read the BIDS schema datatypes and entities
bidsdatatypes = {}
for _datatypefile in (schema_folder/'datatypes').glob('*.yaml'):
    with _datatypefile.open('r') as stream:
        bidsdatatypes[_datatypefile.stem] = yaml.load(stream)
with (schema_folder/'entities.yaml').open('r') as _stream:
    entities = yaml.load(_stream)


def is_dicomfile(file: Path) -> bool:
    """
    Checks whether a file is a DICOM-file. It uses the feature that Dicoms have the string DICM hardcoded at offset 0x80.

    :param file:    The full pathname of the file
    :return:        Returns true if a file is a DICOM-file
    """

    if file.is_file():
        if file.stem.startswith('.'):
            LOGGER.warning(f'File is hidden: {file}')
        with file.open('rb') as dicomfile:
            dicomfile.seek(0x80, 1)
            if dicomfile.read(4) == b'DICM':
                return True
        LOGGER.debug(f"Reading non-standard DICOM file: {file}")
        if file.suffix.lower() in ('.ima','.dcm','.dicm','.dicom',''):           # Avoid memory problems when reading a very large (e.g. EEG) source file
            dicomdata = dcmread(file, force=True)               # The DICM tag may be missing for anonymized DICOM files
            return 'Modality' in dicomdata
        # else:
        #     dicomdata = dcmread(file)                         # NB: Raises an error for non-DICOM files
        #     return 'Modality' in dicomdata

    return False


def is_dicomfile_siemens(file: Path) -> bool:
    """
    Checks whether a file is a *SIEMENS* DICOM-file. All Siemens Dicoms contain a dump of the
    MrProt structure. The dump is marked with a header starting with 'ASCCONV BEGIN'. Though
    this check is not foolproof, it is very unlikely to fail.

    :param file:    The full pathname of the file
    :return:        Returns true if a file is a Siemens DICOM-file
    """

    return b'ASCCONV BEGIN' in file.open('rb').read()


def is_parfile(file: Path) -> bool:
    """
    Rudimentary check (on file extensions and whether it exists) whether a file is a Philips PAR file

    :param file:    The full pathname of the file
    :return:        Returns true if a file is a Philips PAR-file
    """

    # TODO: Implement a proper check, e.g. using nibabel
    if file.is_file() and file.suffix in ('.PAR', '.par', '.XML', '.xml'):
        return True
    else:
        return False


def unpack(sourcefolder: Path, subprefix: str='sub-', sesprefix: str='ses-', wildcard: str='*', workfolder: Path='') -> (Path, bool):
    """
    Unpacks and sorts DICOM files in sourcefolder to a temporary folder if sourcefolder contains a DICOMDIR file or .tar.gz, .gz or .zip files

    :param sourcefolder:    The full pathname of the folder with the source data
    :param subprefix:       The optional subprefix (e.g. 'sub-'). Used to parse the subid
    :param sesprefix:       The optional sesprefix (e.g. 'ses-'). Used to parse the sesid
    :param wildcard:        A glob search pattern to select the tarballed/zipped files
    :param workfolder:      A root folder for temporary data
    :return:                A tuple with the full pathname of the source or workfolder and a workdir-path or False when the data is not unpacked in a temporary folder
    """

    # Search for zipped/tarballed files
    packedfiles = []
    packedfiles.extend(sourcefolder.glob(f"{wildcard}.tar"))
    packedfiles.extend(sourcefolder.glob(f"{wildcard}.tar.?z"))
    packedfiles.extend(sourcefolder.glob(f"{wildcard}.tar.bz2"))
    packedfiles.extend(sourcefolder.glob(f"{wildcard}.zip"))

    # Check if we are going to do unpacking and/or sorting
    if packedfiles or (sourcefolder/'DICOMDIR').is_file():

        # Create a (temporary) sub/ses workfolder for unpacking the data
        if not workfolder:
            workfolder = tempfile.mkdtemp()
        workfolder   = Path(workfolder)
        subid, sesid = get_subid_sesid(sourcefolder/'dum.my', subprefix=subprefix, sesprefix=sesprefix)
        subid, sesid = subid.replace('sub-', subprefix), sesid.replace('ses-', sesprefix)
        worksubses   = workfolder/subid/sesid
        worksubses.mkdir(parents=True, exist_ok=True)

        # Copy everything over to the workfolder
        LOGGER.info(f"Making temporary copy: {sourcefolder} -> {worksubses}")
        copy_tree(str(sourcefolder), str(worksubses))     # Older python versions don't support PathLib

        # Unpack the zip/tarballed files in the temporary folder
        for packedfile in [worksubses/packedfile.name for packedfile in packedfiles]:
            LOGGER.info(f"Unpacking: {packedfile.name} -> {worksubses}")
            ext = packedfile.suffixes
            if ext[-1] == '.zip':
                with zipfile.ZipFile(packedfile, 'r') as zip_fid:
                    zip_fid.extractall(worksubses)
            elif '.tar' in ext:
                with tarfile.open(packedfile, 'r') as tar_fid:
                    tar_fid.extractall(worksubses)

            # Sort the DICOM files immediately (to avoid name collisions)
            dicomsort.sortsessions(worksubses)

        # Sort the DICOM files if not sorted yet (e.g. DICOMDIR)
        dicomsort.sortsessions(worksubses)

        return worksubses, workfolder

    else:

        return sourcefolder, False


def get_dicomfile(folder: Path, index: int=0) -> Path:
    """
    Gets a dicom-file from the folder (supports DICOMDIR)

    :param folder:  The full pathname of the folder
    :param index:   The index number of the dicom file
    :return:        The filename of the first dicom-file in the folder.
    """

    if (folder/'DICOMDIR').is_file():
        dicomdir = fileset.FileSet(folder/'DICOMDIR')
        files    = [Path(file.path) for file in dicomdir]
    else:
        files = sorted(folder.iterdir())

    idx = 0
    for file in files:
        if file.stem.startswith('.'):
            LOGGER.warning(f'Ignoring hidden file: {file}')
            continue
        if is_dicomfile(file):
            if idx == index:
                return file
            else:
                idx += 1

    return Path()


def get_parfiles(folder: Path) -> List[Path]:
    """
    Gets a Philips PAR-file from the folder

    :param folder:  The full pathname of the folder
    :return:        The filename of the first PAR-file in the folder.
    """

    parfiles = []
    for file in sorted(folder.iterdir()):
        if is_parfile(file):
            parfiles.append(file)

    return parfiles


def load_bidsmap(yamlfile: Path, folder: Path=Path(), report: Union[bool,None]=True) -> Tuple[dict, Path]:
    """
    Read the mapping heuristics from the bidsmap yaml-file. If yamlfile is not fullpath, then 'folder' is first searched before
    the default 'heuristics'. If yamfile is empty, then first 'bidsmap.yaml' is searched for, them 'bidsmap_template.yaml'. So fullpath
    has precendence over folder and bidsmap.yaml has precedence over bidsmap_template.yaml

    :param yamlfile:    The full pathname or basename of the bidsmap yaml-file. If None, the default bidsmap_template.yaml file in the heuristics folder is used
    :param folder:      Only used when yamlfile=basename or None: yamlfile is then first searched for in folder and then falls back to the ./heuristics folder (useful for centrally managed template yaml-files)
    :param report:      Report log.info when reading a file
    :return:            Tuple with (1) ruamel.yaml dict structure, with all options, BIDS mapping heuristics, labels and attributes, etc and (2) the fullpath yaml-file
    """

    # Input checking
    if not folder.name:
        folder = heuristics_folder
    if not yamlfile.name:
        yamlfile = folder/'bidsmap.yaml'
        if not yamlfile.is_file():
            yamlfile = bidsmap_template

    # Add a standard file-extension if needed
    if not yamlfile.suffix:
        yamlfile = yamlfile.with_suffix('.yaml')

    # Get the full path to the bidsmap yaml-file
    if len(yamlfile.parents) == 1:
        if (folder/yamlfile).is_file():
            yamlfile = folder/yamlfile
        else:
            yamlfile = heuristics_folder/yamlfile

    if not yamlfile.is_file():
        if report:
            LOGGER.info(f"No existing bidsmap file found: {yamlfile}")
        return dict(), yamlfile
    elif report:
        LOGGER.info(f"Reading: {yamlfile}")

    # Read the heuristics from the bidsmap file
    with yamlfile.open('r') as stream:
        bidsmap = yaml.load(stream)

    # Issue a warning if the version in the bidsmap YAML-file is not the same as the bidscoin version
    if 'bidscoin' in bidsmap['Options'] and 'version' in bidsmap['Options']['bidscoin']:
        bidsmapversion = bidsmap['Options']['bidscoin']['version']
    elif 'version' in bidsmap['Options']:                       # Handle legacy bidsmaps
        bidsmapversion = bidsmap['Options']['version']
    else:
        bidsmapversion = 'Unknown'
    if bidsmapversion != bidscoin.version() and report:
        LOGGER.warning(f'BIDScoiner version conflict: {yamlfile} was created using version {bidsmapversion}, but this is version {bidscoin.version()}')

    # Add missing provenance info, run dictionaries and bids entities
    run_ = get_run_()
    for dataformat in bidsmap:
        if dataformat in ('Options','PlugIns'): continue        # Handle legacy bidsmaps (-> 'PlugIns')
        if not bidsmap[dataformat]:             continue
        for datatype in bidsmap[dataformat]:
            if not isinstance(bidsmap[dataformat][datatype], list): continue
            for index, run in enumerate(bidsmap[dataformat][datatype]):

                # Add missing provenance info
                if not run.get('provenance'):
                    run['provenance'] = f"sub-unknown/ses-unknown/{dataformat}_{datatype}_id{index+1:03}"

                # Add missing run dictionaries (e.g. "meta" or "filesystem")
                for key, val in run_.items():
                    if key not in run or not run[key]:
                        run[key] = val

                # Add missing bids entities
                for typegroup in bidsdatatypes.get(datatype,[]):
                    if run['bids']['suffix'] in typegroup['suffixes']:      # run_found = True
                        for entityname in typegroup['entities']:
                            entitykey = entities[entityname]['entity']
                            if entitykey not in run['bids'] and entitykey not in ('sub','ses'):
                                LOGGER.debug(f"Adding missing {dataformat}/{datatype} entity key: {entitykey}")
                                run['bids'][entitykey] = ''

    # Make sure we get a proper dictionary with plugins
    if not bidsmap['Options'].get('plugins'):
        bidsmap['Options']['plugins'] = {}
    for plugin, options in bidsmap['Options']['plugins'].items():
        if not bidsmap['Options']['plugins'].get(plugin):
            bidsmap['Options']['plugins'][plugin] = {}

    # Validate the bidsmap entries
    check_bidsmap(bidsmap, report)

    return bidsmap, yamlfile


def save_bidsmap(filename: Path, bidsmap: dict) -> None:
    """
    Save the BIDSmap as a YAML text file

    :param filename:    Full pathname of the bidsmap file
    :param bidsmap:     Full bidsmap data structure, with all options, BIDS labels and attributes, etc
    :return:
    """

    # Validate the bidsmap entries
    if not check_bidsmap(bidsmap, False):
        LOGGER.warning('Bidsmap values are invalid according to the BIDS specification')

    LOGGER.info(f"Writing bidsmap to: {filename}")
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open('w') as stream:
        yaml.dump(bidsmap, stream)

    # See if we can reload it, i.e. whether it is valid yaml...
    try:
        load_bidsmap(filename, report=None)
    except Exception as bidsmaperror:
        # Just trying again seems to help? :-)
        with filename.open('w') as stream:
            yaml.dump(bidsmap, stream)
        try:
            load_bidsmap(filename, report=None)
        except Exception as bidsmaperror:
            LOGGER.exception(f'{bidsmaperror}\nThe saved output bidsmap does not seem to be valid YAML, please check {filename}, e.g. by way of an online yaml validator, such as https://yamlchecker.com/')


def check_bidsmap(bidsmap: dict, validate: bool=True) -> bool:
    """
    Check the bidsmap for required and optional entitities using the BIDS schema files

    :param bidsmap:     Full bidsmap data structure, with all options, BIDS labels and attributes, etc
    :param validate:    Validate if all bids-keys and values are present according to the BIDS schema specifications
    :return:            True if the bidsmap is valid, otherwise False
    """

    valid = True

    # Check all the runs in the bidsmap
    for dataformat in bidsmap:
        if dataformat in ('Options','PlugIns'): continue    # Handle legacy bidsmaps (-> 'PlugIns'). TODO: Check Options
        if not bidsmap[dataformat]:             continue
        for datatype in bidsmap[dataformat]:
            if not isinstance(bidsmap[dataformat][datatype], list): continue
            for run in bidsmap[dataformat][datatype]:
                valid = check_run(datatype, run, validate) and valid

    return valid


def parse_x_protocol(pattern: str, dicomfile: Path) -> str:
    """
    Siemens writes a protocol structure as text into each DICOM file.
    This structure is necessary to recreate a scanning protocol from a DICOM,
    since the DICOM information alone wouldn't be sufficient.

    :param pattern:     A regexp expression: '^' + pattern + '\t = \t(.*)\\n'
    :param dicomfile:   The full pathname of the dicom-file
    :return:            The string extracted values from the dicom-file according to the given pattern
    """

    if not is_dicomfile_siemens(dicomfile):
        LOGGER.warning(f"Parsing {pattern} may fail because {dicomfile} does not seem to be a Siemens DICOM file")

    regexp = '^' + pattern + '\t = \t(.*)\n'
    regex  = re.compile(regexp.encode('utf-8'))

    with dicomfile.open('rb') as openfile:
        for line in openfile:
            match = regex.match(line)
            if match:
                return match.group(1).decode('utf-8')

    LOGGER.warning(f"Pattern: '{regexp.encode('unicode_escape').decode()}' not found in: {dicomfile}")
    return ''


# Profiling shows this is currently the most expensive function, so therefore the (primitive but effective) _DICOMDICT_CACHE optimization
_DICOMDICT_CACHE = None
_DICOMFILE_CACHE = None
@lru_cache(maxsize=4096)
def get_dicomfield(tagname: str, dicomfile: Path) -> Union[str, int]:
    """
    Robustly extracts a DICOM field/tag from a dictionary or from vendor specific fields

    :param tagname:     Name of the DICOM field
    :param dicomfile:   The full pathname of the dicom-file
    :return:            Extracted tag-values from the dicom-file
    """

    global _DICOMDICT_CACHE, _DICOMFILE_CACHE

    if not dicomfile.name:
        return ''

    if not dicomfile.is_file():
        LOGGER.warning(f"{dicomfile} not found")
        value = ''

    elif not is_dicomfile(dicomfile):
        LOGGER.warning(f"{dicomfile} is not a DICOM file, cannot read {tagname}")
        value = ''

    else:
        try:
            if dicomfile != _DICOMFILE_CACHE:
                dicomdata = dcmread(dicomfile, force=True)          # The DICM tag may be missing for anonymized DICOM files
                if 'Modality' not in dicomdata:
                    raise ValueError(f'Cannot read {dicomfile}')
                _DICOMDICT_CACHE = dicomdata
                _DICOMFILE_CACHE = dicomfile
            else:
                dicomdata = _DICOMDICT_CACHE

            value = dicomdata.get(tagname, '')

            # Try a recursive search
            if not value:
                for elem in dicomdata.iterall():
                    if tagname in (elem.name, elem.keyword):
                        value = elem.value
                        break

        except OSError:
            LOGGER.warning(f'Cannot read {tagname} from {dicomfile}')
            value = ''

        except Exception as dicomerror:
            try:
                value = parse_x_protocol(tagname, dicomfile)

            except Exception as dicomerror:
                LOGGER.warning(f'Could not parse {tagname} from {dicomfile}\n{dicomerror}')
                value = ''

    # Cast the dicom datatype to int or str (i.e. to something that yaml.dump can handle)
    if isinstance(value, int):
        return int(value)
    elif value is None:
        return ''
    else:
        return str(value)               # If it's a MultiValue type then flatten it


# Profiling shows this is currently the most expensive function, so therefore the (primitive but effective) _PARDICT_CACHE optimization
_PARDICT_CACHE = None
_PARFILE_CACHE = None
@lru_cache(maxsize=4096)
def get_parfield(tagname: str, parfile: Path) -> Union[str, int]:
    """
    Extracts the value from a PAR/XML field

    :param tagname: Name of the PAR/XML field
    :param parfile: The full pathname of the PAR/XML file
    :return:        Extracted tag-values from the PAR/XML file
    """

    global _PARDICT_CACHE, _PARFILE_CACHE

    if not parfile.name:
        return ''

    if not parfile.is_file():
        LOGGER.warning(f"{parfile} not found")
        value = ''

    elif not is_parfile(parfile):
        LOGGER.warning(f"{parfile} is not a PAR/XML file, cannot read {tagname}")
        value = ''

    else:
        try:
            if parfile != _PARFILE_CACHE:
                pardict = parse_PAR_header(parfile.open('r'))
                if 'series_type' not in pardict[0]:
                    raise ValueError(f'Cannot read {parfile}')
                _PARDICT_CACHE = pardict
                _PARFILE_CACHE = parfile
            else:
                pardict = _PARDICT_CACHE
            value = pardict[0].get(tagname, '')

        except OSError:
            LOGGER.warning(f'Cannot read {tagname} from {parfile}')
            value = ''

        except Exception as parerror:
            LOGGER.warning(f'Could not parse {tagname} from {parfile}\n{parerror}')
            value = ''

    # Cast the dicom datatype to int or str (i.e. to something that yaml.dump can handle)
    if isinstance(value, int):
        return int(value)
    elif value is None:
        return ''
    else:
        return str(value)               # If it's a MultiValue type then flatten it


def get_dataformat(source: Path) -> str:
    """
    Wrapper to get the dataformat of a source file or folder

    :param source:  The full pathname of a (e.g. DICOM or PAR/XML) session directory or of a source file
    :return:        'DICOM' if sourcefile is a DICOM-file or 'PAR' when it is a PAR/XML file

    TODO: replace with a dataformat class
    """

    # If source is a session directory, get a sourcefile
    try:
        if source.is_dir():

            # Try to see if we can find DICOM files
            sourcedirs = bidscoin.lsdirs(source)
            for sourcedir in sourcedirs:
                sourcefile = get_dicomfile(sourcedir)
                if sourcefile.name:
                    return 'DICOM'

            # Try to see if we can find PAR/XML files
            sourcefiles = get_parfiles(source)
            if sourcefiles:
                return 'PAR'

        # If we don't know the dataformat, just try
        if is_dicomfile(source):
            return 'DICOM'

        if is_parfile(source):
            return 'PAR'

    except OSError as nosource:
        LOGGER.warning(nosource)

    LOGGER.debug(f"Cannot determine the dataformat of: {source}")
    return ''


def get_sourcevalue(tagname: str, sourcefile: Union[Path, dict], dataformat: str= '') -> Union[str, int, None]:
    """
    Gets the tagname header-attribute or tagname filesystem-property

    :param tagname:     Name of the field in the sourcefile
    :param sourcefile:  The full pathname of the (e.g. DICOM or PAR/XML) sourcefile or a run-item with a run['provenance'] field (needed for dataformat=='FileSystem', tag=='nrfiles')
    :param dataformat:  The information source in the bidsmap that is used, e.g. 'DICOM'. Use 'FileSystem' to read the run['filesystem'] values
    :return:            Extracted tag-values from the sourcefile

    TODO: replace with a dataformat class
    """

    if isinstance(sourcefile, dict):
        run        = sourcefile
        sourcefile = Path(run['provenance'])
    else:
        run        = get_run_(sourcefile)
    if not sourcefile.name:
        return

    if not dataformat:
        dataformat = get_dataformat(sourcefile)

    if dataformat == 'DICOM':
        return get_dicomfield(tagname, sourcefile)

    if dataformat == 'PAR':
        return get_parfield(tagname, sourcefile)

    if dataformat == 'FileSystem':
        if tagname == 'path':
            return str(sourcefile.parent)
        if tagname == 'name':
            return sourcefile.name
        if tagname == 'size' and sourcefile.is_file():
            # Convert the size in bytes into a human-readable B, KB, MG, GB, TB format
            size  = sourcefile.stat().st_size                   # Size in bytes
            power = 2**10                                       # 2**10 = 1024
            label = {0: '', 1: 'k', 2: 'M', 3: 'G', 4: 'T'}     # Standard labels for powers of 1024
            n = 0                                               # The power/label index
            while size > power and n < len(label):
                size /= power
                n    += 1
            return f"{size:.2f} {label[n]}B"
        if tagname == 'nrfiles' and sourcefile.is_file():
            def match(file): return ((match_attribute(file.parent,         run['filesystem']['path']) or not run['filesystem']['path']) and
                                     (match_attribute(file.name,           run['filesystem']['name']) or not run['filesystem']['name']) and
                                     (match_attribute(file.stat().st_size, run['filesystem']['size']) or not run['filesystem']['size']))
            return len([file for file in sourcefile.parent.glob('*') if match(file)])


def add_prefix(prefix: str, tag: str) -> str:
    """
    Simple function to account for optional BIDS tags in the bids file names, i.e. it prefixes 'prefix' only when tag is not empty

    :param prefix:  The prefix (e.g. '_ses-')
    :param tag:     The tag (e.g. 'medication')
    :return:        The tag with the leading prefix (e.g. '_ses-medication') or just the empty tag ''
    """

    if tag:
        tag = prefix + str(tag)
    else:
        tag = ''

    return tag


def strip_suffix(run: dict) -> dict:
    """
    Certain attributes such as SeriesDescriptions (but not ProtocolName!?) may get a suffix like '_SBRef' from the vendor,
    try to strip it off from the BIDS labels

    :param run: The run with potentially added suffixes that are the same as the BIDS suffixes
    :return:    The run with these suffixes removed
    """

    # See if we have a suffix for this datatype
    if 'suffix' in run['bids'] and run['bids']['suffix']:
        suffix = run['bids']['suffix'].lower()
    else:
        return run

    # See if any of the BIDS labels ends with the same suffix. If so, then remove it
    for key in run['bids']:
        if key == 'suffix':
            continue
        if isinstance(run['bids'][key], str) and run['bids'][key].lower().endswith(suffix):
            run['bids'][key] = run['bids'][key][0:-len(suffix)]       # NB: This will leave the added '_' and '.' characters, but they will be taken out later (as they are not BIDS-valid)

    return run


def cleanup_value(label: str) -> str:
    """
    Converts a given label to a cleaned-up label that can be used as a BIDS label. Remove leading and trailing spaces;
    convert other spaces, special BIDS characters and anything that is not an alphanumeric to a ''. This will for
    example map "Joe's reward_task" to "Joesrewardtask"

    :param label:   The given label that potentially contains undesired characters
    :return:        The cleaned-up / BIDS-valid label
    """

    if label is None:
        return ''
    if not isinstance(label, str):
        return label

    special_characters = (' ', '_', '-','.')

    for special in special_characters:
        label = label.strip().replace(special, '')

    return re.sub(r'(?u)[^-\w.]', '', label)


def dir_bidsmap(bidsmap: dict, dataformat: str) -> List[Path]:
    """
    Make a provenance list of all the runs in the bidsmap[dataformat]

    :param bidsmap:     The bidsmap, with all the runs in it
    :param dataformat:  The information source in the bidsmap that is used, e.g. 'DICOM'
    :return:            List of all provenances
    """

    provenance = []
    for datatype in bidscoindatatypes + (unknowndatatype, ignoredatatype):
        if bidsmap.get(dataformat) and bidsmap[dataformat].get(datatype):
            for run in bidsmap[dataformat][datatype]:
                if not run['provenance']:
                    LOGGER.warning(f'The bidsmap run {datatype} run does not contain provenance data')
                else:
                    provenance.append(Path(run['provenance']))

    provenance.sort()

    return provenance


def get_run_(provenance: Union[str, Path]='') -> dict:
    """
    Get an empty run-item with the proper structure and provenance info

    :param provenance:  The unique provance that is use to identify the run
    :return:            The empty run
    """

    return dict(provenance = str(provenance),
                filesystem = {'path':'', 'name':'', 'size':'', 'nrfiles':''},
                attributes = {},
                bids       = {},
                meta       = {})


def get_run(bidsmap: dict, dataformat: str, datatype: str, suffix_idx: Union[int, str], sourcefile: Path=Path()) -> dict:
    """
    Find the (first) run in bidsmap[dataformat][bidsdatatype] with run['bids']['suffix_idx'] == suffix_idx

    :param bidsmap:     This could be a template bidsmap, with all options, BIDS labels and attributes, etc
    :param dataformat:  The information source in the bidsmap that is used, e.g. 'DICOM'
    :param datatype:    The datatype in which a matching run is searched for (e.g. 'anat')
    :param suffix_idx:  The name of the suffix that is searched for (e.g. 'bold') or the datatype index number
    :param sourcefile:  The name of the sourcefile. If given, the bidsmap dynamic values are read from file
    :return:            The clean (filled) run item in the bidsmap[dataformat][bidsdatatype] with the matching suffix_idx,
                        otherwise a dict with empty attributes & bids keys
    """

    if not dataformat:
        dataformat = get_dataformat(sourcefile)

    runs = bidsmap.get(dataformat, {}).get(datatype, [])
    if not runs:
        runs = []
    for index, run in enumerate(runs):
        if index == suffix_idx or run['bids']['suffix'] == suffix_idx:

            # Get a clean run (remove comments to avoid overly complicated commentedMaps from ruamel.yaml)
            run_ = get_run_(str(sourcefile.resolve()))

            for filekey, filevalue in run['filesystem'].items():
                run_['filesystem'][filekey] = filevalue

            for attrkey, attrvalue in run['attributes'].items():
                if sourcefile.name:
                    run_['attributes'][attrkey] = get_sourcevalue(attrkey, sourcefile, dataformat)
                else:
                    run_['attributes'][attrkey] = attrvalue

            for bidskey, bidsvalue in run['bids'].items():
                run_['bids'][bidskey] = get_dynamicvalue(bidsvalue, sourcefile)

            for metakey, metavalue in run['meta'].items():
                run_['meta'][metakey] = get_dynamicvalue(metavalue, sourcefile, cleanup=False)

            return run_

    LOGGER.warning(f"'{datatype}' run with suffix_idx '{suffix_idx}' not found in bidsmap['{dataformat}']")
    return get_run_(str(sourcefile.resolve()))


def delete_run(bidsmap: dict, dataformat: str, datatype: str, provenance: Path) -> None:
    """
    Delete a run from the BIDS map

    :param bidsmap:     Full bidsmap data structure, with all options, BIDS labels and attributes, etc
    :param dataformat:  The information source in the bidsmap that is used, e.g. 'DICOM'
    :param datatype:    The datatype that is used, e.g. 'anat'
    :param provenance:  The unique provance that is use to identify the run
    :return:
    """

    if not dataformat:
        dataformat = get_dataformat(provenance)

    for index, run in enumerate(bidsmap[dataformat][datatype]):
        if run['provenance'] == str(provenance):
            del bidsmap[dataformat][datatype][index]


def append_run(bidsmap: dict, dataformat: str, datatype: str, run: dict, clean: bool=True) -> None:
    """
    Append a run to the BIDS map

    :param bidsmap:     Full bidsmap data structure, with all options, BIDS labels and attributes, etc
    :param dataformat:  The information source in the bidsmap that is used, e.g. 'DICOM'. If empty then it is determined from the provenance
    :param datatype:    The datatype that is used, e.g. 'anat'
    :param run:         The run (listitem) that is appended to the datatype
    :param clean:       A boolean to clean-up commentedMap fields
    :return:
    """

    if not dataformat:
        dataformat = get_dataformat(run['provenance'])

    # Copy the values from the run to an empty dict
    if clean:
        run_ = get_run_(run['provenance'])

        for item in run_.keys():
            if item == 'provenance': continue
            for key, value in run[item].items():
                run_[item][key] = value

        run = run_

    if not bidsmap.get(dataformat):
        bidsmap[dataformat] = {}
    elif not bidsmap.get(dataformat).get(datatype):
        bidsmap[dataformat][datatype] = [run]
    else:
        bidsmap[dataformat][datatype].append(run)


def update_bidsmap(bidsmap: dict, source_datatype: str, provenance: Path, target_datatype: str, run: dict, dataformat: str, clean: bool=True) -> None:
    """
    Update the BIDS map if the datatype changes:
    1. Remove the source run from the source datatype section
    2. Append the (cleaned) target run to the target datatype section

    Else:
    1. Use the provenance to look-up the index number in that datatype
    2. Replace the run

    :param bidsmap:             Full bidsmap data structure, with all options, BIDS labels and attributes, etc
    :param source_datatype:     The current datatype name, e.g. 'anat'
    :param provenance:          The unique provance that is use to identify the run
    :param target_datatype:     The datatype name what is should be, e.g. 'dwi'
    :param run:                 The run item that is being moved
    :param dataformat:          The name of the dataformat, e.g. 'DICOM'
    :param clean:               A boolean that is passed to bids.append_run (telling it to clean-up commentedMap fields)
    :return:
    """

    if not dataformat:
        dataformat = get_dataformat(run['provenance'])

    num_runs_in = len(dir_bidsmap(bidsmap, dataformat))

    # Warn the user if the target run already exists when the run is moved to another datatype
    if source_datatype != target_datatype:
        if exist_run(bidsmap, dataformat, target_datatype, run):
            LOGGER.warning(f'That run from {source_datatype} already exists in {target_datatype}...')

        # Delete the source run
        delete_run(bidsmap, dataformat, source_datatype, provenance)

        # Append the (cleaned-up) target run
        append_run(bidsmap, dataformat, target_datatype, run, clean)

    else:
        for index, run_ in enumerate(bidsmap[dataformat][target_datatype]):
            if run_['provenance'] == str(provenance):
                bidsmap[dataformat][target_datatype][index] = run
                break

    num_runs_out = len(dir_bidsmap(bidsmap, dataformat))
    if num_runs_out != num_runs_in:
        LOGGER.exception(f"Number of runs in bidsmap['{dataformat}'] changed unexpectedly: {num_runs_in} -> {num_runs_out}")


def match_attribute(attribute, pattern) -> bool:
    """
    Match the value items with the attribute string using regexp. If both attribute
    and values are a list then they are directly compared as is, else they are converted
    to a string

    Examples:
        match_attribute('my_pulse_sequence_name', 'name')       -> False
        match_attribute([1,2,3], [1,2,3])                       -> True
        match_attribute([1,2,3], '[1, 2, 3]')                   -> True
        match_attribute('my_pulse_sequence_name', '^my.*name$') -> True
        match_attribute('T1_MPRage', '(?i).*(MPRAGE|T1w).*'     -> True

    :param attribute:   The long string that is being searched in (e.g. a DICOM attribute)
    :param pattern:     A re.fullmatch regular expression pattern
    :return:            True if a match is found or both attribute and values are identical or
                        empty / None. False otherwise
    """

    # Consider it a match if both attribute and value are identical or empty / None
    if attribute==pattern or (not attribute and not pattern):
        return True

    if not attribute or not pattern:
        return False

    # Make sure we start with proper string types
    attribute = str(attribute).strip()
    pattern   = str(pattern).strip()

    # Compare the value items (with / without wildcard) with the attribute string items
    try:
        match = re.fullmatch(pattern, attribute)
    except re.error as patternerror:
        LOGGER.error(f"Cannot compile regular expression pattern '{pattern}': {patternerror}")
        match = None

    return match is not None


def exist_run(bidsmap: dict, dataformat: str, datatype: str, run_item: dict, matchbidslabels: bool=False, matchmetalabels: bool=False) -> bool:
    """
    Checks the bidsmap to see if there is already an entry in runlist with the same attributes and, optionally, bids values as in the input run

    :param bidsmap:         Full bidsmap data structure, with all options, BIDS labels and attributes, etc
    :param dataformat:      The information source in the bidsmap that is used, e.g. 'DICOM'
    :param datatype:        The datatype in the source that is used, e.g. 'anat'. Empty values will search through all datatypes
    :param run_item:        The run (listitem) that is searched for in the datatype
    :param matchbidslabels: If True, also matches the BIDS-keys, otherwise only run['attributes']
    :param matchmetalabels: If True, also matches the meta-keys, otherwise only run['attributes']
    :return:                True if the run exists in runlist, otherwise False
    """

    if not dataformat:
        dataformat = get_dataformat(run_item['provenance'])

    if not datatype:
        for datatype in bidscoindatatypes + (unknowndatatype, ignoredatatype):
            if exist_run(bidsmap, dataformat, datatype, run_item, matchbidslabels):
                return True

    if not bidsmap.get(dataformat, {}).get(datatype):
        return False

    for run in bidsmap[dataformat][datatype]:

        # Begin with match = False only if all attributes are empty
        match = any([run[matching][attrkey] not in [None,''] for matching in ('filesystem','attributes') for attrkey in run[matching]])  # Normally match==True, but make match==False if all attributes are empty

        # Search for a case where all run_item items match with the run_item items
        for matching in ('filesystem', 'attributes'):
            for itemkey, itemvalue in run_item[matching].items():
                value = run[matching].get(itemkey)          # Matching bids-labels which exist in one datatype but not in the other -> None
                match = match and match_attribute(itemvalue, value)
                if not match:
                    break                                   # There is no point in searching further within the run_item now that we've found a mismatch

        # See if the bidskeys also all match. This is probably not very useful, but maybe one day...
        if matchbidslabels and match:
            for itemkey, itemvalue in run_item['bids'].items():
                value = run['bids'].get(itemkey)            # Matching bids-labels which exist in one datatype but not in the other -> None
                match = match and value==itemvalue
                if not match:
                    break                                   # There is no point in searching further within the run_item now that we've found a mismatch

        # See if the bidskeys also all match. This is probably not very useful, but maybe one day...
        if matchmetalabels and match:
            for itemkey, itemvalue in run_item['meta'].items():
                value = run['meta'].get(itemkey)            # Matching bids-labels which exist in one datatype but not in the other -> None
                match = match and value==itemvalue
                if not match:
                    break                                   # There is no point in searching further within the run_item now that we've found a mismatch

        # Stop searching if we found a matching run_item (i.e. which is the case if match is still True after all run tests)
        if match:
            return True

    return False


def check_run(datatype: str, run: dict, validate: bool=False) -> bool:
    """
    Check run for required and optional entitities using the BIDS schema files

    :param datatype:    The datatype that is checked, e.g. 'anat'
    :param run:         The run (listitem) with bids entities that are checked against missing values & invalid keys
    :param validate:    Validate if all bids-keys and values are present according to the BIDS schema specifications
    :return:            True if the run entities are bids-valid or if they cannot be checked, otherwise False
    """

    run_found  = False
    run_valsok = True
    run_keysok = True

    # Check if we have provenance info
    if validate and not run['provenance']:
        pass    # TODO: avoid this when reading templates
        # logger.info(f'No provenance info found for {datatype}/*_{run["bids"]["suffix"]}')

    # Use the suffix to find the right typegroup
    if validate and 'suffix' not in run['bids']:
        LOGGER.warning(f'Invalid bidsmap: BIDS {datatype} entity "suffix" is absent for {run["provenance"]} -> {datatype}')
    if datatype not in bidsdatatypes: return True
    for typegroup in bidsdatatypes[datatype]:
        if run['bids']['suffix'] in typegroup['suffixes']:
            run_found = True

            # Check if all expected entity-keys are present in the run and if they are properly filled
            for entityname in typegroup['entities']:
                entitykey = entities[entityname]['entity']
                bidsvalue = run['bids'].get(entitykey)
                if entitykey in ('sub', 'ses'): continue
                if isinstance(bidsvalue, list):
                    bidsvalue = bidsvalue[bidsvalue[-1]]    # Get the selected item
                if isinstance(bidsvalue, str) and not (bidsvalue.startswith('<') and bidsvalue.endswith('>')) and bidsvalue != cleanup_value(bidsvalue):
                    LOGGER.warning(f'Invalid {entitykey} value: "{bidsvalue}" for {run["provenance"]} -> {datatype}/*_{run["bids"]["suffix"]}')
                if validate and entitykey not in run['bids']:
                    LOGGER.warning(f'Invalid bidsmap: BIDS entity "{entitykey}" is absent for {run["provenance"]} -> {datatype}/*_{run["bids"]["suffix"]}')
                    run_keysok = False
                elif typegroup['entities'][entityname]=='required' and not bidsvalue:
                    if validate is False:                   # Do not inform the user about empty template values
                        LOGGER.info(f'BIDS entity "{entitykey}" is required for {datatype}/*_{run["bids"]["suffix"]}')
                    run_valsok = False

            # Check if all the bids-keys are present in the schema file
            entitykeys = [entities[entityname]['entity'] for entityname in typegroup['entities']]
            for bidskey in run['bids']:
                if bidskey not in entitykeys + ['suffix']:
                    if validate:
                        LOGGER.warning(f'Invalid bidsmap: BIDS {datatype} entity {run["provenance"]} -> "{bidskey}: {run["bids"][bidskey]}" is not allowed according to the BIDS standard')
                        run_keysok = False
                    elif run["bids"][bidskey]:
                        if validate is False:
                            LOGGER.info(f'BIDS {datatype} entity "{bidskey}: {run["bids"][bidskey]}" is not allowed according to the BIDS standard (clear "{run["bids"][bidskey]})" to resolve this issue)')
                        run_valsok = False

    return run_found and run_valsok and run_keysok


def get_matching_run(sourcefile: Path, bidsmap: dict, dataformat: str) -> Tuple[dict, str, Union[int, None]]:
    """
    Find the first run in the bidsmap with filesystem and file attributes that match with the sourcefile, and then
    through the attributes. The datatypes are searcher for in this order:

    (ignoredatatype,) + bidscoindatatypes + (unknowndatatype,)

    Then update/fill the (dynamic) bids and meta values (bids values are cleaned-up to be BIDS-valid)

    :param sourcefile:  The full pathname of the source dicom-file or PAR/XML file
    :param bidsmap:     Full bidsmap data structure, with all options, BIDS keys and attributes, etc
    :param dataformat:  The information source in the bidsmap that is used, e.g. 'DICOM'
    :return:            (run, datatype, index) The matching and filled-in / cleaned run item, datatype and list index as in run = bidsmap[dataformat][datatype][index]
                        datatype = bids.unknowndatatype and index = None if there is no match, the run is still populated with info from the source-file
    """

    if not dataformat:
        dataformat = get_dataformat(sourcefile)

    # Loop through all bidscoindatatypes and runs; all info goes cleanly into run_ (to avoid formatting problem of the CommentedMap)
    run_ = get_run_(str(sourcefile.resolve()))
    for datatype in (ignoredatatype,) + bidscoindatatypes + (unknowndatatype,):                                 # The datatypes in which a matching run is searched for

        runs = bidsmap.get(dataformat, {}).get(datatype, [])
        if not runs:
            runs = []
        for index, run in enumerate(runs):

            match = any([run[matching][attrkey] not in [None,''] for matching in ('filesystem','attributes') for attrkey in run[matching]])     # Normally match==True, but make match==False if all attributes are empty

            # Try to see if the sourcefile matches all of the filesystem properties
            run_['filesystem'] = {}
            for filekey, filevalue in run['filesystem'].items():

                # Check if the attribute value matches with the info from the sourcefile
                if filevalue:
                    sourcevalue = get_sourcevalue(filekey, sourcefile, 'FileSystem')
                    match       = match and match_attribute(sourcevalue, filevalue)

                # Don not fill the empty attribute with the info from the sourcefile but keep the matching expression
                run_['filesystem'][filekey] = filevalue

            # Try to see if the sourcefile matches all of the attributes and fill all of them
            run_['attributes'] = {}
            for attrkey, attrvalue in run['attributes'].items():

                # Check if the attribute value matches with the info from the sourcefile
                sourcevalue = get_sourcevalue(attrkey, sourcefile, dataformat)
                if attrvalue:
                    match = match and match_attribute(sourcevalue, attrvalue)

                # Fill the empty attribute with the info from the sourcefile
                run_['attributes'][attrkey] = sourcevalue

            # Try to fill the bids-labels
            run_['bids'] = {}
            for bidskey, bidsvalue in run['bids'].items():

                # Replace the dynamic bids values
                run_['bids'][bidskey] = get_dynamicvalue(bidsvalue, sourcefile)

                # SeriesDescriptions (and ProtocolName?) may get a suffix like '_SBRef' from the vendor, try to strip it off
                run_ = strip_suffix(run_)

            # Try to fill the meta-data
            run_['meta'] = {}
            for metakey, metavalue in run['meta'].items():

                # Replace the dynamic bids values
                run_['meta'][metakey] = get_dynamicvalue(metavalue, sourcefile, cleanup=False)

            # Stop searching the bidsmap if we have a match
            if match:
                return run_, datatype, index

    # We don't have a match (all tests failed, so datatype should be the *last* one, i.e. unknowndatatype)
    LOGGER.debug(f"Could not find a matching run in the bidsmap for {sourcefile} -> {datatype}")
    return run_, datatype, None


def get_subid_sesid(sourcefile: Path, subid: str= '<<SourceFilePath>>', sesid: str= '<<SourceFilePath>>', subprefix: str= 'sub-', sesprefix: str= 'ses-') -> Tuple[str, str]:
    """
    Extract the cleaned-up subid and sesid from the pathname if subid/sesid == '<<SourceFilePath>>', or from the dicom header

    :param sourcefile: The full pathname of the file. If it is a source file, the sub/ses values are parsed from its path if subid/sesid=='<<SourceFilePath>>'
    :param subid:      The subject identifier, i.e. name of the subject folder (e.g. 'sub-001' or just '001') or a dynamic source attribute. Can be left empty
    :param sesid:      The optional session identifier, same as subid
    :param subprefix:  The optional subprefix (e.g. 'sub-'). Used to parse the sub-value from the provenance as default subid
    :param sesprefix:  The optional sesprefix (e.g. 'ses-'). If it is found in the provenance then a default sesid will be set
    :return:           Updated (subid, sesid) tuple, including the BIDS-compliant sub-/ses-prefix
    """

    # Input checking
    if subprefix not in str(sourcefile):
        LOGGER.warning(f"Could not parse sub/ses-id information from '{sourcefile}': no '{subprefix}' label in its path")
        return '', ''

    # Add default value for subid and sesid (e.g. for the bidseditor)
    if subid == '<<SourceFilePath>>':
        subid = [part for part in sourcefile.parent.parts if part.startswith(subprefix)][-1]
    else:
        subid = get_dynamicvalue(subid, sourcefile, runtime=True)
    if sesid == '<<SourceFilePath>>':
        sesid = [part for part in sourcefile.parent.parts if part.startswith(sesprefix)]
        if sesid:
            sesid = sesid[-1]
        else:
            sesid = ''
    else:
        sesid = get_dynamicvalue(sesid, sourcefile, runtime=True)

    # Add sub- and ses- prefixes if they are not there
    subid = 'sub-' + cleanup_value(re.sub(f'^{subprefix}', '', subid))
    if sesid:
        sesid = 'ses-' + cleanup_value(re.sub(f'^{sesprefix}', '', sesid))

    return subid, sesid


def get_derivatives(datatype: str) -> list:
    """
    Retrieves a list of suffixes that are stored in the derivatives folder (e.g. the qMRI maps). TODO: Replace with a more systematic / documented method
    """

    if datatype == 'anat':
        return [suffix for suffix in bidsdatatypes[datatype][1]['suffixes'] if suffix not in ('UNIT1',)]                    # The qMRI data (maps)
    elif datatype == 'fmap':
        return [suffix for n,typegroup in enumerate(bidsdatatypes[datatype]) for suffix in typegroup['suffixes'] if n>1]    # The non-standard fmaps (file collections)
    else:
        return []


def get_bidsname(subid: str, sesid: str, run: dict, runtime: bool=False) -> str:
    """
    Composes a filename as it should be according to the BIDS standard using the BIDS keys in run. The bids values are
    dynamically updated and cleaned, and invalid bids keys are ignored

    :param subid:       The subject identifier, i.e. name of the subject folder (e.g. 'sub-001' or just '001')
    :param sesid:       The optional session identifier, i.e. name of the session folder (e.g. 'ses-01' or just '01'). Can be left empty
    :param run:         The run mapping with the BIDS key-value pairs
    :param runtime:     Replaces <<dynamic>> bidsvalues if True
    :return:            The composed BIDS file-name (without file-extension)
    """

    # Try to update the sub/ses-ids
    if not subid.startswith('sub-'):
        subid = f"sub-{cleanup_value(subid)}"
    if sesid and not sesid.startswith('ses-'):
        sesid = f"ses-{cleanup_value(sesid)}"

    # Compose a bidsname from valid BIDS entities only
    bidsname = f"{subid}{add_prefix('_', sesid)}"                               # Start with the subject/session identifier
    for entitykey in [entities[entity]['entity'] for entity in entities]:
        bidsvalue = run['bids'].get(entitykey)                                  # Get the entity data from the run
        if isinstance(bidsvalue, list):
            bidsvalue = bidsvalue[bidsvalue[-1]]                                # Get the selected item
        else:
            bidsvalue = get_dynamicvalue(bidsvalue, Path(run['provenance']), runtime)
        if bidsvalue:
            bidsname = f"{bidsname}_{entitykey}-{cleanup_value(bidsvalue)}"     # Append the key-value data to the bidsname
    bidsname = f"{bidsname}{add_prefix('_', run['bids']['suffix'])}"            # And end with the suffix

    return bidsname


def get_filesystemhelp(filesystemkey: str) -> str:
    """
    Reads the description of a matching attributes key in the source dictionary

    :param filesystemkey:   The filesystem key for which the help text is obtained
    :return:                The obtained help text
    """

    # Return the description from the DICOM dictionary or a default text
    if filesystemkey == 'path':
        return 'The path of the source file that is matched against the (regexp) pattern'
    if filesystemkey == 'name':
        return 'The name of the source file that is matched against the (regexp) pattern'
    if filesystemkey == 'size':
        return 'The size of the source file that is matched against the (regexp) pattern'
    if filesystemkey == 'nrfiles':
        return 'The nr of similar files in the folder that matched against the filesystem (regexp) patterns'


def get_attributeshelp(attributeskey: str) -> str:
    """
    Reads the description of a matching attributes key in the source dictionary

    TODO: implement PAR/REC support

    :param attributeskey:   The attribute key for which the help text is obtained
    :return:                The obtained help text
    """

    if not attributeskey:
        return "Please provide a key-name"

    # Return the description from the DICOM dictionary or a default text
    try:
        return f"{attributeskey}\nThe DICOM '{datadict.dictionary_description(attributeskey)}' attribute"

    except ValueError:
        return f"{attributeskey}\nA private key"


def get_entityhelp(entitykey: str) -> str:
    """
    Reads the description of a matching entity=entitykey in the schema/entities.yaml file

    :param entitykey:   The bids key for which the help text is obtained
    :return:            The obtained help text
    """

    if not entitykey:
        return "Please provide a key-name"

    # Return the description from the entities or a default text
    for entityname in entities:
        if entities[entityname]['entity'] == entitykey:
            return f"{entities[entityname]['name']}\n{entities[entityname]['description']}"

    return f"{entitykey}\nA private key"


def get_metahelp(metakey: str) -> str:
    """
    Reads the description of a matching schema/metadata/metakey.yaml file

    :param metakey: The meta key for which the help text is obtained
    :return:        The obtained help text
    """

    if not metakey:
        return "Please provide a key-name"

    # Return the description from the metadata file or a default text
    metafile = schema_folder/'metadata'/(metakey + '.yaml')
    if metafile.is_file():
        with metafile.open('r') as stream:
            metadata = yaml.load(stream)
        if metakey == 'IntendedFor':    # IntendedFor is a special search-pattern field in BIDScoin
            metadata['description'] += ('\nThese associated files can be dynamically searched for during'
                                        '\nbidscoiner runtime with glob-style matching patterns such as'
                                        '\n"<<Reward*_bold><Stop*_epi>>" (see the online documentation)')
        return f"{metadata['name']}\n{metadata['description']}"

    return f"{metakey}\nA private key"


def get_dynamicvalue(bidsvalue: str, sourcefile: Path, cleanup: bool=True, runtime: bool=False) -> str:
    """
    Replaces (dynamic) bidsvalues with (DICOM) run attributes when they start with '<' and end with '>',
    but not with '<<' and '>>' unless runtime = True

    :param bidsvalue:   The value from the BIDS key-value pair
    :param sourcefile:  The source (e.g. DICOM or PAR/XML) file from which the attribute is read
    :param cleanup:     Removes non-BIDS-compliant characters
    :param runtime:     Replaces <<dynamic>> bidsvalues if True
    :return:            Updated bidsvalue (if possible, otherwise the original bidsvalue is returned)
    """

    # Input checks
    if not bidsvalue or not isinstance(bidsvalue, str):
        return bidsvalue

    # Intelligent filling of the value is done runtime by bidscoiner
    if bidsvalue.startswith('<<') and bidsvalue.endswith('>>'):
        if runtime:
            bidsvalue = bidsvalue[1:-1]
        else:
            return bidsvalue

    # Fill any bids-key with the <annotated> dicom attribute(s)
    if bidsvalue.startswith('<') and bidsvalue.endswith('>') and sourcefile.name:
        sourcevalue = ''.join([str(get_sourcevalue(value, sourcefile)) for value in bidsvalue[1:-1].split('><')])
        if sourcevalue:
            bidsvalue = sourcevalue
            if cleanup:
                bidsvalue = cleanup_value(bidsvalue)

    return bidsvalue


def get_bidsvalue(bidsfile: Union[str, Path], bidskey: str, newvalue: str='') -> Union[Path, str]:
    """
    Sets the bidslabel, i.e. '*_bidskey-*_' is replaced with '*_bidskey-bidsvalue_'. If the key is not in the bidsname
    then the newvalue is appended to the acquisition label. If newvalue is empty (= default), then the parsed existing
    bidsvalue is returned and nothing is set

    :param bidsfile:    The bidsname (e.g. as returned from get_bidsname or fullpath)
    :param bidskey:     The name of the bidskey, e.g. 'echo' or 'suffix'
    :param newvalue:    The new bidsvalue. NB: remove non-BIDS compliant characters beforehand (e.g. using cleanup_value)
    :return:            The bidsname with the new bidsvalue or, if newvalue is empty, the existing bidsvalue
    """

    bidspath = Path(bidsfile).parent
    bidsname = Path(bidsfile).with_suffix('').stem
    bidsext  = ''.join(Path(bidsfile).suffixes)

    # Get the existing bidsvalue
    oldvalue = ''
    acqvalue = ''
    if bidskey == 'suffix':
        oldvalue = bidsname.split('_')[-1]
    else:
        for keyval in bidsname.split('_'):
            if '-' in keyval:
                key, value = keyval.split('-', 1)
                if key == bidskey:
                    oldvalue = value
                if key == 'acq':
                    acqvalue = value

    # Replace the existing bidsvalue with the new value or append the newvalue to the acquisition value
    if newvalue:
        if f'_{bidskey}-' not in bidsname + 'suffix':
            if '_acq-' not in bidsname:         # Insert the 'acq' key right after task, ses or sub key-value pair (i.e. order as in entities.yaml)
                keyvals  = bidsname.split('_')
                keyvals.insert(1 + ('_ses-' in bidsname) + ('_task-' in bidsname), 'acq-')
                bidsname = '_'.join(keyvals)
            bidskey  = 'acq'
            oldvalue = acqvalue
            newvalue = f"{acqvalue}{newvalue}"

        # Return the updated bidsfile
        if bidskey == 'suffix':
            newbidsfile = (bidspath/(bidsname.replace(f"_{oldvalue}", f"_{newvalue}"))).with_suffix(bidsext)
        else:
            newbidsfile = (bidspath/(bidsname.replace(f"{bidskey}-{oldvalue}", f"{bidskey}-{newvalue}"))).with_suffix(bidsext)
        if isinstance(bidsfile, str):
            newbidsfile = str(newbidsfile)
        return newbidsfile

    # Or just return the parsed old bidsvalue
    else:
        return oldvalue


def insert_bidskeyval(bidsfile: Union[str, Path], bidskey: str, newvalue: str='') -> Union[Path, str]:
    """
    Inserts or replaces the bids key-label pair into the bidsfile. All invalid keys are removed from the name

    :param bidsfile:    The bidsname (e.g. as returned from get_bidsname or fullpath)
    :param bidskey:     The name of the new bidskey, e.g. 'echo' or 'suffix'
    :param newvalue:    The value of the new bidskey
    :return:            The bidsname with the new bids key-value pair
    """

    bidspath = Path(bidsfile).parent
    bidsname = Path(bidsfile).with_suffix('').stem
    bidsext  = ''.join(Path(bidsfile).suffixes)

    # Parse the key-value pairs and store all the run info
    run   = get_run_()
    sesid = ''
    for keyval in bidsname.split('_'):
        if '-' in keyval:
            key, val = keyval.split('-', 1)
            if key == 'sub':
                subid = keyval
            elif key == 'ses':
                sesid = keyval
            else:
                run['bids'][key] = val
        else:
            run['bids']['suffix'] = f"{run['bids'].get('suffix','')}_{keyval}"     # account for multiple suffixes (e.g. _bold_e1_ph from dcm2niix)
    if run['bids'].get('suffix','').startswith('_'):
        run['bids']['suffix'] = run['bids']['suffix'][1:]

    # Insert the key-value pair in the run
    if bidskey == 'sub':
        subid = newvalue
    elif bidskey == 'ses':
        sesid = newvalue
    else:
        run['bids'][bidskey] = newvalue

    # Compose the new filename
    newbidsfile = (bidspath/get_bidsname(subid, sesid, run)).with_suffix(bidsext)

    if isinstance(bidsfile, str):
        newbidsfile = str(newbidsfile)
    return newbidsfile


def increment_runindex(bidsfolder: Path, bidsname: str, ext: str='.*') -> Union[Path, str]:
    """
    Checks if a file with the same the bidsname already exists in the folder and then increments the runindex (if any)
    until no such file is found

    :param bidsfolder:  The full pathname of the bidsfolder
    :param bidsname:    The bidsname with a provisional runindex
    :param ext:         The file extension for which the runindex is incremented (default = '.*')
    :return:            The bidsname with the incremented runindex
    """

    while list(bidsfolder.glob(bidsname + ext)):

        runindex = get_bidsvalue(bidsname, 'run')
        if runindex:
            bidsname = get_bidsvalue(bidsname, 'run', str(int(runindex) + 1))

    return bidsname
