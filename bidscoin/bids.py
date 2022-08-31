"""
Module with helper functions

Some functions are derived from dac2bids.py from Daniel Gomez 29.08.2016
https://github.com/dangom/dac2bids/blob/master/dac2bids.py

@author: Marcel Zwiers
"""
import copy
import re
import logging
import tempfile
import tarfile
import zipfile
import json
import shutil
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

# Read the BIDS schema data
with (bidscoin.schemafolder/'objects'/'datatypes.yaml').open('r') as _stream:
    bidsdatatypesdef = yaml.load(_stream)                                       # The valid BIDS datatypes, along with their full names and descriptions
bidsdatatypes = {}
for _datatype in bidsdatatypesdef:
    with (bidscoin.schemafolder/'rules'/'datatypes'/_datatype).with_suffix('.yaml').open('r') as _stream:
        bidsdatatypes[_datatype] = yaml.load(_stream)                           # The entities that can/should be present for each BIDS datatype
with (bidscoin.schemafolder/'objects'/'suffixes.yaml').open('r') as _stream:
    suffixes = yaml.load(_stream)                                               # The descriptions of the valid BIDS file suffixes
with (bidscoin.schemafolder/'objects'/'entities.yaml').open('r') as _stream:
    entities = yaml.load(_stream)                                               # The descriptions of the entities present in BIDS filenames
with (bidscoin.schemafolder/'rules'/'entities.yaml').open('r') as _stream:
    entitiesorder = yaml.load(_stream)                                          # The order in which the entities should appear within filenames
with (bidscoin.schemafolder/'objects'/'metadata.yaml').open('r') as _stream:
    metadata = yaml.load(_stream)                                               # The descriptions of the valid BIDS metadata fields


class DataSource:
    def __init__(self, provenance: Union[str, Path]='', plugins: dict=None, dataformat: str='', datatype: str='', subprefix: str='', sesprefix: str=''):
        """
        A source datatype (e.g. DICOM or PAR) that can be converted to BIDS by the plugins

        :param provenance:  The full path of a representative file for this data source
        :param plugins:     The plugins that are used to interact with the source datatype
        :param dataformat:  The dataformat name in the bidsmap, e.g. DICOM or PAR
        :param datatype:    The intended BIDS datatype of the data source TODO: move to a separate BidsTarget / Mapping class
        :param subprefix:   The subprefix used in the sourcefolder
        :param sesprefix:   The sesprefix used in the sourcefolder
        """

        self.path       = Path(provenance)
        self.datatype   = datatype
        self.dataformat = dataformat
        self.plugins    = plugins
        if not plugins:
            self.plugins = {}
        if not dataformat:
            self.is_datasource()
        self.subprefix  = subprefix
        self.sesprefix  = sesprefix
        self.metadata   = {}
        jsonfile        = self.path.with_suffix('').with_suffix('.json') if self.path.name else self.path
        if jsonfile.is_file():
            with jsonfile.open('r') as json_fid:
                self.metadata = json.load(json_fid)
                if not isinstance(self.metadata, dict):
                    LOGGER.warning(f"Skipping unexpectedly formatted meta-data in: {jsonfile}")
                    self.metadata = {}

    def is_datasource(self) -> bool:
        """Returns True is the datasource has a valid dataformat"""

        for plugin, options in self.plugins.items():
            module = bidscoin.import_plugin(plugin, ('is_sourcefile',))
            if module:
                try:
                    dataformat = module.is_sourcefile(self.path)
                except Exception as moderror:
                    dataformat = ''
                    LOGGER.warning(f"The {plugin} plugin crashed while reading {self.path}\n{moderror}")
                if dataformat:
                    self.dataformat = dataformat
                    return True

        LOGGER.debug(f"No plugins to read {self.path}")
        return False

    def properties(self, tagname: str, run: dict=None) -> Union[str, int]:
        """
        Gets the 'filepath[:regexp]', 'filename[:regexp]', 'filesize' or 'nrfiles' filesystem property. The filepath (with trailing "/")
        and filename can be parsed using an optional regular expression re.findall(regexp, filepath / filename). The last match is returned
        for the filepath, the first match for the filename

        :param tagname: The name of the filesystem property key, e.g. 'filename', 'filename:sub-(.*?)_' or 'nrfiles'
        :param run:     If given and tagname == 'nrfiles' then the nrfiles is dependent on the other filesystem matching-criteria
        :return:        The property value (posix with a trailing "/" if tagname == 'filepath') or '' if the property could not be parsed from the datasource
        """

        try:
            if tagname.startswith('filepath:') and len(tagname) > 9:
                match = re.findall(tagname[9:], self.path.parent.as_posix() + '/')
                if match:
                    if len(match) > 1:
                        LOGGER.warning(f"Multiple matches {match} found when extracting {tagname} from {self.path.parent.as_posix() + '/'}, using: {match[-1]}")
                    return match[-1] if match else ''           # The last match is most likely the most informative
            elif tagname == 'filepath':
                return self.path.parent.as_posix() + '/'

            if tagname.startswith('filename:') and len(tagname) > 9:
                match = re.findall(tagname[9:], self.path.name)
                if match:
                    if len(match) > 1:
                        LOGGER.warning(f"Multiple matches {match} found when extracting {tagname} from {self.path.name}, using: {match[0]}")
                    return match[0] if match else ''            # The first match is most likely the most informative (?)
            elif tagname == 'filename':
                return self.path.name

            if tagname == 'filesize' and self.path.is_file():
                # Convert the size in bytes into a human-readable B, KB, MG, GB, TB format
                size  = self.path.stat().st_size                # Size in bytes
                power = 2 ** 10                                 # 2**10 = 1024
                label = {0:'', 1:'k', 2:'M', 3:'G', 4:'T'}      # Standard labels for powers of 1024
                n = 0                                           # The power/label index
                while size > power and n < len(label):
                    size /= power
                    n += 1
                return f"{size:.2f} {label[n]}B"

            if tagname == 'nrfiles' and self.path.is_file():
                if run:                                         # Currently not used but keep the option open for future use
                    def match(file): return ((match_runvalue(file.parent, run['properties']['filepath']) or not run['properties']['filepath']) and
                                             (match_runvalue(file.name, run['properties']['filename']) or not run['properties']['filename']) and
                                             (match_runvalue(file.stat().st_size, run['properties']['filesize']) or not run['properties']['filesize']))
                    return len([file for file in self.path.parent.iterdir() if match(file)])
                else:
                    return len(list(self.path.parent.iterdir()))

        except OSError as ioerror:
            LOGGER.warning(f"{ioerror}")

        return ''

    def attributes(self, attributekey: str, validregexp: bool=False) -> str:
        """
        Read the attribute value from the json sidecar file if it is there, else use the plugins to read it from the datasource

        :param attributekey: The attribute key for which a value is read from the json-file or from the datasource. A colon-separated regular expression can be appended to the attribute key (same as for the `filepath` and `filename` properties)
        :param validregexp:  If True, the regexp meta-characters in the attribute value (e.g. '*') are replaced by '.',
                             e.g. to prevent compile errors in match_runvalue()
        :return:             The attribute value or '' if the attribute could not be read from the datasource. NB: values are always converted to strings
        """

        attributeval = ''

        try:
            # Split off the regular expression pattern
            if ':' in attributekey:
                attributekey, pattern = attributekey.split(':', 1)
            else:
                pattern = ''

            # Read the attribute value from the sidecar file or from the datasource
            if attributekey in self.metadata:
                attributeval = str(self.metadata[attributekey]) if self.metadata[attributekey] is not None else ''
            else:
                for plugin, options in self.plugins.items():
                    module = bidscoin.import_plugin(plugin, ('get_attribute',))
                    if module:
                        attributeval = module.get_attribute(self.dataformat, self.path, attributekey, options)
                        attributeval = str(attributeval) if attributeval is not None else ''
                    if attributeval:
                        break

            # Apply the regular expression to the attribute value
            if attributeval:
                if validregexp:
                    try:            # Strip meta-characters to prevent match_runvalue() errors
                        re.compile(attributeval)
                    except re.error:
                        for metacharacter in ('.', '^', '$', '*', '+', '?', '{', '}', '[', ']', '\\', '|', '(', ')'):
                            attributeval = attributeval.strip().replace(metacharacter, '.')
                if pattern:
                    match = re.findall(pattern, attributeval)
                    if len(match) > 1:
                        LOGGER.warning(f"Multiple matches {match} found when extracting {pattern} from {attributeval}, using: {match[0]}")
                    attributeval = match[0] if match else ''    # The first match is most likely the most informative (?)

        except OSError as ioerror:
            LOGGER.warning(f"{ioerror}")

        return attributeval

    def subid_sesid(self, subid: str=None, sesid: str=None) -> Tuple[str, str]:
        """
        Extract the cleaned-up subid and sesid from the datasource properties or attributes

        :param subid:   The subject identifier, i.e. name of the subject folder (e.g. 'sub-001' or just '001') or a dynamic source attribute.
                        Can be left empty / None to use the default <<filepath:regexp>> extraction
        :param sesid:   The optional session identifier, same as subid
        :return:        Updated (subid, sesid) tuple, including the BIDS-compliant 'sub-'/'ses-' prefixes
        """

        # Add the default value for subid and sesid if not given
        if subid is None:
            subid = f"<<filepath:/{self.subprefix}(.*?)/>>"
        if sesid is None:
            sesid = f"<<filepath:/{self.sesprefix}(.*?)/>>"

        # Parse the sub-/ses-id's
        subid_ = self.dynamicvalue(subid, runtime=True)
        sesid  = self.dynamicvalue(sesid, runtime=True)
        if not subid_:
            LOGGER.error(f"Could not parse sub/ses-id information from {self.path} using: {subid}'")
            subid_ = subid
        subid = subid_

        # Add sub- and ses- prefixes if they are not there
        subid = 'sub-' + cleanup_value(re.sub(f"^{self.subprefix if self.subprefix!='*' else ''}", '', subid))
        if sesid:
            sesid = 'ses-' + cleanup_value(re.sub(f"^{self.sesprefix if self.sesprefix!='*' else ''}", '', sesid))

        return subid, sesid

    def dynamicvalue(self, value, cleanup: bool=True, runtime: bool=False):
        """
        Replaces dynamic (bids/meta) values with source attributes of filesystem properties when they start with
        '<' and end with '>', but not with '<<' and '>>' unless runtime = True

        :param value:       The dynamic value that contains source attribute or filesystem property key(s)
        :param cleanup:     Removes non-BIDS-compliant characters if True
        :param runtime:     Replaces dynamic values if True
        :return:            Updated value
        """

        # Input checks
        if not value or not isinstance(value, str) or not self.path.name:
            return value

        # Intelligent filling of the value is done runtime by bidscoiner
        if '<<' in value and '>>' in value:
            if runtime:
                value = value.replace('<<', '<').replace('>>', '>')
            else:
                return value

        # Fill any value-key with the <annotated> source attribute(s) or filesystem property
        if '<' in value and '>' in value:
            sourcevalue = ''
            for val in [val.split('>') for val in value.split('<')]:    # value = '123<abc>456' -> for val in [['123'], ['abc', '456']]
                if len(val) == 2:           # The first element is the dynamic part in val
                    sourcevalue += str(self.properties(val[0])) + str(self.attributes(val[0]))
                sourcevalue += val[-1]      # The last element is always the non-dynamic part in val
            value = sourcevalue
            if cleanup:
                value = cleanup_value(value)

        return value


def unpack(sourcefolder: Path, wildcard: str='*', workfolder: Path='') -> (List[Path], bool):
    """
    Unpacks and sorts DICOM files in sourcefolder to a temporary folder if sourcefolder contains a DICOMDIR file or .tar.gz, .gz or .zip files

    :param sourcefolder:    The full pathname of the folder with the source data
    :param wildcard:        A glob search pattern to select the tarballed/zipped files
    :param workfolder:      A root folder for temporary data
    :return:                Either ([unpacked and sorted session folders], True), or ([sourcefolder], False)
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
            workfolder = Path(tempfile.mkdtemp())
        else:
            workfolder = Path(workfolder)/next(tempfile._get_candidate_names())
        worksubses = workfolder/sourcefolder.relative_to(sourcefolder.parent.parent)     # = workfolder/raw/sub/ses
        worksubses.mkdir(parents=True, exist_ok=True)

        # Copy everything over to the workfolder
        LOGGER.info(f"Making temporary copy: {sourcefolder} -> {worksubses}")
        copy_tree(str(sourcefolder), str(worksubses))     # Older python versions don't support PathLib

        # Unpack the zip/tarballed files in the temporary folder
        sessions = []
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
            sessions += dicomsort.sortsessions(worksubses)

        # Sort the DICOM files if not sorted yet (e.g. DICOMDIR)
        sessions = list(set(sessions + dicomsort.sortsessions(worksubses)))

        return sessions, True

    else:

        return [sourcefolder], False


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
    try:
        if file.is_file() and file.suffix.lower() == '.par' and '# CLINICAL TRYOUT' in file.read_text():
            return True
        elif file.is_file() and file.suffix.lower() == '.xml':
            return True
    except (OSError, UnicodeDecodeError) as ioerror:
        pass

    return False


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
    Gets the Philips PAR-file from the folder

    :param folder:  The full pathname of the folder
    :return:        The filenames of the PAR-files in the folder.
    """

    parfiles = []
    for file in sorted(folder.iterdir()):
        if file.stem.startswith('.'):
            LOGGER.warning(f'Ignoring hidden file: {file}')
            continue
        if is_parfile(file):
            parfiles.append(file)

    return parfiles


def get_datasource(session: Path, plugins: dict, recurse: int=2) -> DataSource:
    """Gets a data source from the session inputfolder and its subfolders"""

    datasource = DataSource()
    for item in sorted(session.iterdir()):
        if item.stem.startswith('.'):
            LOGGER.debug(f'Ignoring hidden file: {item}')
            continue
        if item.is_dir() and recurse:
            datasource = get_datasource(item, plugins, recurse-1)
        elif item.is_file():
            datasource = DataSource(item, plugins)
        if datasource.dataformat:
            return datasource

    return datasource


def parse_x_protocol(pattern: str, dicomfile: Path) -> str:
    """
    Siemens writes a protocol structure as text into each DICOM file.
    This structure is necessary to recreate a scanning protocol from a DICOM,
    since the DICOM information alone wouldn't be sufficient.

    :param pattern:     A regexp expression: '^' + pattern + '\t = \t(.*)\\n'
    :param dicomfile:   The full pathname of the dicom-file
    :return:            The string extracted values from the dicom-file according to the given pattern
    """

    regexp = '^' + pattern + '\t = \t(.*)\n'
    regex  = re.compile(regexp.encode('utf-8'))

    with dicomfile.open('rb') as openfile:
        for line in openfile:
            match = regex.match(line)
            if match:
                return match.group(1).decode('utf-8')

    if not is_dicomfile_siemens(dicomfile):
        LOGGER.warning(f"Parsing {pattern} may have failed because {dicomfile} does not seem to be a Siemens DICOM file")

    LOGGER.warning(f"Pattern: '{regexp.encode('unicode_escape').decode()}' not found in: {dicomfile}")
    return ''


# Profiling shows this is currently the most expensive function, so therefore the (primitive but effective) _DICOMDICT_CACHE optimization
_DICOMDICT_CACHE = None
_DICOMFILE_CACHE = None
@lru_cache(maxsize=4096)
def get_dicomfield(tagname: str, dicomfile: Path) -> Union[str, int]:
    """
    Robustly extracts a DICOM attribute/tag value from a dictionary or from vendor specific fields

    :param tagname:     DICOM attribute name (e.g. 'SeriesNumber') or Pydicom-style tag number (e.g. '0x00200011', '(0x20,0x11)', '(0020, 0011)', '(20, 11)', '20,11')
    :param dicomfile:   The full pathname of the dicom-file
    :return:            Extracted tag-values as a flat string
    """

    global _DICOMDICT_CACHE, _DICOMFILE_CACHE

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
                _DICOMDICT_CACHE = dicomdata
                _DICOMFILE_CACHE = dicomfile
            else:
                dicomdata = _DICOMDICT_CACHE

            try:                                                    # Try Pydicom's hexadecimal tag number first
                value = eval(f"dicomdata[{tagname}].value")
            except (NameError, KeyError, SyntaxError):
                value = dicomdata.get(tagname, '')                  # Then try and see if it is an attribute name

            # Try a recursive search
            if not value and value != 0:
                for elem in dicomdata.iterall():
                    if tagname in (elem.name, elem.keyword, str(elem.tag), str(elem.tag).replace(', ',',')):
                        value = elem.value
                        break

            if not value and value!=0 and 'Modality' not in dicomdata:
                raise ValueError(f"Missing mandatory DICOM 'Modality' field in: {dicomfile}")

        except OSError as ioerror:
            LOGGER.warning(f"Cannot read {tagname} from {dicomfile}\n{ioerror}")
            value = ''

        except Exception as dicomerror:
            LOGGER.warning(f"Could not read {tagname} from {dicomfile}\n{dicomerror}")
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


# Profiling shows this is currently the most expensive function, so therefore the (primitive but effective) cache optimization
_TWIXHDR_CACHE  = None
_TWIXFILE_CACHE = None
@lru_cache(maxsize=4096)
def get_twixfield(tagname: str, twixfile: Path, mraid: int=2) -> Union[str, int]:
    """
    Recursively searches the TWIX file to extract the field value

    :param tagname:     Name of the TWIX field
    :param twixfile:    The full pathname of the TWIX file
    :param mraid:       The mapVBVD argument for selecting the multiraid file to load (default = 2, i.e. 2nd file)
    :return:            Extracted tag-values from the TWIX file
    """

    global _TWIXHDR_CACHE, _TWIXFILE_CACHE

    if not twixfile.is_file():
        LOGGER.debug(f"{twixfile} not found")
        value = ''

    else:
        try:
            if twixfile != _TWIXFILE_CACHE:

                from mapvbvd import mapVBVD

                twixObj = mapVBVD(twixfile, quiet=True)
                if isinstance(twixObj, list):
                    twixObj = twixObj[mraid - 1]
                hdr = twixObj['hdr']
                _TWIXHDR_CACHE  = hdr
                _TWIXFILE_CACHE = twixfile
            else:
                hdr = _TWIXHDR_CACHE

            def iterget(item, key):
                if isinstance(item, dict):

                    # First check to see if we can get the key-value data from the item
                    val = item.get(key, '')
                    if val and not isinstance(val, dict):
                        return val

                    # Loop over the item to see if we can get the key-value from the sub-items
                    if isinstance(item, dict):
                        for ds in item:
                            val = iterget(item[ds], key)
                            if val:
                                return val

                return ''

            value = iterget(hdr, tagname)

        except OSError:
            LOGGER.warning(f'Cannot read {tagname} from {twixfile}')
            value = ''

        except Exception as twixerror:
            LOGGER.warning(f'Could not parse {tagname} from {twixfile}\n{twixerror}')
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

    if not parfile.is_file():
        LOGGER.debug(f"{parfile} not found")
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


# Profiling shows this is currently the most expensive function, so therefore the (primitive but effective) cache optimization
_SPARHDR_CACHE  = None
_SPARFILE_CACHE = None
@lru_cache(maxsize=4096)
def get_sparfield(tagname: str, sparfile: Path) -> Union[str, int]:
    """
    Extracts the field value from the SPAR header-file

    :param tagname:     Name of the SPAR field
    :param sparfile:    The full pathname of the SPAR file
    :return:            Extracted tag-values from the SPAR file
    """

    global _SPARHDR_CACHE, _SPARFILE_CACHE

    if not sparfile.is_file():
        LOGGER.debug(f"{sparfile} not found")
        value = ''

    else:
        try:
            if sparfile!=_SPARFILE_CACHE:

                from spec2nii.philips import read_spar

                hdr = read_spar(sparfile)
                _SPARHDR_CACHE  = hdr
                _SPARFILE_CACHE = sparfile
            else:
                hdr = _SPARHDR_CACHE

            value = hdr.get(tagname, '')

        except ImportError:
            LOGGER.warning(f"The extra `spec2nii` library could not be found or was not installed (see the BIDScoin install instructions)")

        except OSError:
            LOGGER.warning(f"Cannot read {tagname} from {sparfile}")
            value = ''

        except Exception as sparerror:
            LOGGER.warning(f"Could not parse {tagname} from {sparfile}\n{sparerror}")
            value = ''

    # Cast the dicom datatype to int or str (i.e. to something that yaml.dump can handle)
    if isinstance(value, int):
        return int(value)
    elif value is None:
        return ''
    else:
        return str(value)  # If it's a MultiValue type then flatten it


# Profiling shows this is currently the most expensive function, so therefore the (primitive but effective) cache optimization
_P7HDR_CACHE  = None
_P7FILE_CACHE = None
@lru_cache(maxsize=4096)
def get_p7field(tagname: str, p7file: Path) -> Union[str, int]:
    """
    Extracts the field value from the P-file header

    :param tagname:     Name of the SPAR field
    :param p7file:      The full pathname of the P7 file
    :return:            Extracted tag-values from the P7 file
    """

    global _P7HDR_CACHE, _P7FILE_CACHE

    if not p7file.is_file():
        LOGGER.debug(f"{p7file} not found")
        value = ''

    else:
        try:
            if p7file!=_P7FILE_CACHE:

                from spec2nii.GE.ge_read_pfile import Pfile

                hdr = Pfile(p7file).hdr
                _P7HDR_CACHE  = hdr
                _P7FILE_CACHE = p7file
            else:
                hdr = _P7HDR_CACHE

            value = getattr(hdr, tagname, '')
            if type(value) == bytes:
                try:
                    value = value.decode('UTF-8')
                except UnicodeDecodeError:
                    pass

        except ImportError:
            LOGGER.warning(f"The extra `spec2nii` library could not be found or was not installed (see the BIDScoin install instructions)")

        except OSError:
            LOGGER.warning(f'Cannot read {tagname} from {p7file}')
            value = ''

        except Exception as p7error:
            LOGGER.warning(f'Could not parse {tagname} from {p7file}\n{p7error}')
            value = ''

    # Cast the dicom datatype to int or str (i.e. to something that yaml.dump can handle)
    if isinstance(value, int):
        return int(value)
    elif value is None:
        return ''
    else:
        return str(value)  # If it's a MultiValue type then flatten it


# ---------------- All function below this point are bidsmap related. TODO: make a class out of them -------------------


def load_bidsmap(yamlfile: Path, folder: Path=Path(), plugins:Union[tuple,list]=(), report: Union[bool,None]=True) -> Tuple[dict, Path]:
    """
    Read the mapping heuristics from the bidsmap yaml-file. If yamlfile is not fullpath, then 'folder' is first searched before
    the default 'heuristics'. If yamfile is empty, then first 'bidsmap.yaml' is searched for, then 'bidsmap_template'. So fullpath
    has precendence over folder and bidsmap.yaml has precedence over the bidsmap_template.

    NB: A run['datasource'] = DataSource object is added to every run-item

    :param yamlfile:    The full pathname or basename of the bidsmap yaml-file. If None, the default bidsmap_template file in the heuristics folder is used
    :param folder:      Only used when yamlfile=basename or None: yamlfile is then first searched for in folder and then falls back to the ./heuristics folder (useful for centrally managed template yaml-files)
    :param plugins:     List of plugins to be used (with default options, overrules the plugin list in the study/template bidsmaps)
    :param report:      Report log.info when reading a file
    :return:            Tuple with (1) ruamel.yaml dict structure, with all options, BIDS mapping heuristics, labels and attributes, etc and (2) the fullpath yaml-file
    """

    # Input checking
    if not folder.name or not folder.is_dir():
        folder = bidscoin.heuristicsfolder
    if not yamlfile.name:
        yamlfile = folder/'bidsmap.yaml'
        if not yamlfile.is_file():
            yamlfile = bidscoin.bidsmap_template

    # Add a standard file-extension if needed
    if not yamlfile.suffix:
        yamlfile = yamlfile.with_suffix('.yaml')

    # Get the full path to the bidsmap yaml-file
    if len(yamlfile.parents) == 1:
        if (folder/yamlfile).is_file():
            yamlfile = folder/yamlfile
        else:
            yamlfile = bidscoin.heuristicsfolder/yamlfile

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
    if bidsmapversion.rsplit('.', 1)[0] != bidscoin.version().rsplit('.', 1)[0] and report:
        LOGGER.warning(f'BIDScoiner version conflict: {yamlfile} was created with version {bidsmapversion}, but this is version {bidscoin.version()}')
    elif bidsmapversion != bidscoin.version() and report:
        LOGGER.info(f'BIDScoiner version difference: {yamlfile} was created with version {bidsmapversion}, but this is version {bidscoin.version()}. This is normally ok but check the https://bidscoin.readthedocs.io/en/latest/CHANGELOG.html')

    # Make sure we get a proper plugin options and dataformat sections (use plugin default bidsmappings when a template bidsmap is loaded)
    if not bidsmap['Options'].get('plugins'):
        bidsmap['Options']['plugins'] = {}
    if plugins:
        for plugin in [plugin for plugin in bidsmap['Options']['plugins'] if plugin not in plugins]:
            del bidsmap['Options']['plugins'][plugin]
    for plugin in plugins if plugins else bidsmap['Options']['plugins']:
        module = bidscoin.import_plugin(plugin)
        if not bidsmap['Options']['plugins'].get(plugin):
            LOGGER.info(f"Adding default bidsmap options from the {plugin} plugin")
            bidsmap['Options']['plugins'][plugin] = module.OPTIONS if 'OPTIONS' in dir(module) else {}
        if 'BIDSMAP' in dir(module) and yamlfile.parent == bidscoin.heuristicsfolder:
            for dataformat, bidsmappings in module.BIDSMAP.items():
                if dataformat not in bidsmap:
                    LOGGER.info(f"Adding default bidsmappings from the {plugin} plugin")
                    bidsmap[dataformat] = bidsmappings

    # Add missing provenance info, run dictionaries and bids entities
    run_      = get_run_()
    subprefix = bidsmap['Options']['bidscoin'].get('subprefix','')
    sesprefix = bidsmap['Options']['bidscoin'].get('sesprefix','')
    for dataformat in bidsmap:
        if dataformat in ('Options','PlugIns'): continue        # Handle legacy bidsmaps (-> 'PlugIns')
        if not bidsmap[dataformat]:             continue
        for datatype in bidsmap[dataformat]:
            if not isinstance(bidsmap[dataformat][datatype], list): continue
            for index, run in enumerate(bidsmap[dataformat][datatype]):

                # Add missing provenance info
                if not run.get('provenance'):
                    run['provenance'] = str(Path(f"{subprefix.replace('*','')}-unknown/{sesprefix.replace('*','')}-unknown/{dataformat}_{datatype}_id{index+1:03}"))

                # Add missing run dictionaries (e.g. "meta" or "properties")
                for key, val in run_.items():
                    if key not in run or not run[key]:
                        run[key] = val

                # Add a DataSource object
                run['datasource'] = DataSource(run['provenance'], bidsmap['Options']['plugins'], dataformat, datatype, subprefix, sesprefix)

                # Add missing bids entities
                for typegroup in bidsdatatypes.get(datatype,[]):
                    if run['bids']['suffix'] in typegroup['suffixes']:      # run_found = True
                        for entityname in typegroup['entities']:
                            entitykey = entities[entityname]['entity']
                            if entitykey not in run['bids'] and entitykey not in ('sub','ses'):
                                LOGGER.info(f"Adding missing {dataformat}>{datatype}>{run['bids']['suffix']} bidsmap entity key: {entitykey}")
                                run['bids'][entitykey] = ''

    # Validate the bidsmap entries
    check_bidsmap(bidsmap, report)

    return bidsmap, yamlfile


def save_bidsmap(filename: Path, bidsmap: dict) -> None:
    """
    Save the BIDSmap as a YAML text file

    NB: The run['datasource'] = DataSource objects are not saved

    :param filename:    Full pathname of the bidsmap file
    :param bidsmap:     Full bidsmap data structure, with all options, BIDS labels and attributes, etc
    :return:
    """

    # Remove the added DataSource object
    bidsmap = copy.deepcopy(bidsmap)
    for dataformat in bidsmap:
        if dataformat in ('Options','PlugIns'): continue        # Handle legacy bidsmaps (-> 'PlugIns')
        if not bidsmap[dataformat]:             continue
        for datatype in bidsmap[dataformat]:
            if not isinstance(bidsmap[dataformat][datatype], list): continue
            for run in bidsmap[dataformat][datatype]:
                run.pop('datasource', None)

    # Validate the bidsmap entries
    if not check_bidsmap(bidsmap, False):
        LOGGER.warning('Bidsmap values are invalid according to the BIDS specification')

    LOGGER.info(f"Writing bidsmap to: {filename}")
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open('w') as stream:
        yaml.dump(bidsmap, stream)


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
    for datatype in bidsmap.get(dataformat):
        if datatype in ('subject','session') or not bidsmap[dataformat][datatype]:
            continue
        for run in bidsmap[dataformat][datatype]:
            if not run['provenance']:
                LOGGER.warning(f'The bidsmap run {datatype} run does not contain provenance data')
            else:
                provenance.append(Path(run['provenance']))

    provenance.sort()

    return provenance


def get_run_(provenance: Union[str, Path]='', dataformat: str='', datatype: str='', bidsmap: dict=None) -> dict:
    """
    Get an empty run-item with the proper structure and provenance info

    :param provenance:  The unique provenance that is use to identify the run
    :param dataformat:  The information source in the bidsmap that is used, e.g. 'DICOM'
    :param datatype:    The bidsmap datatype that is used, e.g. 'anat'
    :param bidsmap:     The bidsmap, with all the bidscoin options in it
    :return:            The empty run
    """

    if bidsmap:
        plugins    = bidsmap['Options']['plugins']
        subprefix  = bidsmap['Options']['bidscoin'].get('subprefix','')
        sesprefix  = bidsmap['Options']['bidscoin'].get('sesprefix','')
        datasource = DataSource(provenance, plugins, dataformat, datatype, subprefix, sesprefix)
    else:
        datasource = DataSource(provenance, dataformat=dataformat, datatype=datatype)

    return dict(provenance = str(provenance),
                properties = {'filepath':'', 'filename':'', 'filesize':'', 'nrfiles':''},
                attributes = {},
                bids       = {},
                meta       = {},
                datasource = datasource)


def get_run(bidsmap: dict, datatype: str, suffix_idx: Union[int, str], datasource: DataSource) -> dict:
    """
    Find the (first) run in bidsmap[dataformat][bidsdatatype] with run['bids']['suffix_idx'] == suffix_idx

    :param bidsmap:     This could be a template bidsmap, with all options, BIDS labels and attributes, etc
    :param datatype:    The datatype in which a matching run is searched for (e.g. 'anat')
    :param suffix_idx:  The name of the suffix that is searched for (e.g. 'bold') or the datatype index number
    :param datasource:  The datasource with the provenance file from which the properties, attributes and dynamic values are read
    :return:            The clean (filled) run item in the bidsmap[dataformat][bidsdatatype] with the matching suffix_idx,
                        otherwise a dict with empty attributes & bids keys
    """

    runs = bidsmap.get(datasource.dataformat, {}).get(datatype, [])
    if not runs:
        runs = []
    for index, run in enumerate(runs):
        if index == suffix_idx or run['bids']['suffix'] == suffix_idx:

            # Get a clean run (remove comments to avoid overly complicated commentedMaps from ruamel.yaml)
            run_ = get_run_(datasource.path, bidsmap=bidsmap)

            for propkey, propvalue in run['properties'].items():
                run_['properties'][propkey] = propvalue

            for attrkey, attrvalue in run['attributes'].items():
                if datasource.path.name:
                    run_['attributes'][attrkey] = datasource.attributes(attrkey, validregexp=True)
                else:
                    run_['attributes'][attrkey] = attrvalue

            # Replace the dynamic bids values, except the dynamic run-index (e.g. <<1>>)
            for bidskey, bidsvalue in run['bids'].items():
                if bidskey == 'run' and bidsvalue and bidsvalue.replace('<','').replace('>','').isdecimal():
                    run_['bids'][bidskey] = bidsvalue
                else:
                    run_['bids'][bidskey] = datasource.dynamicvalue(bidsvalue)

            # Replace the dynamic meta values, except the IntendedFor value (e.g. <<task>>)
            for metakey, metavalue in run['meta'].items():
                if metakey == 'IntendedFor':
                    run_['meta'][metakey] = metavalue
                else:
                    run_['meta'][metakey] = datasource.dynamicvalue(metavalue, cleanup=False)

            run_['datasource']      = copy.deepcopy(run['datasource'])
            run_['datasource'].path = datasource.path

            return run_

    LOGGER.warning(f"'{datatype}' run with suffix_idx '{suffix_idx}' not found in bidsmap['{datasource.dataformat}']")
    return get_run_(datasource.path, bidsmap=bidsmap)


def find_run(bidsmap: dict, provenance: str, dataformat: str='', datatype: str='') -> dict:
    """
    Find the (first) run in bidsmap[dataformat][bidsdatatype] with run['provenance'] == provenance

    :param bidsmap:     This could be a template bidsmap, with all options, BIDS labels and attributes, etc
    :param provenance:  The unique provenance that is use to identify the run
    :param dataformat:  The dataformat section in the bidsmap in which a matching run is searched for, e.g. 'DICOM'
    :param datatype:    The datatype in which a matching run is searched for (e.g. 'anat')
    :return:            The (unfilled) run item from the bidsmap[dataformat][bidsdatatype]
    """

    if dataformat:
        dataformats = (dataformat,)
    else:
        dataformats = [item for item in bidsmap if item not in ('Options','PlugIns') and bidsmap[item]]
    for dataformat in dataformats:
        if datatype:
            datatypes = (datatype,)
        else:
            datatypes = [item for item in bidsmap[dataformat] if item not in ('subject','session') and bidsmap[dataformat][item]]
        for dtype in datatypes:
            for run in bidsmap[dataformat][dtype]:
                if Path(run['provenance']) == Path(provenance):
                    return run


def delete_run(bidsmap: dict, provenance: Union[dict, str], datatype: str= '') -> None:
    """
    Delete a run from the BIDS map

    :param bidsmap:     Full bidsmap data structure, with all options, BIDS labels and attributes, etc
    :param provenance:  The provenance identifier of/or the run-item that is deleted
    :param datatype:    The datatype that of the deleted run_item (can be different from run_item['datasource']), e.g. 'anat'
    :return:
    """

    if isinstance(provenance, str):
        run_item = find_run(bidsmap, provenance)
    else:
        run_item = provenance
        provenance = run_item['provenance']

    dataformat = run_item['datasource'].dataformat
    if not datatype:
        datatype = run_item['datasource'].datatype
    for index, run in enumerate(bidsmap[dataformat].get(datatype,[])):
        if Path(run['provenance']) == Path(provenance):
            del bidsmap[dataformat][datatype][index]


def append_run(bidsmap: dict, run: dict, clean: bool=True) -> None:
    """
    Append a run to the BIDS map

    :param bidsmap:     Full bidsmap data structure, with all options, BIDS labels and attributes, etc
    :param run:         The run (listitem) that is appended to the datatype
    :param clean:       A boolean to clean-up commentedMap fields
    :return:
    """

    dataformat = run['datasource'].dataformat
    datatype   = run['datasource'].datatype

    # Copy the values from the run to an empty dict
    if clean:
        run_ = get_run_(run['provenance'], datatype=datatype, bidsmap=bidsmap)

        for item in run_.keys():
            if item == 'provenance':
                continue
            if item == 'datasource':
                run_['datasource'] = run['datasource']
                continue
            for key, value in run[item].items():
                run_[item][key] = value

        run = run_

    if not bidsmap.get(dataformat):
        bidsmap[dataformat] = {}
    elif not bidsmap.get(dataformat).get(datatype):
        bidsmap[dataformat][datatype] = [run]
    else:
        bidsmap[dataformat][datatype].append(run)


def update_bidsmap(bidsmap: dict, source_datatype: str, run: dict, clean: bool=True) -> None:
    """
    Update the BIDS map if the datatype changes:
    1. Remove the source run from the source datatype section
    2. Append the (cleaned) target run to the target datatype section

    Else:
    1. Use the provenance to look-up the index number in that datatype
    2. Replace the run

    :param bidsmap:             Full bidsmap data structure, with all options, BIDS labels and attributes, etc
    :param source_datatype:     The current datatype name, e.g. 'anat'
    :param run:                 The run item that is being moved to run['datasource'].datatype
    :param clean:               A boolean that is passed to bids.append_run (telling it to clean-up commentedMap fields)
    :return:
    """

    dataformat  = run['datasource'].dataformat
    datatype    = run['datasource'].datatype
    num_runs_in = len(dir_bidsmap(bidsmap, dataformat))

    # Warn the user if the target run already exists when the run is moved to another datatype
    if source_datatype != datatype:
        if exist_run(bidsmap, datatype, run):
            LOGGER.warning(f'That run from {source_datatype} already exists in {datatype}...')

        # Delete the source run
        delete_run(bidsmap, run, source_datatype)

        # Append the (cleaned-up) target run
        append_run(bidsmap, run, clean)

    else:
        for index, run_ in enumerate(bidsmap[dataformat][datatype]):
            if run_['provenance'] == run['provenance']:
                bidsmap[dataformat][datatype][index] = run
                break

    num_runs_out = len(dir_bidsmap(bidsmap, dataformat))
    if num_runs_out != num_runs_in:
        LOGGER.exception(f"Number of runs in bidsmap['{dataformat}'] changed unexpectedly: {num_runs_in} -> {num_runs_out}")


def match_runvalue(attribute, pattern) -> bool:
    """
    Match the value items with the attribute string using regexp. If both attribute
    and values are a list then they are directly compared as is, else they are converted
    to a string

    Examples:
        match_runvalue('my_pulse_sequence_name', 'filename')   -> False
        match_runvalue([1,2,3], [1,2,3])                       -> True
        match_runvalue([1,2,3], '[1, 2, 3]')                   -> True
        match_runvalue('my_pulse_sequence_name', '^my.*name$') -> True
        match_runvalue('T1_MPRage', '(?i).*(MPRAGE|T1w).*'     -> True

    :param attribute:   The long string that is being searched in (e.g. a DICOM attribute)
    :param pattern:     A re.fullmatch regular expression pattern
    :return:            True if a match is found or both attribute and values are identical or
                        empty / None. False otherwise
    """

    # Consider it a match if both attribute and value are identical or empty / None
    if attribute==pattern or (not attribute and not pattern):
        return True

    if not pattern:
        return False

    # Make sure we start with proper string types
    if attribute is None:
        attribute = ''
    attribute = str(attribute).strip()
    pattern   = str(pattern).strip()

    # See if the pattern matches the source attribute
    try:
        match = re.fullmatch(pattern, attribute)
    except re.error as patternerror:
        LOGGER.error(f"Cannot compile regular expression pattern '{pattern}': {patternerror}")
        match = None

    return match is not None


def exist_run(bidsmap: dict, datatype: str, run_item: dict, matchbidslabels: bool=False, matchmetalabels: bool=False) -> bool:
    """
    Checks the bidsmap to see if there is already an entry in runlist with the same attributes and, optionally, bids values as in the input run

    :param bidsmap:         Full bidsmap data structure, with all options, BIDS labels and attributes, etc
    :param datatype:        The datatype in the source that is used, e.g. 'anat'. Empty values will search through all datatypes
    :param run_item:        The run-item that is searched for in the datatype
    :param matchbidslabels: If True, also matches the BIDS-keys, otherwise only run['attributes']
    :param matchmetalabels: If True, also matches the meta-keys, otherwise only run['attributes']
    :return:                True if the run exists in runlist, otherwise False
    """

    bidscoindatatypes = bidsmap['Options']['bidscoin'].get('datatypes',[])
    unknowndatatypes  = bidsmap['Options']['bidscoin'].get('unknowntypes',[])
    ignoredatatypes   = bidsmap['Options']['bidscoin'].get('ignoretypes',[])

    if not datatype:
        for datatype in bidscoindatatypes + unknowndatatypes + ignoredatatypes:
            if exist_run(bidsmap, datatype, run_item, matchbidslabels):
                return True

    if not bidsmap.get(run_item['datasource'].dataformat, {}).get(datatype):
        return False

    for run in bidsmap[run_item['datasource'].dataformat][datatype]:

        # Begin with match = False only if all attributes are empty
        match = any([run[matching][attrkey] not in [None,''] for matching in ('properties','attributes') for attrkey in run[matching]])  # Normally match==True, but make match==False if all attributes are empty

        # Search for a case where all run_item items match with the run_item items
        for matching in ('properties', 'attributes'):
            for itemkey, itemvalue in run_item[matching].items():
                value = run[matching].get(itemkey)          # Matching bids-labels which exist in one datatype but not in the other -> None
                match = match and match_runvalue(itemvalue, value)
                if not match:
                    break                                   # There is no point in searching further within the run_item now that we've found a mismatch

        # See if the bidskeys also all match. This is probably not very useful, but maybe one day...
        if matchbidslabels and match:
            for itemkey, itemvalue in run_item['bids'].items():
                value = run['bids'].get(itemkey)            # Matching bids-labels which exist in one datatype but not in the other -> None
                match = match and value==itemvalue
                if not match:
                    break                                   # There is no point in searching further within the run_item now that we've found a mismatch

        # See if the metakeys also all match. This is probably not very useful, but maybe one day...
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
        if run['bids'].get('suffix') in typegroup['suffixes']:
            run_found = True

            # Check if all expected entity-keys are present in the run and if they are properly filled
            for entityname in typegroup['entities']:
                entitykey = entities[entityname]['entity']
                bidsvalue = run['bids'].get(entitykey)
                if entitykey in ('sub', 'ses'): continue
                if isinstance(bidsvalue, list):
                    bidsvalue = bidsvalue[bidsvalue[-1]]    # Get the selected item
                if isinstance(bidsvalue, str) and not ('<' in bidsvalue and '>' in bidsvalue) and bidsvalue != cleanup_value(bidsvalue):
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


def get_matching_run(datasource: DataSource, bidsmap: dict, runtime=False) -> Tuple[dict, bool]:
    """
    Find the first run in the bidsmap with properties and file attributes that match with the data source, and then
    through the attributes. The datatypes are searched for in this order:

    ignoredatatypes + bidscoindatatypes + unknowndatatypes

    Then update/fill the provenance, and the (dynamic) bids and meta values (bids values are cleaned-up to be BIDS-valid)

    :param datasource:  The data source from which the attributes are read. NB: The datasource.datatype attribute is updated
    :param bidsmap:     Full bidsmap data structure, with all options, BIDS keys and attributes, etc
    :param runtime:     Dynamic <<values>> are expanded if True
    :return:            (run, match) The matching and filled-in / cleaned run item, datatype, and True if there is a match
                        If there is no match then the run is still populated with info from the source-file
    """

    bidscoindatatypes = bidsmap['Options']['bidscoin'].get('datatypes',[])
    unknowndatatypes  = bidsmap['Options']['bidscoin'].get('unknowntypes',[])
    ignoredatatypes   = bidsmap['Options']['bidscoin'].get('ignoretypes',[])

    # Loop through all bidscoindatatypes and runs; all info goes cleanly into run_ (to avoid formatting problem of the CommentedMap)
    run_ = get_run_(datasource.path, dataformat=datasource.dataformat, bidsmap=bidsmap)
    for datatype in ignoredatatypes + bidscoindatatypes + unknowndatatypes:         # The datatypes in which a matching run is searched for

        runs                = bidsmap.get(datasource.dataformat, {}).get(datatype, [])
        datasource.datatype = datatype
        for run in runs if runs else []:

            match = any([run[matching][attrkey] not in [None,''] for matching in ('properties','attributes') for attrkey in run[matching]])     # Normally match==True, but make match==False if all attributes are empty
            run_  = get_run_(datasource.path, dataformat=datasource.dataformat, datatype=datatype, bidsmap=bidsmap)

            # Try to see if the sourcefile matches all of the filesystem properties
            for propkey, propvalue in run['properties'].items():

                # Check if the attribute value matches with the info from the sourcefile
                if propvalue:
                    sourcevalue = datasource.properties(propkey)
                    match       = match and match_runvalue(sourcevalue, propvalue)

                # Don not fill the empty attribute with the info from the sourcefile but keep the matching expression
                run_['properties'][propkey] = propvalue

            # Try to see if the sourcefile matches all of the attributes and fill all of them
            for attrkey, attrvalue in run['attributes'].items():

                # Check if the attribute value matches with the info from the sourcefile
                sourcevalue = datasource.attributes(attrkey, validregexp=True)
                if attrvalue:
                    match = match and match_runvalue(sourcevalue, attrvalue)

                # Fill the empty attribute with the info from the sourcefile
                run_['attributes'][attrkey] = sourcevalue

            # Try to fill the bids-labels
            for bidskey, bidsvalue in run['bids'].items():

                # Replace the dynamic bids values, except the dynamic run-index (e.g. <<1>>)
                if bidskey == 'run' and bidsvalue and bidsvalue.replace('<','').replace('>','').isdecimal():
                    run_['bids'][bidskey] = bidsvalue
                else:
                    run_['bids'][bidskey] = datasource.dynamicvalue(bidsvalue, runtime=runtime)

                # SeriesDescriptions (and ProtocolName?) may get a suffix like '_SBRef' from the vendor, try to strip it off
                run_ = strip_suffix(run_)

            # Try to fill the meta-data
            for metakey, metavalue in run['meta'].items():

                # Replace the dynamic meta values, except the IntendedFor value (e.g. <<task>>)
                if metakey == 'IntendedFor':
                    run_['meta'][metakey] = metavalue
                else:
                    run_['meta'][metakey] = datasource.dynamicvalue(metavalue, cleanup=False, runtime=runtime)

            # Copy the DataSource object
            run_['datasource']      = copy.deepcopy(run['datasource'])
            run_['datasource'].path = datasource.path

            # Stop searching the bidsmap if we have a match
            if match:
                return run_, True

    # We don't have a match (all tests failed, so datatype should be the *last* one, e.g. unknowndatatype)
    LOGGER.debug(f"Could not find a matching run in the bidsmap for {datasource.path} -> {ignoredatatypes + bidscoindatatypes} -> {unknowndatatypes}")
    return run_, False


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


def get_bidsname(subid: str, sesid: str, run: dict, runtime: bool=False, cleanup: bool=True) -> str:
    """
    Composes a filename as it should be according to the BIDS standard using the BIDS keys in run. The bids values are
    dynamically updated and cleaned, and invalid bids keys and empty bids values are ignored

    :param subid:       The subject identifier, i.e. name of the subject folder (e.g. 'sub-001' or just '001')
    :param sesid:       The optional session identifier, i.e. name of the session folder (e.g. 'ses-01' or just '01'). Can be left empty
    :param run:         The run mapping with the BIDS key-value pairs
    :param runtime:     Replaces dynamic bidsvalues if True
    :param cleanup:     Removes non-BIDS-compliant characters if True
    :return:            The composed BIDS file-name (without file-extension)
    """

    # Try to update the sub/ses-ids
    subid = re.sub(f'^sub-', '', subid)
    if cleanup:
        subid = cleanup_value(subid)
    if sesid:
        sesid = re.sub(f'^ses-', '', sesid)
        if cleanup:
            sesid = cleanup_value(sesid)

    # Compose a bidsname from valid BIDS entities only
    bidsname = f"sub-{subid}{add_prefix('_ses-', sesid)}"                       # Start with the subject/session identifier
    for entitykey in [entities[entity]['entity'] for entity in entitiesorder]:
        bidsvalue = run['bids'].get(entitykey)                                  # Get the entity data from the run
        if not bidsvalue:
            bidsvalue = ''
        if isinstance(bidsvalue, list):
            bidsvalue = bidsvalue[bidsvalue[-1]]                                # Get the selected item
        elif not (entitykey=='run' and bidsvalue.replace('<','').replace('>','').isdecimal()):
            bidsvalue = run['datasource'].dynamicvalue(bidsvalue, cleanup=True, runtime=runtime)
        if bidsvalue:
            if cleanup:
                bidsvalue = cleanup_value(bidsvalue)
            bidsname = f"{bidsname}_{entitykey}-{bidsvalue}"                    # Append the key-value data to the bidsname
    suffix = run['bids'].get('suffix')
    if cleanup and suffix:
        suffix = cleanup_value(suffix)
    bidsname = f"{bidsname}{add_prefix('_', suffix)}"                           # And end with the suffix

    return bidsname


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


def insert_bidskeyval(bidsfile: Union[str, Path], bidskey: str, newvalue: str) -> Union[Path, str]:
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
    subid = ''
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
    newbidsfile = (bidspath/get_bidsname(subid, sesid, run, cleanup=False)).with_suffix(bidsext)

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


def copymetadata(metasource: Path, metatarget: Path, extensions: list) -> dict:
    """
    Copies over or, in case of json-files, returns the content of 'metasource' data files

    NB: In future versions this function could also support returning the content of e.g. csv- or Excel-files

    :param metasource:  The filepath of the source-data file with associated / equally named meta-data files
    :param metatarget:  The filepath of the source-data file to with the (non-json) meta-data files are copied over
    :param extensions:  A list of file extensions of the meta-data files
    :return:            The meta-data of the json-file
    """

    metadict = {}
    for ext in extensions:
        metasource = metasource.with_suffix('').with_suffix(ext)
        metatarget = metatarget.with_suffix('').with_suffix(ext)
        if metasource.is_file():
            LOGGER.info(f"Copying source data from: '{metasource}''")
            if ext == '.json':
                with metasource.open('r') as json_fid:
                    metadict = json.load(json_fid)
                if not isinstance(metadict, dict):
                    LOGGER.error(f"Skipping unexpectedly formatted meta-data in: {metasource}")
                    metadict = {}
            else:
                if metatarget.is_file():
                    LOGGER.warning(f"Deleting unexpected existing data-file: {metatarget}")
                    metatarget.unlink()
                shutil.copy2(metasource, metatarget)

    return metadict


def get_propertieshelp(propertieskey: str) -> str:
    """
    Reads the description of a matching attributes key in the source dictionary

    :param propertieskey:   The properties key for which the help text is obtained
    :return:                The obtained help text
    """

    # Return the description from the DICOM dictionary or a default text
    if propertieskey == 'filepath':
        return 'The path of the source file that is matched against the (regexp) pattern'
    if propertieskey == 'filename':
        return 'The name of the source file that is matched against the (regexp) pattern'
    if propertieskey == 'filesize':
        return 'The size of the source file that is matched against the (regexp) pattern'
    if propertieskey == 'nrfiles':
        return 'The nr of similar files in the folder that matched against the properties (regexp) patterns'


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
        return f"{attributeskey}\nA private attribute"


def get_datatypehelp(datatype: str) -> str:
    """
    Reads the description of the datatype in the schema/objects/datatypes.yaml file

    :param datatype:    The datatype for which the help text is obtained
    :return:            The obtained help text
    """

    if not datatype:
        return "Please provide a datatype"

    # Return the description for the datatype or a default text
    if datatype in bidsdatatypesdef:
        return f"{bidsdatatypesdef[datatype]['name']}\n{bidsdatatypesdef[datatype]['description']}"

    return f"{datatype}\nA private datatype"


def get_suffixhelp(suffix: str) -> str:
    """
    Reads the description of the suffix in the schema/objects/suffixes.yaml file

    :param suffix:      The suffix for which the help text is obtained
    :return:            The obtained help text
    """

    if not suffix:
        return "Please provide a suffix"

    # Return the description for the suffix or a default text
    if suffix in suffixes:
        return f"{suffixes[suffix]['name']}\n{suffixes[suffix]['description']}"

    return f"{suffix}\nA private suffix"


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

    return f"{entitykey}\nA private entity"


def get_metahelp(metakey: str) -> str:
    """
    Reads the description of a matching schema/metadata/metakey.yaml file

    :param metakey: The meta key for which the help text is obtained
    :return:        The obtained help text
    """

    if not metakey:
        return "Please provide a key-name"

    # Return the description from the metadata file or a default text
    if metakey in metadata:           # metadata[metaname]['name'] == metaname???
        description = metadata[metakey]['description']
        if metakey == 'IntendedFor':    # IntendedFor is a special search-pattern field in BIDScoin
            description += ('\nNB: These associated files can be dynamically searched for'
                            '\nduring bidscoiner runtime with glob-style matching patterns,'
                            '\n"such as <<Reward*_bold><Stop*_epi>>" (see documentation)')
        return f"{metadata[metakey]['name']}\n{description}"

    return f"{metakey}\nA private meta key"
