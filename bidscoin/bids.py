"""
BIDScoin module with bids/bidsmap related helper functions

@author: Marcel Zwiers
"""

import bids_validator
import copy
import json
import logging
import re
import shutil
import tempfile
import warnings
import fnmatch
import pandas as pd
import ast
import datetime
import jsonschema
from functools import lru_cache
from pathlib import Path
from typing import List, Set, Tuple, Union, Dict, Any, Iterable, NewType
from pydicom import dcmread, fileset, datadict
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    import sys
    sys.path.append(str(Path(__file__).parents[1]))
from bidscoin import bcoin, schemafolder, templatefolder, lsdirs, __version__
from bidscoin.utilities import dicomsort
from ruamel.yaml import YAML
yaml = YAML()
yaml.representer.ignore_aliases = lambda *data: True                            # Expand aliases (https://stackoverflow.com/questions/58091449/disabling-alias-for-yaml-file-in-python)

# Define custom data types (replace with proper classes or TypeAlias of Python >= 3.10)
Plugin     = NewType('Plugin',     Dict[str, Any])
Options    = NewType('Options',    Dict[str, Dict[str, Any]])
Properties = NewType('Properties', Dict[str, Any])
Attributes = NewType('Attributes', Dict[str, Any])
Bids       = NewType('Bids',       Dict[str, Any])
Meta       = NewType('Meta',       Dict[str, Any])
Run        = NewType('Run',        Dict[str, Any])                              # Any = Union[Provenance, Properties, Attributes, Bids, Meta, DataSource]]) but we cannot yet refer to DataSource
Dataformat = NewType('Dataformat', Dict[str, Union[str, List[Run]]])
Bidsmap    = NewType('Bidsmap',    Dict[str, Union[Options, Dataformat]])

LOGGER = logging.getLogger(__name__)

# Read the BIDS schema data
with (schemafolder/'objects'/'datatypes.yaml').open('r') as _stream:
    bidsdatatypesdef = yaml.load(_stream)                                       # The valid BIDS datatypes, along with their full names and descriptions
datatyperules = {}
for _datatypefile in (schemafolder/'rules'/'files'/'raw').glob('*.yaml'):
    with _datatypefile.open('r') as _stream:
        datatyperules[_datatypefile.stem] = yaml.load(_stream)                  # The entities that can/should be present for each BIDS data type
with (schemafolder/'objects'/'suffixes.yaml').open('r') as _stream:
    suffixes = yaml.load(_stream)                                               # The descriptions of the valid BIDS file suffixes
with (schemafolder/'objects'/'entities.yaml').open('r') as _stream:
    entities = yaml.load(_stream)                                               # The descriptions of the entities present in BIDS filenames
with (schemafolder/'rules'/'entities.yaml').open('r') as _stream:
    entitiesorder = yaml.load(_stream)                                          # The order in which the entities should appear within filenames
with (schemafolder/'objects'/'metadata.yaml').open('r') as _stream:
    metafields = yaml.load(_stream)                                             # The descriptions of the valid BIDS metadata fields


class DataSource:
    def __init__(self, provenance: Union[str, Path]='', plugins: Dict[str, Plugin]=None, dataformat: str='', datatype: str='', subprefix: str='', sesprefix: str=''):
        """
        A source data type (e.g. DICOM or PAR) that can be converted to BIDS by the plugins

        :param provenance:  The full path of a representative file for this data source
        :param plugins:     The plugins that are used to interact with the source data type. Uses bidsmap['Options']['plugins'] format
        :param dataformat:  The dataformat name in the bidsmap, e.g. DICOM or PAR
        :param datatype:    The intended BIDS data type of the data source TODO: move to a separate BidsTarget/Mapping class
        :param subprefix:   The subprefix used in the sourcefolder
        :param sesprefix:   The sesprefix used in the sourcefolder
        """

        self.path: Path      = Path(provenance)
        self.datatype: str   = datatype
        self.dataformat: str = dataformat
        self.plugins         = plugins
        if not plugins:
            self.plugins = {}
        if not dataformat:
            self.is_datasource()
        self.subprefix: str  = subprefix
        self.sesprefix: str  = sesprefix
        self._cache: dict    = {}

    def resubprefix(self) -> str:
        """Returns the subprefix with escaped regular expression characters (except '-'). A single '*' wildcard is returned as ''"""
        return '' if self.subprefix=='*' else re.escape(self.subprefix).replace(r'\-','-')

    def resesprefix(self) -> str:
        """Returns the sesprefix with escaped regular expression characters (except '-'). A single '*' wildcard is returned as ''"""
        return '' if self.sesprefix=='*' else re.escape(self.sesprefix).replace(r'\-','-')

    def is_datasource(self) -> bool:
        """Returns True is the datasource has a valid dataformat"""

        if not self.path.is_file() or self.path.is_dir():
            return False

        for plugin, options in self.plugins.items():
            module = bcoin.import_plugin(plugin, ('is_sourcefile',))
            if module:
                try:
                    dataformat = module.is_sourcefile(self.path)
                except Exception as moderror:
                    dataformat = ''
                    LOGGER.exception(f"The {plugin} plugin crashed while reading {self.path}\n{moderror}")
                if dataformat:
                    self.dataformat: str = dataformat
                    return True

        if self.datatype:
            LOGGER.verbose(f"No plugins found that can read {self.datatype}: {self.path}")

        return False

    def properties(self, tagname: str, run: Run=None) -> Union[str, int]:
        """
        Gets the 'filepath[:regex]', 'filename[:regex]', 'filesize' or 'nrfiles' filesystem property. The filepath (with trailing "/")
        and filename can be parsed using an optional regular expression re.findall(regex, filepath/filename). The last match is returned
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
                        LOGGER.warning(f"Multiple matches {match} found when extracting '{tagname}' from '{self.path.parent.as_posix() + '/'}'. Using: {match[-1]}")
                    return match[-1] if match else ''           # The last match is most likely the most informative
            elif tagname == 'filepath':
                return self.path.parent.as_posix() + '/'

            if tagname.startswith('filename:') and len(tagname) > 9:
                match = re.findall(tagname[9:], self.path.name)
                if match:
                    if len(match) > 1:
                        LOGGER.warning(f"Multiple matches {match} found when extracting '{tagname}' from '{self.path.name}'. Using: {match[0]}")
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

        except re.error as patternerror:
            LOGGER.error(f"Cannot compile regular expression property pattern '{tagname}': {patternerror}")

        except (IOError, OSError) as ioerror:
            LOGGER.warning(f"{ioerror}")

        return ''

    def attributes(self, attributekey: str, validregexp: bool=False, cache: bool=True) -> str:
        """
        Read the attribute value from the extended attributes, or else use the plugins to read it from the datasource

        :param attributekey: The attribute key for which a value is read from the json-file or from the datasource. A colon-separated regular expression can be appended to the attribute key (same as for the `filepath` and `filename` properties)
        :param validregexp:  If True, the regex meta-characters in the attribute value (e.g. '*') are replaced by '.',
                             e.g. to prevent compile errors in match_runvalue()
        :param cache:        Try to read the attribute from self._cache first if cache=True, else ignore the cache
        :return:             The attribute value or '' if the attribute could not be read from the datasource. NB: values are always converted to strings
        """

        attributeval = pattern = ''

        try:
            # Split off the regular expression pattern
            if ':' in attributekey:
                attributekey, pattern = attributekey.split(':', 1)

            # See if we have the data in our cache
            if attributekey in self._cache and cache:
                attributeval = str(self._cache[attributekey])

            # Read the attribute value from the sidecar file or from the datasource (using the plugins)
            else:
                extattr = self._extattributes()
                if attributekey in extattr:
                    attributeval = str(extattr[attributekey]) if extattr[attributekey] is not None else ''

                else:
                    for plugin, options in self.plugins.items():
                        module = bcoin.import_plugin(plugin, ('get_attribute',))
                        if module:
                            attributeval = module.get_attribute(self.dataformat, self.path, attributekey, options)
                            attributeval = str(attributeval) if attributeval is not None else ''
                        if attributeval:
                            break

                # Add the attribute value to the cache
                self._cache[attributekey] = attributeval

            if attributeval:

                # Apply the regular expression to the attribute value
                if validregexp:
                    try:            # Strip meta-characters to prevent match_runvalue() errors
                        re.compile(attributeval)
                    except re.error:
                        for metacharacter in ('.', '^', '$', '*', '+', '?', '{', '}', '[', ']', '\\', '|', '(', ')'):
                            attributeval = attributeval.strip().replace(metacharacter, '.')     # Alternative: attributeval = re.escape(attributeval)
                if pattern:
                    match = re.findall(pattern, attributeval)
                    if len(match) > 1:
                        LOGGER.warning(f"Multiple matches {match} found when extracting '{pattern}' from '{attributeval}'. Using: {match[0]}")
                    attributeval = match[0] if match else ''    # The first match is most likely the most informative (?)

        except re.error as patternerror:
            LOGGER.error(f"Cannot compile regular expression attribute pattern '{pattern}': {patternerror}")

        except (IOError, OSError) as ioerror:
            LOGGER.warning(f"{ioerror}")

        return attributeval

    def _extattributes(self) -> Attributes:
        """
        Read attributes from the json sidecar file if it is there

        :return:    The attribute key-value dictionary
        """
        attributes = {}
        jsonfile   = self.path.with_suffix('').with_suffix('.json') if self.path.name else Path()
        if jsonfile.is_file():
            LOGGER.bcdebug(f"Reading extended attributes from: {jsonfile}")
            with jsonfile.open('r') as json_fid:
                attributes = json.load(json_fid)
            if not isinstance(attributes, dict):
                LOGGER.warning(f"Skipping unexpectedly formatted meta-data in: {jsonfile}")
                return Attributes({})
            self._cache.update(attributes)

        return Attributes(attributes)

    def subid_sesid(self, subid: str=None, sesid: str=None) -> Tuple[str, str]:
        """
        Extract the cleaned-up subid and sesid from the datasource properties or attributes

        :param subid:   The subject identifier, i.e. name of the subject folder (e.g. 'sub-001' or just '001') or a dynamic source attribute.
                        Can be left unspecified/None (but not '') to use the default <<filepath:regex>> extraction
        :param sesid:   The optional session identifier, same as subid, except that sesid='' will return sesid='' instead of sesid='ses-'
        :return:        Updated (subid, sesid) tuple, including the BIDS-compliant 'sub-'/'ses-' prefixes
        """

        # Add the default value for subid and sesid if unspecified / None
        if subid is None:
            subid = f"<<filepath:/{self.resubprefix()}(.*?)/>>"
        if sesid is None:
            sesid = f"<<filepath:/{self.resubprefix()}.*?/{self.resesprefix()}(.*?)/>>"

        # Parse the sub-/ses-id's
        subid_ = self.dynamicvalue(subid, runtime=True)
        sesid  = self.dynamicvalue(sesid, runtime=True)
        if not subid_:
            LOGGER.error(f"Could not parse required sub-<label> label from {self.path} using: {subid} -> 'sub-'")
        subid = subid_

        # Add sub- and ses- prefixes if they are not there
        subid =  'sub-' + sanitize(re.sub(f"^{self.resubprefix()}", '', subid))
        sesid = ('ses-' + sanitize(re.sub(f"^{self.resesprefix()}", '', sesid))) if sesid else ''

        return subid, sesid

    def dynamicvalue(self, value, cleanup: bool=True, runtime: bool=False):
        """
        Replaces dynamic (bids/meta) values with source attributes of filesystem properties when they start with
        '<' and end with '>', but not with '<<' and '>>' unless runtime = True

        :param value:       The dynamic value that contains source attribute or filesystem property key(s)
        :param cleanup:     Sanitizes non-BIDS-compliant characters from the retrieved dynamic value if True
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
                value = sanitize(value)

        return value


def unpack(sesfolder: Path, wildcard: str='', workfolder: Path='', _subprefix: Union[str,None]='') -> Tuple[Set[Path], bool]:
    """
    Unpacks and sorts DICOM files in sourcefolder to a temporary folder if sourcefolder contains a DICOMDIR file or .tar.gz, .gz or .zip files

    :param sesfolder:   The full pathname of the folder with the source data
    :param wildcard:    A glob search pattern to select the tarball/zipped files (leave empty to skip unzipping)
    :param workfolder:  A root folder for temporary data
    :param _subprefix:  A pytest helper variable that is passed to dicomsort.sortsessions(args, subprefix=_subprefix)
    :return:            Either ([unpacked and sorted session folders], True), or ([sourcefolder], False)
    """

    # Search for zipped/tarball files
    tarzipfiles = list(sesfolder.glob(wildcard)) if wildcard else []

    # See if we have a flat unsorted (DICOM) data organization, i.e. no directories, but DICOM-files
    flatDICOM = not lsdirs(sesfolder) and get_dicomfile(sesfolder).is_file()

    # Check if we are going to do unpacking and/or sorting
    if tarzipfiles or flatDICOM or (sesfolder/'DICOMDIR').is_file():

        if tarzipfiles:
            LOGGER.info(f"Found zipped/tarball data in: {sesfolder}")
        else:
            LOGGER.info(f"Detected a {'flat' if flatDICOM else 'DICOMDIR'} data-structure in: {sesfolder}")

        # Create a (temporary) sub/ses workfolder for unpacking the data
        if not workfolder:
            workfolder = Path(tempfile.mkdtemp(dir=tempfile.gettempdir()))
        else:
            workfolder = Path(workfolder)/next(tempfile._get_candidate_names())
        worksesfolder = workfolder/sesfolder.relative_to(sesfolder.anchor)
        worksesfolder.mkdir(parents=True, exist_ok=True)

        # Copy everything over to the workfolder
        LOGGER.info(f"Making temporary copy: {sesfolder} -> {worksesfolder}")
        shutil.copytree(sesfolder, worksesfolder, dirs_exist_ok=True)

        # Unpack the zip/tarball files in the temporary folder
        sessions: Set[Path] = set()
        for tarzipfile in [worksesfolder/tarzipfile.name for tarzipfile in tarzipfiles]:
            LOGGER.info(f"Unpacking: {tarzipfile.name} -> {worksesfolder}")
            try:
                shutil.unpack_archive(tarzipfile, worksesfolder)
            except Exception as unpackerror:
                LOGGER.warning(f"Could not unpack: {tarzipfile}\n{unpackerror}")
                continue

            # Sort the DICOM files in the worksesfolder root immediately (to avoid name collisions)
            if not (worksesfolder/'DICOMDIR').is_file() and get_dicomfile(worksesfolder).name:
                sessions.update(dicomsort.sortsessions(worksesfolder, _subprefix, recursive=False))

        # Sort the DICOM files if not sorted yet (e.g. DICOMDIR)
        sessions.update(dicomsort.sortsessions(worksesfolder, _subprefix, recursive=True))

        return sessions, True

    else:

        return {sesfolder}, False


@lru_cache(maxsize=65536)
def is_dicomfile(file: Path) -> bool:
    """
    Checks whether a file is a DICOM-file. As a quick test, it first uses the feature that Dicoms have the
    string DICM hardcoded at offset 0x80. If that fails and (the file has a normal DICOM extension, e.g. '.dcm')
    then it is tested whether pydicom can read the file

    :param file:    The full pathname of the file
    :return:        Returns true if a file is a DICOM-file
    """

    if file.is_file():

        # Perform a quick test first
        with file.open('rb') as dicomfile:
            dicomfile.seek(0x80, 1)
            if dicomfile.read(4) == b'DICM':
                return True

        # Perform a proof of the pudding test (but avoid memory problems when reading a very large (e.g. EEG) source file)
        if file.suffix.lower() in ('.ima','.dcm','.dicm','.dicom',''):
            if file.name == 'DICOMDIR':
                return True
            dicomdata = dcmread(file, force=True)   # The DICM tag may be missing for anonymized DICOM files. NB: Force=False raises an error for non-DICOM files
            return 'Modality' in dicomdata

    return False


@lru_cache(maxsize=65536)
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
    except (OSError, IOError, UnicodeDecodeError) as ioerror:
        pass

    return False


def get_dicomfile(folder: Path, index: int=0) -> Path:
    """
    Gets a dicom-file from the folder (supports DICOMDIR)

    :param folder:  The full pathname of the folder
    :param index:   The index number of the dicom file
    :return:        The filename of the first dicom-file in the folder.
    """

    if folder.name.startswith('.'):
        LOGGER.verbose(f"Ignoring hidden folder: {folder}")
        return Path()

    if (folder/'DICOMDIR').is_file():
        dicomdir = fileset.FileSet(folder/'DICOMDIR')
        files    = [Path(file.path) for file in dicomdir]
    else:
        files = sorted(folder.iterdir())

    idx = 0
    for file in files:
        if file.name.startswith('.'):
            LOGGER.verbose(f"Ignoring hidden file: {file}")
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

    if folder.name.startswith('.'):
        LOGGER.verbose(f"Ignoring hidden folder: {folder}")
        return []

    parfiles: List[Path] = []
    for file in sorted(folder.iterdir()):
        if file.name.startswith('.'):
            LOGGER.verbose(f"Ignoring hidden file: {file}")
            continue
        if is_parfile(file):
            parfiles.append(file)

    return parfiles


def get_datasource(session: Path, plugins: Dict[str, Plugin], recurse: int=8) -> DataSource:
    """Gets a data source from the session inputfolder and its subfolders"""

    datasource = DataSource()
    for item in sorted(session.iterdir()):
        if item.name.startswith('.'):
            LOGGER.verbose(f"Ignoring hidden data-source: {item}")
            continue
        if item.is_dir() and recurse:
            datasource = get_datasource(item, plugins, recurse-1)
        elif item.is_file():
            datasource = DataSource(item, plugins)
        if datasource.dataformat:
            return datasource

    return datasource


@lru_cache(maxsize=65536)
def parse_x_protocol(pattern: str, dicomfile: Path) -> str:
    """
    Siemens writes a protocol structure as text into each DICOM file.
    This structure is necessary to recreate a scanning protocol from a DICOM,
    since the DICOM information alone wouldn't be sufficient.

    This function is derived from dac2bids.py from Daniel Gomez 29.08.2016
    https://github.com/dangom/dac2bids/blob/master/dac2bids.py

    :param pattern:     A regular expression: '^' + pattern + '\t = \t(.*)\\n'
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

    LOGGER.warning(f"Pattern: '{regexp.encode('unicode_escape').decode()}' not found in: {dicomfile}")
    return ''


# Profiling shows this is currently the most expensive function, therefore the (primitive but effective) _DICOMDICT_CACHE optimization
_DICOMDICT_CACHE = None
_DICOMFILE_CACHE = None
@lru_cache(maxsize=65536)
def get_dicomfield(tagname: str, dicomfile: Path) -> Union[str, int]:
    """
    Robustly extracts a DICOM attribute/tag value from a dictionary or from vendor specific fields.

    A XA-20 enhanced DICOM hack is made, i.e. if `EchoNumbers` is empty then an attempt is made to
    read it from the ICE dims (see https://github.com/rordenlab/dcm2niix/blob/master/Siemens/README.md)

    Another hack is to get 'PhaseEncodingDirection` (see https://neurostars.org/t/determining-bids-phaseencodingdirection-from-dicom/612/10)

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
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            from nibabel.nicom import csareader
            try:
                if dicomfile != _DICOMFILE_CACHE:
                    if dicomfile.name == 'DICOMDIR':
                        LOGGER.bcdebug(f"Getting DICOM fields from {dicomfile} seems dysfunctional (will raise dcmread error below if pydicom => v3.0)")
                    dicomdata = dcmread(dicomfile, force=True)          # The DICM tag may be missing for anonymized DICOM files
                    _DICOMDICT_CACHE = dicomdata
                    _DICOMFILE_CACHE = dicomfile
                else:
                    dicomdata = _DICOMDICT_CACHE

                try:                                                    # Try Pydicom's hexadecimal tag number first
                    value = eval(f"dicomdata[{tagname}].value")         # NB: This may generate e.g. UserWarning: Invalid value 'filepath' used with the 'in' operator: must be an element tag as a 2-tuple or int, or an element keyword
                except (NameError, KeyError, SyntaxError):
                    value = dicomdata.get(tagname,'') if tagname in dicomdata else ''  # Then try and see if it is an attribute name. NB: Do not use dicomdata.get(tagname, '') to avoid using its class attributes (e.g. 'filename')

                # Try a recursive search
                if not value and value != 0:
                    for elem in dicomdata.iterall():
                        if tagname in (elem.name, elem.keyword, str(elem.tag), str(elem.tag).replace(', ',',')):
                            value = elem.value
                            break

                if dicomdata.get('Modality') == 'MR':

                    # PhaseEncodingDirection patch (see https://neurostars.org/t/determining-bids-phaseencodingdirection-from-dicom/612/10)
                    if tagname == 'PhaseEncodingDirection' and not value:
                        if 'SIEMENS' in dicomdata.get('Manufacturer').upper() and csareader.get_csa_header(dicomdata):
                            csa = csareader.get_csa_header(dicomdata, 'Image')['tags']
                            pos = csa.get('PhaseEncodingDirectionPositive',{}).get('items')     # = [0] or [1]
                            dir = dicomdata.get('InPlanePhaseEncodingDirection')                # = ROW or COL
                            if dir == 'COL' and pos:
                                value = 'AP' if pos[0] else 'PA'
                            elif dir == 'ROW' and pos:
                                value = 'LR' if pos[0] else 'RL'
                        elif dicomdata.get('Manufacturer','').upper().startswith('GE'):
                            value = dicomdata.get('RectilinearPhaseEncodeReordering')           # = LINEAR or REVERSE_LINEAR

                    # XA-20 enhanced DICOM hack: Catch missing EchoNumbers from ice-dims
                    if tagname == 'EchoNumbers' and not value:
                        ice_dims = dicomdata.get((0x21, 1106)) or ''
                        if '_' in ice_dims:
                            value = ice_dims.split('_')[1]

                    # Try reading the Siemens CSA header. For V* versions the CSA header tag is (0029,1020), for XA versions (0021,1019). TODO: see if dicom_parser is supporting this
                    if not value and value != 0 and 'SIEMENS' in dicomdata.get('Manufacturer').upper() and csareader.get_csa_header(dicomdata):

                        if find_spec('dicom_parser'):
                            from dicom_parser import Image

                            for csa in ('CSASeriesHeaderInfo', 'CSAImageHeaderInfo'):
                                value = value if (value or value==0) else Image(dicomfile).header.get(csa)
                                for csatag in tagname.split('.'):           # E.g. CSA tagname = 'SliceArray.Slice.instance_number.Position.Tra'
                                    if isinstance(value, dict):             # Final CSA header attributes in dictionary of dictionaries
                                        value = value.get(csatag, '')
                                        if 'value' in value:                # Normal CSA (i.e. not MrPhoenixProtocol)
                                            value = value['value']
                                if value != 0:
                                    value = str(value or '')

                        else:

                            for modality in ('Series', 'Image'):
                                value = value if (value or value==0) else csareader.get_csa_header(dicomdata, modality)['tags']
                                for csatag in tagname.split('.'):           # NB: Currently MrPhoenixProtocol is not supported
                                    if isinstance(value, dict):             # Final CSA header attributes in dictionary of dictionaries
                                        value = value.get(csatag, {}).get('items', '')
                                        if isinstance(value, list) and len(value) == 1:
                                            value = value[0]
                                if value != 0:
                                    value = str(value or '')

                if not value and value != 0 and 'Modality' not in dicomdata:
                    raise ValueError(f"Missing mandatory DICOM 'Modality' field in: {dicomfile}")

            except (IOError, OSError) as ioerror:
                LOGGER.warning(f"Cannot read {tagname} from {dicomfile}\n{ioerror}")
                value = ''

            except Exception as dicomerror:
                LOGGER.warning(f"Could not read {tagname} from {dicomfile}\n{dicomerror}")
                value = ''

    # Cast the dicom data type to int or str (i.e. to something that yaml.dump can handle)
    if isinstance(value, int):
        return int(value)
    elif value is None:
        return ''
    else:
        return str(value)               # If it's a MultiValue type then flatten it


# Profiling shows this is currently the most expensive function, therefore the (primitive but effective) cache optimization
_TWIXHDR_CACHE  = None
_TWIXFILE_CACHE = None
@lru_cache(maxsize=65536)
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
        LOGGER.error(f"{twixfile} not found")
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

        except (IOError, OSError):
            LOGGER.warning(f'Cannot read {tagname} from {twixfile}')
            value = ''

        except Exception as twixerror:
            LOGGER.warning(f'Could not parse {tagname} from {twixfile}\n{twixerror}')
            value = ''

    # Cast the dicom data type to int or str (i.e. to something that yaml.dump can handle)
    if isinstance(value, int):
        return int(value)
    elif value is None:
        return ''
    else:
        return str(value)               # If it's a MultiValue type then flatten it


# Profiling shows this is currently the most expensive function, therefore the (primitive but effective) _PARDICT_CACHE optimization
_PARDICT_CACHE = None
_PARFILE_CACHE = None
@lru_cache(maxsize=65536)
def get_parfield(tagname: str, parfile: Path) -> Union[str, int]:
    """
    Uses nibabel to extract the value from a PAR field (NB: nibabel does not yet support XML)

    :param tagname: Name of the PAR/XML field
    :param parfile: The full pathname of the PAR/XML file
    :return:        Extracted tag-values from the PAR/XML file
    """

    global _PARDICT_CACHE, _PARFILE_CACHE

    if not parfile.is_file():
        LOGGER.error(f"{parfile} not found")
        value = ''

    elif not is_parfile(parfile):
        LOGGER.warning(f"{parfile} is not a PAR/XML file, cannot read {tagname}")
        value = ''

    else:
        try:
            from nibabel.parrec import parse_PAR_header

            if parfile != _PARFILE_CACHE:
                pardict = parse_PAR_header(parfile.open('r'))
                if 'series_type' not in pardict[0]:
                    raise ValueError(f'Cannot read {parfile}')
                _PARDICT_CACHE = pardict
                _PARFILE_CACHE = parfile
            else:
                pardict = _PARDICT_CACHE
            value = pardict[0].get(tagname, '')

        except (IOError, OSError):
            LOGGER.warning(f'Cannot read {tagname} from {parfile}')
            value = ''

        except Exception as parerror:
            LOGGER.warning(f'Could not parse {tagname} from {parfile}\n{parerror}')
            value = ''

    # Cast the dicom data type to int or str (i.e. to something that yaml.dump can handle)
    if isinstance(value, int):
        return int(value)
    elif value is None:
        return ''
    else:
        return str(value)               # If it's a MultiValue type then flatten it


# Profiling shows this is currently the most expensive function, therefore the (primitive but effective) cache optimization
_SPARHDR_CACHE  = None
_SPARFILE_CACHE = None
@lru_cache(maxsize=65536)
def get_sparfield(tagname: str, sparfile: Path) -> Union[str, int]:
    """
    Extracts the field value from the SPAR header-file

    :param tagname:     Name of the SPAR field
    :param sparfile:    The full pathname of the SPAR file
    :return:            Extracted tag-values from the SPAR file
    """

    global _SPARHDR_CACHE, _SPARFILE_CACHE

    value = ''
    if not sparfile.is_file():
        LOGGER.error(f"{sparfile} not found")

    else:
        try:
            if sparfile != _SPARFILE_CACHE:

                from spec2nii.Philips.philips import read_spar

                hdr = read_spar(sparfile)
                _SPARHDR_CACHE  = hdr
                _SPARFILE_CACHE = sparfile
            else:
                hdr = _SPARHDR_CACHE

            value = hdr.get(tagname, '')

        except ImportError:
            LOGGER.warning(f"The extra `spec2nii` library could not be found or was not installed (see the BIDScoin install instructions)")

        except (IOError, OSError):
            LOGGER.warning(f"Cannot read {tagname} from {sparfile}")

        except Exception as sparerror:
            LOGGER.warning(f"Could not parse {tagname} from {sparfile}\n{sparerror}")

    # Cast the dicom data type to int or str (i.e. to something that yaml.dump can handle)
    if isinstance(value, int):
        return int(value)
    elif value is None:
        return ''
    else:
        return str(value)  # If it's a MultiValue type then flatten it


# Profiling shows this is currently the most expensive function, therefore the (primitive but effective) cache optimization
_P7HDR_CACHE  = None
_P7FILE_CACHE = None
@lru_cache(maxsize=65536)
def get_p7field(tagname: str, p7file: Path) -> Union[str, int]:
    """
    Extracts the field value from the P-file header

    :param tagname:     Name of the SPAR field
    :param p7file:      The full pathname of the P7 file
    :return:            Extracted tag-values from the P7 file
    """

    global _P7HDR_CACHE, _P7FILE_CACHE

    value = ''
    if not p7file.is_file():
        LOGGER.error(f"{p7file} not found")

    else:
        try:
            if p7file != _P7FILE_CACHE:

                from spec2nii.GE.ge_read_pfile import Pfile

                hdr = Pfile(p7file).hdr
                _P7HDR_CACHE  = hdr
                _P7FILE_CACHE = p7file
            else:
                hdr = _P7HDR_CACHE

            value = getattr(hdr, tagname, '')
            if type(value) == bytes:
                try: value = value.decode('UTF-8')
                except UnicodeDecodeError: pass

        except ImportError:
            LOGGER.warning(f"The extra `spec2nii` library could not be found or was not installed (see the BIDScoin install instructions)")

        except (IOError, OSError):
            LOGGER.warning(f'Cannot read {tagname} from {p7file}')

        except Exception as p7error:
            LOGGER.warning(f'Could not parse {tagname} from {p7file}\n{p7error}')

    # Cast the dicom data type to int or str (i.e. to something that yaml.dump can handle)
    if isinstance(value, int):
        return int(value)
    elif value is None:
        return ''
    else:
        return str(value)  # If it's a MultiValue type then flatten it


# ---------------- All function below this point are bidsmap related. TODO: make a class out of them -------------------


def load_bidsmap(yamlfile: Path=Path(), folder: Path=templatefolder, plugins:Iterable[Union[Path,str]]=(), checks: Tuple[bool, bool, bool]=(True, True, True)) -> Tuple[Bidsmap, Path]:
    """
    Read the mapping heuristics from the bidsmap yaml-file. If yamlfile is not fullpath, then 'folder' is first searched before
    the default 'heuristics'. If yamfile is empty, then first 'bidsmap.yaml' is searched for, then 'bidsmap_template'. So fullpath
    has precedence over folder and bidsmap.yaml has precedence over the bidsmap_template.

    NB: A run['datasource'] = DataSource object is added to every run-item

    :param yamlfile:    The full pathname or basename of the bidsmap yaml-file
    :param folder:      Used when yamlfile=basename and not in the pwd: yamlfile is then assumed to be in the (bidscoin)folder. A bidsignore file in folder will be added to the bidsmap bidsignore items
    :param plugins:     List of plugins to be used (with default options, overrules the plugin list in the study/template bidsmaps). Leave empty to use all plugins in the bidsmap
    :param checks:      Booleans to check if all (bidskeys, bids-suffixes, bids-values) in the run are present according to the BIDS schema specifications
    :return:            Tuple with (1) ruamel.yaml dict structure, with all options, BIDS mapping heuristics, labels and attributes, etc. and (2) the fullpath yaml-file
    """

    # Input checking
    if not yamlfile.name:
        yamlfile = Path('bidsmap.yaml')
    if not yamlfile.suffix:
        yamlfile = yamlfile.with_suffix('.yaml')    # Add a standard file-extension if needed
    if len(yamlfile.parents) == 1 and not yamlfile.is_file():
        yamlfile = folder/yamlfile                  # Get the full path to the bidsmap yaml-file
    if not yamlfile.is_file():
        LOGGER.verbose(f"No existing bidsmap file found: {yamlfile}")
        return Bidsmap({}), yamlfile
    bidsignorefile = folder.parents[1]/'.bidsignore'

    # Read the heuristics from the bidsmap file
    if any(checks):
        LOGGER.info(f"Reading: {yamlfile}")
    with yamlfile.open('r') as stream:
        bidsmap = Bidsmap(yaml.load(stream))

    # Issue a warning if the version in the bidsmap YAML-file is not the same as the bidscoin version
    if 'bidscoin' in bidsmap['Options'] and 'version' in bidsmap['Options']['bidscoin']:
        bidsmapversion = bidsmap['Options']['bidscoin']['version']
    elif 'version' in bidsmap['Options']:                       # Handle legacy bidsmaps
        bidsmapversion = bidsmap['Options']['version']
    else:
        bidsmapversion = 'Unknown'
    if bidsmapversion.rsplit('.', 1)[0] != __version__.rsplit('.', 1)[0] and any(checks):
        LOGGER.warning(f'BIDScoiner version conflict: {yamlfile} was created with version {bidsmapversion}, but this is version {__version__}')
    elif bidsmapversion != __version__ and any(checks):
        LOGGER.info(f'BIDScoiner version difference: {yamlfile} was created with version {bidsmapversion}, but this is version {__version__}. This is normally OK but check the https://bidscoin.readthedocs.io/en/latest/CHANGELOG.html')

    # Make sure subprefix and sesprefix are strings
    subprefix = bidsmap['Options']['bidscoin']['subprefix'] = bidsmap['Options']['bidscoin']['subprefix'] or ''
    sesprefix = bidsmap['Options']['bidscoin']['sesprefix'] = bidsmap['Options']['bidscoin']['sesprefix'] or ''

    # Append the existing .bidsignore data from the bidsfolder and make sure bidsignore, unknowntypes, ignoretypes and notderivative are lists
    if isinstance(bidsmap['Options']['bidscoin'].get('bidsignore'), str):
        bidsmap['Options']['bidscoin']['bidsignore'] = bidsmap['Options']['bidscoin']['bidsignore'].split(';')
    if bidsignorefile.is_file():
        bidsmap['Options']['bidscoin']['bidsignore'] = list(set(list(bidsmap['Options']['bidscoin']['bidsignore']) + bidsignorefile.read_text().splitlines()))
    bidsmap['Options']['bidscoin']['bidsignore']    = list(set(bidsmap['Options']['bidscoin'].get('bidsignore') or []))
    bidsmap['Options']['bidscoin']['unknowntypes']  = list(set(bidsmap['Options']['bidscoin'].get('unknowntypes') or []))
    bidsmap['Options']['bidscoin']['ignoretypes']   = list(set(bidsmap['Options']['bidscoin'].get('ignoretypes') or []))
    bidsmap['Options']['bidscoin']['notderivative'] = list(set(bidsmap['Options']['bidscoin'].get('notderivative') or []))

    # Make sure we get a proper plugin options and dataformat sections (use plugin default bidsmappings when a template bidsmap is loaded)
    if not bidsmap['Options'].get('plugins'):
        bidsmap['Options']['plugins'] = {}
    if plugins:
        for plugin in [plugin for plugin in bidsmap['Options']['plugins'] if plugin not in plugins]:
            del bidsmap['Options']['plugins'][plugin]
    for plugin in plugins if plugins else bidsmap['Options']['plugins']:
        module = bcoin.import_plugin(plugin)
        if not bidsmap['Options']['plugins'].get(plugin):
            LOGGER.info(f"Adding default bidsmap options from the {plugin} plugin")
            bidsmap['Options']['plugins'][plugin] = module.OPTIONS if 'OPTIONS' in dir(module) else {}
        if 'BIDSMAP' in dir(module) and yamlfile.parent == templatefolder:
            for dataformat, bidsmappings in module.BIDSMAP.items():
                if dataformat not in bidsmap:
                    LOGGER.info(f"Adding default bidsmappings from the {plugin} plugin")
                    bidsmap[dataformat] = bidsmappings

    # Add missing provenance info, run dictionaries and bids entities
    run_ = create_run()
    for dataformat in bidsmap:
        if dataformat in ('$schema', 'Options'): continue
        bidsmap[dataformat]['session'] = bidsmap[dataformat]['session'] or ''   # Session-less data repositories
        for datatype in bidsmap[dataformat]:
            if not isinstance(bidsmap[dataformat][datatype], list): continue    # E.g. 'subject', 'session' and empty datatypes
            for index, run in enumerate(bidsmap[dataformat][datatype]):

                # Add missing provenance info
                if not run.get('provenance'):
                    run['provenance'] = str(Path(f"{subprefix.replace('*','')}-unknown/{sesprefix.replace('*','')}-unknown/{dataformat}_{datatype}_id{index+1:03}"))

                # Update the provenance store paths if needed (e.g. when the bids-folder was moved)
                provenance = Path(run['provenance'])
                if not provenance.is_file():
                    for n, part in enumerate(provenance.parts):
                        if part == 'bidscoin' and provenance.parts[n+1] == 'provenance':
                            store = folder/provenance.relative_to(*provenance.parts[0:n+1])
                            if store.is_file():
                                LOGGER.debug(f"Updating provenance: {provenance} -> {store}")
                                run['provenance'] = str(store)

                # Add missing run dictionaries (e.g. "meta" or "properties")
                for key, val in run_.items():
                    if key not in run or not run[key]:
                        run[key] = val

                # Add a DataSource object
                run['datasource'] = DataSource(run['provenance'], bidsmap['Options']['plugins'], dataformat, datatype, subprefix, sesprefix)

                # Add missing bids entities
                suffix = run['bids'].get('suffix')
                if run['datasource'].is_datasource():
                    suffix = run['datasource'].dynamicvalue(suffix, True, True)
                for typegroup in datatyperules.get(datatype, {}):                               # E.g. typegroup = 'nonparametric'
                    if suffix in datatyperules[datatype][typegroup]['suffixes']:                # run_found = True
                        for entity in datatyperules[datatype][typegroup]['entities']:
                            entitykey = entities[entity]['name']
                            if entitykey not in run['bids'] and entitykey not in ('sub','ses'):
                                LOGGER.info(f"Adding missing {dataformat}>{datatype}>{suffix} bidsmap entity key: {entitykey}")
                                run['bids'][entitykey] = ''

    # Validate the bidsmap entries
    check_bidsmap(bidsmap, checks)

    return bidsmap, yamlfile


def save_bidsmap(filename: Path, bidsmap: Bidsmap) -> None:
    """
    Save the BIDSmap as a YAML text file

    NB: The run['datasource'] = DataSource objects are not saved

    :param filename:    Full pathname of the bidsmap file
    :param bidsmap:     Full bidsmap data structure, with all options, BIDS labels and attributes, etc.
    :return:
    """

    # Remove the added DataSource object
    bidsmap = copy.deepcopy(bidsmap)
    for dataformat in bidsmap:
        if dataformat in ('$schema', 'Options'): continue
        if not bidsmap[dataformat]: continue
        for datatype in bidsmap[dataformat]:
            if not isinstance(bidsmap[dataformat][datatype], list): continue    # E.g. 'subject' and 'session'
            for run in bidsmap[dataformat][datatype]:
                run.pop('datasource', None)

    # Validate the bidsmap entries
    check_bidsmap(bidsmap, (False,True,True))
    validate_bidsmap(bidsmap, 0)

    LOGGER.info(f"Writing bidsmap to: {filename}")
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open('w') as stream:
        yaml.dump(bidsmap, stream)


def validate_bidsmap(bidsmap: Bidsmap, level: int=1) -> bool:
    """
    Test the bidsname of runs in the bidsmap using the bids-validator

    :param bidsmap: Full bidsmap data structure, with all options, BIDS labels and attributes, etc.
    :param level:  (-2) as 2 but no logging reports,
                   (-1) as 1 but no logging reports,
                    (0) as 1 but only report invalid runs,
                    (1) test only BIDS datatypes, i.e. datatypes not in `.bidsignore` or `ignoretypes`,
                    (2) test all converted datatypes, i.e. datatypes not in `ignoretypes`,
                    (3) test all datatypes
    :return:        True if all tested runs in bidsmap were bids-valid, otherwise False
    """

    if not bidsmap:
        LOGGER.info('No bidsmap to validate')
        return False

    valid       = True
    ignoretypes = bidsmap['Options']['bidscoin'].get('ignoretypes', [])
    bidsignore  = bidsmap['Options']['bidscoin'].get('bidsignore', [])

    # Test all the runs in the bidsmap
    LOGGER.info(f"bids-validator {bids_validator.__version__} test results (* = in .bidsignore):")
    for dataformat in bidsmap:
        if dataformat in ('$schema', 'Options'): continue
        if not bidsmap[dataformat]: continue
        for datatype in bidsmap[dataformat]:
            if not isinstance(bidsmap[dataformat][datatype], list): continue        # E.g. 'subject' and 'session'
            for run in bidsmap[dataformat][datatype]:
                bidsname = get_bidsname(f"sub-{sanitize(dataformat)}", '', run, False)
                ignore   = check_ignore(datatype, bidsignore) or check_ignore(bidsname+'.json', bidsignore, 'file')
                ignore_1 = datatype in ignoretypes or ignore
                ignore_2 = datatype in ignoretypes
                bidstest = bids_validator.BIDSValidator().is_bids(f"/sub-{sanitize(dataformat)}/{datatype}/{bidsname}.json")
                if level==3 or (abs(level)==2 and not ignore_2) or (-2<level<2 and not ignore_1):
                    valid = valid and bidstest
                if (level==0 and not bidstest) or (level==1 and not ignore_1) or (level==2 and not ignore_2) or level==3:
                    LOGGER.info(f"{bidstest}{'*' if ignore else ''}:\t{datatype}/{bidsname}.*")

    if valid:
        LOGGER.success('All generated bidsnames are BIDS-valid')
    else:
        LOGGER.warning('Not all generated bidsnames are BIDS-valid (make sure they are BIDS-ignored')

    return valid


def check_bidsmap(bidsmap: Bidsmap, checks: Tuple[bool, bool, bool]=(True, True, True)) -> Tuple[Union[bool, None], Union[bool, None], Union[bool, None]]:
    """
    Check all non-ignored runs in the bidsmap for required and optional entities using the BIDS schema files

    :param bidsmap: Full bidsmap data structure, with all options, BIDS labels and attributes, etc.
    :param checks:  Booleans to check if all (bids-keys, bids-suffixes, bids-values) in the run are present according to the BIDS schema specifications
    :return:        False if the keys, suffixes or values are proven to be invalid, otherwise None or True
    """

    results = (None, None, None)

    if not any(checks):
        return results

    if not bidsmap:
        LOGGER.info('No bidsmap run-items to check')
        return results

    # Check all the runs in the bidsmap
    LOGGER.info('Checking the bidsmap run-items:')
    for dataformat in bidsmap:
        if dataformat in ('$schema', 'Options'): continue    # TODO: Check Options
        if not bidsmap[dataformat]: continue
        for datatype in bidsmap[dataformat]:
            if not isinstance(bidsmap[dataformat][datatype], list):                  continue   # E.g. 'subject' and 'session'
            if datatype in bidsmap['Options']['bidscoin']['ignoretypes']:            continue   # E.g. 'exclude'
            if check_ignore(datatype, bidsmap['Options']['bidscoin']['bidsignore']): continue
            if bidsmap[dataformat][datatype] and results == (None, None, None):
                results = (True, True, True)                # We can now check the bidsmap
            for run in bidsmap[dataformat][datatype]:
                bidsname = get_bidsname('sub-foo', '', run, False)
                if check_ignore(bidsname+'.json', bidsmap['Options']['bidscoin']['bidsignore'], 'file'): continue
                isvalid = check_run(datatype, run, checks)
                results = [result and valid for result, valid in zip(results, isvalid)]

    if all([result==True for result, check in zip(results, checks) if check is True]):
        LOGGER.success('All run-items in the bidsmap are valid')
    elif any([result==False for result, check in zip(results, checks) if check is True]):
        LOGGER.warning('Not all run-items in the bidsmap are valid')
    else:
        LOGGER.verbose('Could not validate every run-item in the bidsmap')

    return results


def check_template(bidsmap: Bidsmap) -> bool:
    """
    Check all the datatypes in the template bidsmap for required and optional entities using the BIDS schema files

    :param bidsmap:     Full bidsmap data structure, with all options, BIDS labels and attributes, etc.
    :return:            True if the template bidsmap is valid, otherwise False
    """

    if not bidsmap:
        LOGGER.info('No bidsmap datatypes to check')
        return False

    valid       = True
    ignoretypes = bidsmap['Options']['bidscoin'].get('ignoretypes', [])
    bidsignore  = bidsmap['Options']['bidscoin'].get('bidsignore', [])

    # Check all the datatypes in the bidsmap
    LOGGER.verbose('Checking the template bidsmap datatypes:')
    for dataformat in bidsmap:
        if dataformat in ('$schema', 'Options'): continue
        for datatype in bidsmap[dataformat]:
            if not isinstance(bidsmap[dataformat][datatype], list): continue        # Skip datatype = 'subject'/'session'
            if not (datatype in bidsdatatypesdef or datatype in ignoretypes or check_ignore(datatype, bidsignore)):
                LOGGER.warning(f"Invalid {dataformat} datatype: '{datatype}' (you may want to add it to the 'bidsignore' list)")
                valid = False
            if datatype in ignoretypes: continue
            datatypesuffixes = []
            for run in bidsmap[dataformat][datatype]:
                datatypesuffixes.append(run['bids']['suffix'])
                for key, val in run['attributes'].items():
                    try:
                        re.compile(str(val))
                    except re.error:
                        LOGGER.warning(f"Invalid regex pattern in the {key} value '{val}' in: bidsmap[{dataformat}][{datatype}] -> {run['provenance']}\nThis may cause run-matching errors unless '{val}' is a literal attribute value")
            for typegroup in datatyperules.get(datatype, {}):
                for suffix in datatyperules[datatype][typegroup]['suffixes']:
                    if not (suffix in datatypesuffixes or suffix in str(bidsignore) or
                            '[DEPRECATED]'             in suffixes[suffix]['description'] or
                            '**Change:** Removed from' in suffixes[suffix]['description'] or
                            '**Change:** Replaced by'  in suffixes[suffix]['description']):
                        LOGGER.warning(f"Missing '{suffix}' run-item in: bidsmap[{dataformat}][{datatype}] (NB: this may be fine / a deprecated item)")
                        valid = False

    # Validate against the json schema
    with (templatefolder/'schema.json').open('r') as stream:
        schema = json.load(stream)
    try:
        jsonschema.validate(bidsmap, schema)
    except jsonschema.ValidationError as bidsmaperror:
        LOGGER.warning(f"Invalid template bidsmap:\n{bidsmaperror}")
        valid = False

    if valid:
        LOGGER.success('All datatypes and options in the template bidsmap are valid')
    else:
        LOGGER.warning('Not all datatypes and options in the template bidsmap are valid')

    return valid


def check_run(datatype: str, run: Run, checks: Tuple[bool, bool, bool]=(False, False, False)) -> Tuple[Union[bool, None], Union[bool, None], Union[bool, None]]:
    """
    Check run for required and optional entities using the BIDS schema files

    :param datatype:    The datatype that is checked, e.g. 'anat'
    :param run:         The run (list-item) with bids entities that are checked against missing values & invalid keys
    :param checks:      Booleans to report if all (bidskeys, bids-suffixes, bids-values) in the run are present according to the BIDS schema specifications
    :return:            True/False if the keys, suffixes or values are bids-valid or None if they cannot be checked
    """

    run_keysok   = None
    run_suffixok = None
    run_valsok   = None

    # Check if we have provenance info
    if all(checks) and not run['provenance']:
        LOGGER.info(f'No provenance info found for {datatype}/*_{run["bids"]["suffix"]}')

    # Check if we have a suffix and datatype rules
    if 'suffix' not in run['bids']:
        if checks[1]: LOGGER.warning(f'Invalid bidsmap: The {datatype} "suffix" key is missing ({datatype} -> {run["provenance"]})')
        return run_keysok, False, run_valsok                # The suffix is not BIDS-valid, we cannot check the keys and values
    if datatype not in datatyperules:
        return run_keysok, run_suffixok, run_valsok         # We cannot check anything

    # Use the suffix to find the right typegroup
    suffix = run['bids'].get('suffix')
    if 'datasource' in run and run['datasource'].path.is_file():
        suffix = run['datasource'].dynamicvalue(suffix, True, True)
    for typegroup in datatyperules[datatype]:

        if '<' not in suffix or '>' not in suffix:
            run_suffixok = False                            # We can now check the suffix

        if suffix in datatyperules[datatype][typegroup]['suffixes']:

            run_keysok   = True                             # We can now check the key
            run_suffixok = True                             # The suffix is valid
            run_valsok   = True                             # We can now check the value

            # Check if all expected entity-keys are present in the run and if they are properly filled
            for entity in datatyperules[datatype][typegroup]['entities']:
                entitykey    = entities[entity]['name']
                entityformat = entities[entity]['format']   # E.g. 'label' or 'index' (the entity type always seems to be 'string')
                bidsvalue    = run['bids'].get(entitykey)
                dynamicvalue = True if isinstance(bidsvalue, str) and ('<' in bidsvalue and '>' in bidsvalue) else False
                if entitykey in ('sub', 'ses'): continue
                if isinstance(bidsvalue, list):
                    bidsvalue = bidsvalue[bidsvalue[-1]]    # Get the selected item
                if entitykey not in run['bids']:
                    if checks[0]: LOGGER.warning(f'Invalid bidsmap: The "{entitykey}" key is missing ({datatype}/*_{run["bids"]["suffix"]} -> {run["provenance"]})')
                    run_keysok = False
                if bidsvalue and not dynamicvalue and bidsvalue!=sanitize(bidsvalue):
                    if checks[2]: LOGGER.warning(f'Invalid {entitykey} value: "{bidsvalue}" ({datatype}/*_{run["bids"]["suffix"]} -> {run["provenance"]})')
                    run_valsok = False
                elif not bidsvalue and datatyperules[datatype][typegroup]['entities'][entity]=='required':
                    if checks[2]: LOGGER.warning(f'Required "{entitykey}" value is missing ({datatype}/*_{run["bids"]["suffix"]} -> {run["provenance"]})')
                    run_valsok = False
                if bidsvalue and not dynamicvalue and entityformat=='index' and not str(bidsvalue).isdecimal():
                    if checks[2]: LOGGER.warning(f'Invalid {entitykey}-index: "{bidsvalue}" is not a number ({datatype}/*_{run["bids"]["suffix"]} -> {run["provenance"]})')
                    run_valsok = False

            # Check if all the bids-keys are present in the schema file
            entitykeys = [entities[entity]['name'] for entity in datatyperules[datatype][typegroup]['entities']]
            for bidskey in run['bids']:
                if bidskey not in entitykeys + ['suffix']:
                    if checks[0]: LOGGER.warning(f'Invalid bidsmap: The "{bidskey}" key is not allowed according to the BIDS standard ({datatype}/*_{run["bids"]["suffix"]} -> {run["provenance"]})')
                    run_keysok = False
                    if run_valsok: run_valsok = None

            break

    # Hack: There are physio, stim and events entities in the 'task'-rules, which can be added to any datatype
    if suffix in datatyperules['task']['events']['suffixes'] + datatyperules['task']['timeseries']['suffixes']:
        bidsname     = get_bidsname('sub-foo', '', run, False, 'datasource' in run and run['datasource'].path.is_file())
        run_suffixok = bids_validator.BIDSValidator().is_bids(f"/sub-foo/{datatype}/{bidsname}.json")  # NB: Using the BIDSValidator sounds nice but doesn't give any control over the BIDS-version
        run_valsok   = run_suffixok
        LOGGER.bcdebug(f"bidsname={run_suffixok}: /sub-foo/{datatype}/{bidsname}.json")

    if checks[0] and run_keysok in (None, False):
        LOGGER.bcdebug(f'Invalid "{run_keysok}" key-checks in run-item: "{run["bids"]["suffix"]}" ({datatype} -> {run["provenance"]})\nRun["bids"]:\n{run["bids"]}')

    if checks[1] and run_suffixok is False:
        LOGGER.warning(f'Invalid run-item with suffix: "{run["bids"]["suffix"]}" ({datatype} -> {run["provenance"]})')
        LOGGER.bcdebug(f"Run['bids']:\n{run['bids']}")

    if checks[2] and run_valsok in (None, False):
        LOGGER.bcdebug(f'Invalid "{run_valsok}" val-checks in run-item: "{run["bids"]["suffix"]}" ({datatype} -> {run["provenance"]})\nRun["bids"]:\n{run["bids"]}')

    return run_keysok, run_suffixok, run_valsok


def check_ignore(entry: str, bidsignore: Union[str,list], datatype: str= 'dir') -> bool:
    """
    A rudimentary check whether `entry` should be BIDS-ignored. This function should eventually be replaced by bids_validator functionality
    See also https://github.com/bids-standard/bids-specification/issues/131

    :param entry:       The entry that is checked against the bidsignore (e.g. a directory/datatype such as `anat` or a file such as `sub-001_ct.nii.gz`)
    :param bidsignore:  The list or semicolon separated bidsignore pattern (e.g. from the bidscoin Options such as `mrs/;extra_data/;sub-*_ct.*`)
    :param datatype:    The entry datatype, i.e. 'dir' or 'file', that can be used to limit the check
    :return:            True if the entry should be ignored, else False
    """

    # Parse bidsignore to be a list (legacy bidsmaps)
    if isinstance(bidsignore, str):
        bidsignore = bidsignore.split(';')

    ignore = False
    for item in set(bidsignore + ['code/', 'sourcedata/', 'derivatives/']):
        if datatype == 'dir' and not item.endswith('/'): continue
        if datatype == 'file'    and item.endswith('/'): continue
        if item.endswith('/'):
            item = item[0:-1]
        if fnmatch.fnmatch(entry, item):
            ignore = True
            break

    return ignore


def strip_suffix(run: Run) -> Run:
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


def sanitize(label: str) -> str:
    """
    Converts a given label to a cleaned-up label that can be used as a BIDS label. Remove leading and trailing spaces;
    convert other spaces, special BIDS characters and anything that is not an alphanumeric to a ''. This will for
    example map "Joe's reward_task" to "Joesrewardtask"

    :param label:   The given label that potentially contains undesired characters
    :return:        The cleaned-up / BIDS-valid label
    """

    if label is None or label == '':
        return ''
    if not isinstance(label, str):
        return label

    special_characters = (' ', '_', '-','.')

    for special in special_characters:
        label = label.strip().replace(special, '')

    return re.sub(r'(?u)[^-\w.]', '', label)


def dir_bidsmap(bidsmap: Bidsmap, dataformat: str) -> List[Path]:
    """
    Make a provenance list of all the runs in the bidsmap[dataformat]

    :param bidsmap:     The bidsmap, with all the runs in it
    :param dataformat:  The information source in the bidsmap that is used, e.g. 'DICOM'
    :return:            List of all provenances
    """

    provenance = []
    for datatype in bidsmap.get(dataformat, []):
        if not isinstance(bidsmap[dataformat].get(datatype), list): continue  # E.g. 'subject' and 'session'
        for run in bidsmap[dataformat][datatype]:
            if not run['provenance']:
                LOGGER.warning(f'The bidsmap run {datatype} run does not contain provenance data')
            else:
                provenance.append(Path(run['provenance']))

    provenance.sort()

    return provenance


def create_run(datasource: DataSource=None, bidsmap: Bidsmap=None) -> Run:
    """
    Create an empty run-item with the proper structure, provenance info and a data source

    :param datasource:  The data source that is deepcopied and attached
    :param bidsmap:     The bidsmap, with all the bidscoin options in it (for prefix/plugin info)
    :return:            The created run
    """

    datasource = copy.deepcopy(datasource or DataSource())
    if bidsmap:
        datasource.plugins   = bidsmap['Options']['plugins']
        datasource.subprefix = bidsmap['Options']['bidscoin'].get('subprefix','')
        datasource.sesprefix = bidsmap['Options']['bidscoin'].get('sesprefix','')

    return Run(dict(provenance = str(datasource.path),
                    properties = {'filepath':'', 'filename':'', 'filesize':'', 'nrfiles':None},
                    attributes = {},
                    bids       = {},
                    meta       = {},
                    datasource = datasource))


def get_run(bidsmap: Bidsmap, datatype: str, suffix_idx: Union[int, str], datasource: DataSource) -> Run:
    """
    Find the (first) run in bidsmap[dataformat][bidsdatatype] with run['bids']['suffix_idx'] == suffix_idx

    :param bidsmap:     This could be a template bidsmap, with all options, BIDS labels and attributes, etc.
    :param datatype:    The datatype in which a matching run is searched for (e.g. 'anat')
    :param suffix_idx:  The name of the suffix that is searched for (e.g. 'bold') or the datatype index number
    :param datasource:  The datasource with the provenance file from which the properties, attributes and dynamic values are read
    :return:            The clean (filled) run item in the bidsmap[dataformat][bidsdatatype] with the matching suffix_idx,
                        otherwise an empty dict
    """

    runs = bidsmap.get(datasource.dataformat, {}).get(datatype, [])
    for index, run in enumerate(runs):
        if index == suffix_idx or run['bids']['suffix'] == suffix_idx:

            # Get a clean run (remove comments to avoid overly complicated commentedMaps from ruamel.yaml)
            run_ = create_run(datasource, bidsmap)
            run_['datasource'].datatype = datatype

            for propkey, propvalue in run['properties'].items():
                run_['properties'][propkey] = propvalue

            for attrkey, attrvalue in run['attributes'].items():
                if datasource.path.name:
                    run_['attributes'][attrkey] = datasource.attributes(attrkey, validregexp=True)
                else:
                    run_['attributes'][attrkey] = attrvalue

            # Replace the dynamic bids values, except the dynamic run-index (e.g. <<>>)
            for bidskey, bidsvalue in run['bids'].items():

                # NB: bidsvalue can be a (mutable) list
                bidsvalue = copy.copy(bidsvalue)
                if bidskey == 'run' and bidsvalue and (bidsvalue.replace('<','').replace('>','').isdecimal() or bidsvalue == '<<>>'):
                    run_['bids'][bidskey] = bidsvalue
                else:
                    run_['bids'][bidskey] = datasource.dynamicvalue(bidsvalue)

            # Replace the dynamic meta values, except the IntendedFor value (e.g. <<task>>)
            for metakey, metavalue in run['meta'].items():

                # NB: metavalue can be a (mutable) list
                metavalue = copy.copy(metavalue)
                if metakey == 'IntendedFor':
                    run_['meta'][metakey] = metavalue
                elif metakey in ('B0FieldSource', 'B0FieldIdentifier') and '<<session>>' in (metavalue or ''):
                    run_['meta'][metakey] = metavalue
                else:
                    run_['meta'][metakey] = datasource.dynamicvalue(metavalue, cleanup=False)

            return run_

    LOGGER.error(f"A '{datatype}' run with suffix_idx '{suffix_idx}' cannot be found in bidsmap['{datasource.dataformat}']")
    return Run({})


def find_run(bidsmap: Bidsmap, provenance: str, dataformat: str='', datatype: str='') -> Run:
    """
    Find the (first) run in bidsmap[dataformat][bidsdatatype] with run['provenance'] == provenance

    :param bidsmap:     This could be a template bidsmap, with all options, BIDS labels and attributes, etc.
    :param provenance:  The unique provenance that is used to identify the run
    :param dataformat:  The dataformat section in the bidsmap in which a matching run is searched for, e.g. 'DICOM'. Otherwise, all dataformats are searched
    :param datatype:    The datatype in which a matching run is searched for (e.g. 'anat'). Otherwise, all datatypes are searched
    :return:            The (unfilled) run item from the bidsmap[dataformat][bidsdatatype]
    """

    if dataformat:
        dataformats = (dataformat,)
    else:
        dataformats = [item for item in bidsmap if item not in ('$schema','Options') and bidsmap[item]]
    for dataformat in dataformats:
        if datatype:
            datatypes = (datatype,)
        else:
            datatypes = [item for item in bidsmap[dataformat] if item not in ('subject','session') and bidsmap[dataformat][item]]
        for dtype in datatypes:
            for run in bidsmap[dataformat].get(dtype,[]):
                if Path(run['provenance']) == Path(provenance):
                    return run

    LOGGER.debug(f"Could not find this [{dataformat}][{datatype}] run: '{provenance}")
    return Run({})


def delete_run(bidsmap: Bidsmap, provenance: Union[Run, str], datatype: str= '', dataformat: str='') -> None:
    """
    Delete the first matching run from the BIDS map

    :param bidsmap:     Full bidsmap data structure, with all options, BIDS labels and attributes, etc.
    :param provenance:  The provenance identifier of/or the run-item that is deleted
    :param datatype:    The datatype that of the deleted run_item (can be different from run_item['datasource']), e.g. 'anat'
    :param dataformat:  The dataformat section in the bidsmap in which the run is deleted, e.g. 'DICOM'
    :return:
    """

    if isinstance(provenance, str):
        run_item = find_run(bidsmap, provenance, dataformat)
        if not run_item:
            return
    else:
        run_item   = provenance
        provenance = run_item['provenance']

    if not dataformat:
        dataformat = run_item['datasource'].dataformat
    if not datatype:
        datatype = run_item['datasource'].datatype
    if dataformat in bidsmap:
        for index, run in enumerate(bidsmap[dataformat].get(datatype,[])):
            if Path(run['provenance']) == Path(provenance):
                del bidsmap[dataformat][datatype][index]
                return

    LOGGER.error(f"Could not find (and delete) this [{dataformat}][{datatype}] run: '{provenance}")


def append_run(bidsmap: Bidsmap, run: Run) -> None:
    """
    Append a cleaned-up run to the BIDS map

    :param bidsmap:     Full bidsmap data structure, with all options, BIDS labels and attributes, etc.
    :param run:         The run (listitem) that is appended to the datatype
    :return:
    """

    # Copy the values from the run to an empty dict
    run_ = create_run(run['datasource'], bidsmap)
    for item in run_:
        if item in ('provenance', 'datasource'):
            continue
        run_[item].update(copy.deepcopy(run[item]))
    run = run_

    dataformat = run['datasource'].dataformat
    datatype   = run['datasource'].datatype
    if not bidsmap.get(dataformat):
        bidsmap[dataformat] = {datatype: []}
    if not bidsmap.get(dataformat).get(datatype):
        bidsmap[dataformat][datatype] = [run]
    else:
        bidsmap[dataformat][datatype].append(run)


def update_bidsmap(bidsmap: Bidsmap, source_datatype: str, run: Run) -> None:
    """
    Update the BIDS map if the datatype changes:
    1. Remove the source run from the source datatype section
    2. Append the (cleaned and deepcopied) target run to the target datatype section

    Else:
    1. Use the provenance to look up the index number in that datatype
    2. Replace the run

    :param bidsmap:             Full bidsmap data structure, with all options, BIDS labels and attributes, etc.
    :param source_datatype:     The current datatype name, e.g. 'anat'
    :param run:                 The run item that is being moved to run['datasource'].datatype
    :return:
    """

    dataformat   = run['datasource'].dataformat
    run_datatype = run['datasource'].datatype
    num_runs_in  = len(dir_bidsmap(bidsmap, dataformat))

    # Assert that the target datatype is known
    if not run_datatype:
        LOGGER.error(f'The datatype of the run cannot be determined...')

    # Warn the user if the target run already exists when the run is moved to another datatype
    if source_datatype != run_datatype:
        if exist_run(bidsmap, run_datatype, run):
            LOGGER.error(f'The "{source_datatype}" run already exists in {run_datatype}...')

        # Delete the source run
        delete_run(bidsmap, run, source_datatype)

        # Append the (cleaned-up) target run
        append_run(bidsmap, run)

    else:
        for index, run_ in enumerate(bidsmap[dataformat][run_datatype]):
            if Path(run_['provenance']) == Path(run['provenance']):
                bidsmap[dataformat][run_datatype][index] = run
                break

    num_runs_out = len(dir_bidsmap(bidsmap, dataformat))
    if num_runs_out != num_runs_in:
        LOGGER.error(f"Number of runs in bidsmap['{dataformat}'] changed unexpectedly: {num_runs_in} -> {num_runs_out}")


def match_runvalue(attribute, pattern) -> bool:
    """
    Match the value items with the attribute string using regex. If both attribute
    and values are a list then they are directly compared as is, else they are converted
    to a string

    Examples:
        match_runvalue('my_pulse_sequence_name', 'filename')   -> False
        match_runvalue([1,2,3], [1,2,3])                       -> True
        match_runvalue('my_pulse_sequence_name', '^my.*name$') -> True
        match_runvalue('T1_MPRage', '(?i).*(MPRAGE|T1w).*')    -> True

    :param attribute:   The long string that is being searched in (e.g. a DICOM attribute)
    :param pattern:     A re.fullmatch regular expression pattern
    :return:            True if a match is found or both attribute and values are identical or
                        empty/None. False otherwise
    """

    # Consider it a match if both attribute and value are identical or empty/None
    if str(attribute)==str(pattern) or (not attribute and not pattern):
        return True

    if not pattern:
        return False

    # Make sure we start with proper string types
    attribute = str(attribute or '').strip()
    pattern   = str(pattern).strip()

    # See if the pattern matches the source attribute
    try:
        match = re.fullmatch(pattern, attribute)
    except re.error as patternerror:
        LOGGER.error(f"Cannot compile regular expression pattern '{pattern}': {patternerror}")
        match = None

    return match is not None


def exist_run(bidsmap: Bidsmap, datatype: str, run_item: Run) -> bool:
    """
    Checks the bidsmap to see if there is already an entry in runlist with the same properties and attributes as in the input run

    :param bidsmap:         Full bidsmap data structure, with all options, BIDS labels and attributes, etc.
    :param datatype:        The datatype in the source that is used, e.g. 'anat'. Empty values will search through all datatypes
    :param run_item:        The run-item that is searched for in the datatype
    :return:                True if the run exists in runlist, otherwise False
    """

    dataformat = run_item['datasource'].dataformat
    if not datatype:
        for dtype in bidsmap.get(dataformat,{}):
            if not isinstance(bidsmap[dataformat][dtype], list): continue   # E.g. 'subject' and 'session'
            if exist_run(bidsmap, dtype, run_item):
                return True

    if not bidsmap.get(dataformat, {}).get(datatype):
        return False

    for run in bidsmap[dataformat][datatype]:

        # Begin with match = False only if all attributes are empty
        match = any([run[matching][attrkey] not in [None,''] for matching in ('properties','attributes') for attrkey in run[matching]])  # Normally match==True, but make match==False if all attributes are empty

        # Search for a case where all run_item items match with the run_item items
        for matching in ('properties', 'attributes'):
            for itemkey, itemvalue in run_item[matching].items():
                value = run[matching].get(itemkey)          # Matching bids-labels which exist in one datatype but not in the other -> None
                match = match and match_runvalue(itemvalue, value)
                if not match:
                    break                                   # There is no point in searching further within the run_item now that we've found a mismatch

        # Stop searching if we found a matching run_item (i.e. which is the case if match is still True after all run tests)
        if match:
            return True

    return False


def get_matching_run(datasource: DataSource, bidsmap: Bidsmap, runtime=False) -> Tuple[Run, str]:
    """
    Find the first run in the bidsmap with properties and file attributes that match with the data source, and then
    through the attributes. Only non-empty properties and attributes are matched, except when runtime is True, then
    the empty attributes are also matched. The datatypes are searched for in this order:

    ignoredatatypes (e.g. 'exclude') -> normal bidsdatatypes (e.g. 'anat') -> unknowndatatypes (e.g. 'extra_data')

    Then update/fill the provenance, and the (dynamic) bids and meta values (bids values are cleaned-up to be BIDS-valid)

    :param datasource:  The data source from which the attributes are read. NB: The datasource.datatype attribute is updated
    :param bidsmap:     Full bidsmap data structure, with all options, BIDS keys and attributes, etc
    :param runtime:     Dynamic <<values>> are expanded if True
    :return:            (run, provenance) The matching and filled-in / cleaned run item, and if there is a match, the
                        provenance (i.e. unique identifier) of the run-item in the bidsmap. If there is no match then the
                        run is still populated with info from the source-file, but the returned provenance will be ''
    """

    unknowndatatypes: list = bidsmap['Options']['bidscoin'].get('unknowntypes',[])
    ignoredatatypes:  list = bidsmap['Options']['bidscoin'].get('ignoretypes',[])
    bidsdatatypes:    list = [dtype for dtype in bidsmap.get(datasource.dataformat) if dtype not in unknowndatatypes + ignoredatatypes + ['subject', 'session']]
    dataformat             = Dataformat(bidsmap.get(datasource.dataformat, {}))

    # Loop through all datatypes and runs; all info goes cleanly into run_ (to avoid formatting problem of the CommentedMap)
    if 'fmap' in bidsdatatypes:
        bidsdatatypes.insert(0, bidsdatatypes.pop(bidsdatatypes.index('fmap'))) # Put fmap at the front (to catch inverted polarity scans first
    run_ = create_run(datasource, bidsmap)
    for datatype in ignoredatatypes + bidsdatatypes + unknowndatatypes:         # The ordered datatypes in which a matching run is searched for

        if datatype not in dataformat:
            continue
        runs                = dataformat.get(datatype)
        datasource.datatype = datatype
        for run in runs or []:

            match = any([run[matching][attrkey] not in [None,''] for matching in ('properties','attributes') for attrkey in run[matching]])     # Normally match==True, but make match==False if all attributes are empty
            run_  = create_run(datasource, bidsmap)

            # Try to see if the sourcefile matches all the filesystem properties
            for propkey, propvalue in run['properties'].items():

                # Check if the attribute value matches with the info from the sourcefile
                if propvalue:
                    sourcevalue = datasource.properties(propkey)
                    match       = match and match_runvalue(sourcevalue, propvalue)

                # Do not fill the empty attribute with the info from the sourcefile but keep the matching expression
                run_['properties'][propkey] = propvalue

            # Try to see if the sourcefile matches all the attributes and fill all of them
            for attrkey, attrvalue in run['attributes'].items():

                # Check if the attribute value matches with the info from the sourcefile
                sourcevalue = datasource.attributes(attrkey, validregexp=True)
                if attrvalue or runtime:
                    match = match and match_runvalue(sourcevalue, attrvalue)

                # Fill the empty attribute with the info from the sourcefile
                run_['attributes'][attrkey] = sourcevalue

            # Try to fill the bids-labels
            for bidskey, bidsvalue in run['bids'].items():

                # NB: bidsvalue can be a (mutable) list
                bidsvalue = copy.copy(bidsvalue)

                # Replace the dynamic bids values, except the dynamic run-index (e.g. <<>>)
                if bidskey == 'run' and bidsvalue and (bidsvalue.replace('<','').replace('>','').isdecimal() or bidsvalue == '<<>>'):
                    run_['bids'][bidskey] = bidsvalue
                else:
                    run_['bids'][bidskey] = datasource.dynamicvalue(bidsvalue, runtime=runtime)

                # SeriesDescriptions (and ProtocolName?) may get a suffix like '_SBRef' from the vendor, try to strip it off
                run_ = strip_suffix(run_)

            # Try to fill the meta-data
            for metakey, metavalue in run['meta'].items():

                # NB: metavalue can be a (mutable) list
                metavalue = copy.copy(metavalue)

                # Replace the dynamic meta values, except the IntendedFor value (e.g. <<task>>)
                if metakey == 'IntendedFor':
                    run_['meta'][metakey] = metavalue
                elif metakey in ('B0FieldSource', 'B0FieldIdentifier') and '<<session>>' in (metavalue or ''):
                    run_['meta'][metakey] = metavalue
                else:
                    run_['meta'][metakey] = datasource.dynamicvalue(metavalue, cleanup=False, runtime=runtime)

            # Stop searching the bidsmap if we have a match
            if match:
                LOGGER.debug(f"Bidsmap match: {run['provenance']} -> {run_['provenance']}")
                return run_, run['provenance']

    # We don't have a match (all tests failed, so datatype should be the *last* one, e.g. unknowndatatype)
    return run_, ''


def get_derivatives(datatype: str, exceptions: Iterable=()) -> list:
    """
    Retrieves a list of suffixes that are stored in the derivatives folder (e.g. the qMRI maps). TODO: Replace with a more systematic/documented method
    """

    if datatype == 'anat':
        return [suffix for suffix in datatyperules[datatype]['parametric']['suffixes']
                if suffix not in tuple(exceptions) + ('UNIT1',)]        # The qMRI data (maps)
    elif datatype == 'fmap':
        return [suffix for typegroup in datatyperules[datatype] for suffix in datatyperules[datatype][typegroup]['suffixes']
                if suffix not in exceptions and typegroup not in ('fieldmaps','pepolar')]    # The non-standard fmaps (file collections)
    else:
        return []


def get_bidsname(subid: str, sesid: str, run: Run, validkeys: bool, runtime: bool=False, cleanup: bool=True) -> str:
    """
    Composes a filename as it should be according to the BIDS standard using the BIDS keys in run. The bids values are
    dynamically updated and cleaned, and invalid bids keys and empty bids values are ignored

    :param subid:       The subject identifier, i.e. name of the subject folder (e.g. 'sub-001' or just '001')
    :param sesid:       The optional session identifier, i.e. name of the session folder (e.g. 'ses-01' or just '01'). Can be left empty
    :param run:         The run mapping with the BIDS key-value pairs
    :param validkeys:   Removes non-BIDS-compliant bids-keys if True
    :param runtime:     Replaces dynamic bidsvalues if True
    :param cleanup:     Sanitizes non-BIDS-compliant characters from the filename if True
    :return:            The composed BIDS file-name (without file-extension)
    """

    # Try to update the sub/ses-ids
    subid = re.sub(f'^sub-', '', subid)
    sesid = re.sub(f'^ses-', '', sesid) if sesid else ''                        # Catch sesid = None
    if cleanup:
        subid = sanitize(subid)
        sesid = sanitize(sesid)

    # Compose the bidsname
    bidsname    = f"sub-{subid}{'_ses-'+sesid if sesid else ''}"                # Start with the subject/session identifier
    entitiekeys = [entities[entity]['name'] for entity in entitiesorder]        # Use the valid keys from the BIDS schema
    if not validkeys:                                                           # Use the (ordered valid + invalid) keys from the run item
        entitiekeys = [key for key in entitiekeys if key in run['bids']] + \
                      [key for key in run['bids'] if key not in entitiekeys and key!='suffix']
    for entitykey in entitiekeys:
        bidsvalue = run['bids'].get(entitykey)                                  # Get the entity data from the run item
        if not bidsvalue:
            bidsvalue = ''
        if isinstance(bidsvalue, list):
            bidsvalue = bidsvalue[bidsvalue[-1]]                                # Get the selected item
        elif runtime and not (entitykey=='run' and (bidsvalue.replace('<','').replace('>','').isdecimal() or bidsvalue == '<<>>')):
            bidsvalue = run['datasource'].dynamicvalue(bidsvalue, cleanup=True, runtime=runtime)
        if cleanup:
            bidsvalue = sanitize(bidsvalue)
        if bidsvalue:
            bidsname = f"{bidsname}_{entitykey}-{bidsvalue}"                    # Append the key-value data to the bidsname
    suffix = run['bids'].get('suffix')
    if runtime:
        suffix = run['datasource'].dynamicvalue(suffix, runtime=runtime)
    if cleanup:
        suffix = sanitize(suffix)
    bidsname = f"{bidsname}{'_'+suffix if suffix else ''}"                      # And end with the suffix

    return bidsname


def get_bidsvalue(bidsfile: Union[str, Path], bidskey: str, newvalue: str='') -> Union[Path, str]:
    """
    Sets the bidslabel, i.e. '*_bidskey-*_' is replaced with '*_bidskey-bidsvalue_'. If the key exists but is not in the
    bidsname (e.g. 'fallback') then, as a fallback, the newvalue is appended to the acquisition label. If newvalue is empty
    (= default), then the parsed existing bidsvalue is returned and nothing is set

    :param bidsfile:    The bidsname (e.g. as returned from get_bidsname or fullpath)
    :param bidskey:     The name of the bidskey, e.g. 'echo' or 'suffix'
    :param newvalue:    The new bidsvalue. NB: remove non-BIDS compliant characters beforehand (e.g. using sanitize)
    :return:            The bidsname with the new bidsvalue or, if newvalue is empty, the existing bidsvalue
    """

    # Check input
    if not bidskey and newvalue:
        return bidsfile                         # No fallback

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
        if f'_{bidskey}-' not in bidsname + 'suffix':       # Fallback: Append the newvalue to the 'acq'-value
            if '_acq-' not in bidsname:                     # Insert the 'acq' key right after task, ses or sub key-value pair (i.e. order as in entities.yaml)
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


def insert_bidskeyval(bidsfile: Union[str, Path], bidskey: str, newvalue: str, validkeys: bool) -> Union[Path, str]:
    """
    Inserts or replaces the bids key-label pair into the bidsfile. All invalid keys are removed from the name

    :param bidsfile:    The bidsname (e.g. as returned from get_bidsname or fullpath)
    :param bidskey:     The name of the new bidskey, e.g. 'echo' or 'suffix'
    :param newvalue:    The value of the new bidskey
    :param validkeys:   Removes non-BIDS-compliant bids-keys if True
    :return:            The bidsname with the new bids key-value pair
    """

    bidspath = Path(bidsfile).parent
    bidsname = Path(bidsfile).with_suffix('').stem
    bidsext  = ''.join(Path(bidsfile).suffixes)

    # Parse the key-value pairs and store all the run info
    run   = create_run()
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
    newbidsfile = (bidspath/get_bidsname(subid, sesid, run, validkeys, cleanup=False)).with_suffix(bidsext)

    if isinstance(bidsfile, str):
        newbidsfile = str(newbidsfile)
    return newbidsfile


def increment_runindex(outfolder: Path, bidsname: str, run: Run, scans_table: pd.DataFrame=None, targets: Set[Path]=()) -> str:
    """
    Checks if a file with the same bidsname already exists in the folder and then increments the dynamic runindex
    (if any) until no such file is found.

    NB: For <<>> runs, if the run-less file already exists, then add 'run-2' to bidsname and rename run-less files
    to 'run-1', and, optionally, do the same for entries in scans_table and targets (i.e. keep them in sync)

    :param outfolder:   The full pathname of the bids output folder
    :param bidsname:    The bidsname with a provisional runindex, e.g. from get_bidsname()
    :param run:         The run mapping with the BIDS key-value pairs
    :param scans_table  The scans.tsv table that need to remain in sync when renaming a run-less file
    :param targets:     The set of output targets that need to remain in sync when renaming a run-less file
    :return:            The bidsname with the original or incremented runindex
    """

    # Check input
    runval = str(run['bids'].get('run') or '')
    if not (runval.startswith('<<') and runval.endswith('>>') and (runval.replace('<','').replace('>','').isdecimal() or runval == '<<>>')):
        return bidsname
    bidsext  = ''.join(Path(bidsname).suffixes)
    bidsname = bidsname.split('.')[0]

    # Make an inventory of the runs
    runless_name  = insert_bidskeyval(bidsname, 'run', '', False)
    run1_name     = insert_bidskeyval(bidsname, 'run', '1', False)
    runless_files = list(outfolder.glob(f"{runless_name}.*"))
    run1_files    = list(outfolder.glob(f"{run1_name}.*"))

    # Start incrementing from run-1 if we have already renamed runless to run-1
    if run1_files and runval == '<<>>':
        bidsname = run1_name

    # Increment the run-index if the bidsfile already exists until that's no longer the case
    while list(outfolder.glob(f"{bidsname}.*")):        # The run already exists -> increment the run-index
        runindex = get_bidsvalue(bidsname, 'run') or '1'    # If run-less -> identify as existing run-1
        bidsname = insert_bidskeyval(bidsname, 'run', str(int(runindex) + 1), False)

    # Rename run-less to run-1 when dealing with a new run-2
    if runless_files and get_bidsvalue(bidsname, 'run') == '2':

        # Check if everything is OK
        if runless_files and run1_files:
            LOGGER.error(f"File already exists, cannot rename {outfolder/runless_name}.* -> {run1_name}.*")
            return bidsname + bidsext

        # Rename run-less to run-1
        for runless_file in runless_files:
            LOGGER.verbose(f"Found run-2 files for <<>> index, renaming\n{runless_file} -> {run1_name}")
            run1_file = (outfolder/run1_name).with_suffix(''.join(runless_file.suffixes))
            runless_file.replace(run1_file)
            if runless_file in targets:
                targets.remove(runless_file)
                targets.add(run1_file)
            run1_scan    = f"{run1_file.parent.name}/{run1_file.name}"          # NB: as POSIX
            runless_scan = f"{runless_file.parent.name}/{runless_file.name}"    # NB: as POSIX
            if scans_table is not None and runless_scan in scans_table.index:
                scans_table.rename(index={runless_scan: run1_scan}, inplace=True)

    return bidsname + bidsext


def check_runindices(session: Path) -> bool:
    """
    Checks if the run-indices with the acquisition times stored in the scans.tsv file (NB: that means that scans in
    e.g. `extra_data` folders are not checked)

    :param session: The session folder with the BIDS entity folders and scans.tsv file
    :return:        True when acquisition times all increase with the run-indices
    """

    # Read the acquisition times and run-indices from the scans.tsv file
    scans_tsv = next(session.glob('sub-*_scans.tsv'), None)
    if scans_tsv:
        scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
        for scan in scans_table.sort_index().index:

            # Check if the scan exists
            if not (session/scan).is_file():
                LOGGER.warning(f"File in {scans_tsv.name} does not exist: {scan}")

            # Check all the run-2, run-3, etc scans against their preceding scan
            if 'acq_time' in scans_table.columns:

                runindex = get_bidsvalue(scan, 'run')
                if runindex and int(runindex) > 1:
                    prevscan = scan.replace(f"_run-{runindex}", f"_run-{int(runindex) - 1}")

                    # Check if the preceding index exists in the table
                    if prevscan not in scans_table.index:
                        LOGGER.warning(f"Missing {prevscan} entry. Please check `{scans_tsv}`")
                        return False

                    # Check if the preceding scan was indeed acquired at an earlier time point
                    if not (pd.isna(scans_table.loc[scan, 'acq_time']) or pd.isna(scans_table.loc[prevscan, 'acq_time'])):
                        acq_time = datetime.datetime.fromisoformat(scans_table.loc[scan, 'acq_time'])
                        acq_prev = datetime.datetime.fromisoformat(scans_table.loc[prevscan, 'acq_time'])
                        if (acq_time - acq_prev).total_seconds() <= 0:
                            LOGGER.warning(f"Acquisition times do not increase with the run-indices. Please check `{scans_tsv}`")
                            return False

    return True


def updatemetadata(datasource: DataSource, targetmeta: Path, usermeta: Meta, extensions: Iterable, sourcemeta: Path=Path()) -> Meta:
    """
    Load the metadata from the target (json sidecar), then add metadata from the source (json sidecar) and finally add
    the user metadata (meta table). Source metadata other than json sidecars are copied over to the target folder. Special
    dynamic <<session>> values are replaced with the session label, and unused B0-field tags are removed

    NB: In future versions this function could also support more source metadata formats, e.g. yaml, csv- or Excel-files

    :param datasource:  The data source from which dynamic values are read
    :param targetmeta:  The filepath of the target data file with meta-data
    :param usermeta:    A user metadata dict, e.g. the meta table from a run-item
    :param extensions:  A list of file extensions of the source metadata files, e.g. as specified in bidsmap['Options']['plugins']['plugin']['meta']
    :param sourcemeta:  The filepath of the source data file with associated/equally named meta-data files (name may include wildcards). Leave empty to use datasource.path
    :return:            The combined target + source + user metadata
    """

    metapool = {}
    if not sourcemeta.name:
        sourcemeta = datasource.path

    # Add the target metadata to the metadict
    if targetmeta.is_file():
        with targetmeta.open('r') as json_fid:
            metapool = json.load(json_fid)

    # Add the source metadata to the metadict or copy it over
    for ext in set(extensions):
        for sourcefile in sourcemeta.parent.glob(sourcemeta.with_suffix('').with_suffix(ext).name):
            LOGGER.verbose(f"Copying source data from: '{sourcefile}''")

            # Put the metadata in metadict
            if ext == '.json':
                with sourcefile.open('r') as json_fid:
                    metadata = json.load(json_fid)
                if not isinstance(metadata, dict):
                    LOGGER.error(f"Skipping unexpectedly formatted meta-data in: {sourcefile}")
                    continue
                for metakey, metaval in metadata.items():
                    if metapool.get(metakey) and metapool.get(metakey) != metaval:
                        LOGGER.info(f"Overruling {metakey} sourcefile values in {targetmeta}: {metapool[metakey]} -> {metaval}")
                    else:
                        LOGGER.debug(f"Adding '{metakey}: {metaval}' to: {targetmeta}")
                    metapool[metakey] = metaval or None

            # Or just copy over the metadata file
            else:
                targetfile = targetmeta.parent/sourcefile.name
                if not targetfile.is_file():
                    shutil.copyfile(sourcefile, targetfile)

    # Add all the metadata to the metadict. NB: the dynamic `IntendedFor` value is handled separately later
    for metakey, metaval in usermeta.items():
        if metakey != 'IntendedFor' and not (metakey in ('B0FieldSource', 'B0FieldIdentifier') and '<<session>>' in (metaval or '')):
            metaval = datasource.dynamicvalue(metaval, cleanup=False, runtime=True)
            try:
                metaval = ast.literal_eval(str(metaval))  # E.g. convert stringified list or int back to list or int
            except (ValueError, SyntaxError):
                pass
        if metapool.get(metakey) and metapool.get(metakey) != metaval:
            LOGGER.info(f"Overruling {metakey} bidsmap values in {targetmeta}: {metapool[metakey]} -> {metaval}")
        else:
            LOGGER.debug(f"Adding '{metakey}: {metaval}' to: {targetmeta}")
        metapool[metakey] = metaval or None

    # Update B0FieldIdentifiers / Sources
    if '<<session>>' in (metapool.get('B0FieldSource') or ''):
        metapool['B0FieldSource']     = metapool['B0FieldSource'].replace('<<session>>', get_bidsvalue(targetmeta, 'ses'))
    if '<<session>>' in (metapool.get('B0FieldIdentifier') or ''):
        metapool['B0FieldIdentifier'] = metapool['B0FieldIdentifier'].replace('<<session>>', get_bidsvalue(targetmeta, 'ses'))

    # Remove unused (but added from the template) B0FieldIdentifiers / Sources
    if not metapool.get('B0FieldSource'):     metapool.pop('B0FieldSource', None)
    if not metapool.get('B0FieldIdentifier'): metapool.pop('B0FieldIdentifier', None)

    return Meta(metapool)


def addparticipant(participants_tsv: Path, subid: str='', sesid: str='', data: dict=None, dryrun: bool=False) -> Tuple[pd.DataFrame, dict]:
    """
    Read/create and/or add (if it's not there yet) a participant to the participants.tsv/.json file

    :param participants_tsv:    The participants.tsv file
    :param subid:               The subject label. Leave empty to just read the participants table (add nothing)
    :param sesid:               The session label
    :param data:                Personal data of the participant, such as sex or age
    :param dryrun:              Boolean to just display the participants info
    :return:                    The participants table
    """

    # TODO: Check that only values that are consistent over sessions go in the participants.tsv file, otherwise put them in a sessions.tsv file

    # Input check
    data = data or {}

    # Read the participants table
    if participants_tsv.is_file():
        table = pd.read_csv(participants_tsv, sep='\t', dtype=str)
        table.set_index(['participant_id'], verify_integrity=True, inplace=True)
    else:
        table = pd.DataFrame()
        table.index.name = 'participant_id'

    # Read the participants json sidecar
    participants_json = participants_tsv.with_suffix('.json')
    if participants_json.is_file():
        with participants_json.open('r') as json_fid:
            meta = json.load(json_fid)
    else:
        meta = {}

    # Add the participant row
    data_added = False
    if subid:
        if subid not in table.index:
            if sesid:
                table.loc[subid, 'session_id'] = sesid
            table.loc[subid, 'group'] = None
            data_added                = True
        for key in data:
            if key not in table or pd.isnull(table.loc[subid, key]) or table.loc[subid, key] == 'n/a':
                table.loc[subid, key] = data[key]
                data_added            = True

        # Write the data to the participants tsv-file
        if data_added:
            LOGGER.verbose(f"Writing {subid} subject data to: {participants_tsv}")
            if not dryrun:
                table.replace('', 'n/a').to_csv(participants_tsv, sep='\t', encoding='utf-8', na_rep='n/a')

            # Create/write to the json participants table sidecar file
            key_added = False
            if not meta.get('participant_id'):
                meta['participant_id'] = {'Description': 'Unique participant identifier'}
                key_added              = True
            if not meta.get('session_id') and 'session_id' in table.columns:
                meta['session_id'] = {'Description': 'Session identifier'}
                key_added          = True
            if not meta.get('group') and 'group' in table.columns:
                meta['group'] = {'Description': 'Group identifier'}
                key_added     = True
            for col in table.columns:
                if col not in meta:
                    key_added = True
                    meta[col] = dict(LongName    = 'Long (unabbreviated) name of the column',
                                     Description = 'Description of the the column',
                                     Levels      = dict(Key='Value (This is for categorical variables: a dictionary of possible values (keys) and their descriptions (values))'),
                                     Units       = 'Measurement units. [<prefix symbol>]<unit symbol> format following the SI standard is RECOMMENDED')

            # Write the data to the participant sidecar file
            if key_added:
                LOGGER.verbose(f"Writing subject meta data to: {participants_json}")
                if not dryrun:
                    with participants_json.open('w') as json_fid:
                        json.dump(meta, json_fid, indent=4)

    return table, meta


def bidsprov(sesfolder: Path, source: Path, runid: str='', datatype: str='unknown', targets: Iterable[Path]=()) -> pd.DataFrame:
    """
    Save data transformation information in the bids/code/bidscoin folder (in the future this may be done in accordance with BEP028)

    You can use bidsprov(sesfolder, Path()) to return the provenance dataframe

    :param sesfolder:   The bids subject/session folder
    :param source:      The source file or folder that is being converted
    :param runid:       The bidsmap runid that was used to map the source data, e.g. as returned from get_matching_run()
    :param datatype:    The BIDS datatype/name of the subfolder where the targets are saved (e.g. extra_data)
    :param targets:     The set of output files
    :return:            The dataframe with the provenance data
    """

    # Check the input
    bidsfolder = sesfolder.parent
    if bidsfolder.name.startswith('sub-'):
        bidsfolder = bidsfolder.parent
    provfile = bidsfolder/'code'/'bidscoin'/'bidscoiner.tsv'
    targets  = [target.relative_to(bidsfolder) for target in sorted(targets)]

    # Read the provenance data and add the new data to it
    if provfile.is_file():
        provdata = pd.read_csv(provfile, sep='\t', index_col='source')
    else:
        provdata = pd.DataFrame(columns=['runid', 'datatype', 'targets'])
        provdata.index.name = 'source'

    # Write the provenance data
    if source.name:
        LOGGER.debug(f"Writing provenance data to: {provfile}")
        provdata.loc[str(source)] = [runid, datatype, ', '.join([f"{target.parts[1]+':' if target.parts[0]=='derivatives' else ''}{target.name}" for target in targets])]
        provdata.sort_index().to_csv(provfile, sep='\t')

    return provdata


def get_propertieshelp(propertieskey: str) -> str:
    """
    Reads the description of a matching attributes key in the source dictionary

    :param propertieskey:   The properties key for which the help text is obtained
    :return:                The obtained help text
    """

    # Return the description from the DICOM dictionary or a default text
    if propertieskey == 'filepath':
        return 'The path of the source file that is matched against the (regex) pattern'
    if propertieskey == 'filename':
        return 'The name of the source file that is matched against the (regex) pattern'
    if propertieskey == 'filesize':
        return 'The size of the source file that is matched against the (regex) pattern'
    if propertieskey == 'nrfiles':
        return 'The nr of similar files in the folder that matched against the properties (regex) patterns'

    return f"{propertieskey} is not a valid property-key"


def get_attributeshelp(attributeskey: str) -> str:
    """
    Reads the description of a matching attributes key in the source dictionary

    TODO: implement PAR/REC support

    :param attributeskey:   The attribute key for which the help text is obtained
    :return:                The obtained help text
    """

    if not attributeskey:
        return 'Please provide a key-name'

    # Return the description from the DICOM dictionary or a default text
    try:
        return f"{attributeskey}\nThe DICOM '{datadict.dictionary_description(attributeskey)}' attribute"

    except ValueError:
        return f"{attributeskey}\nAn unknown/private attribute"


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
        return f"{bidsdatatypesdef[datatype]['display_name']}\n{bidsdatatypesdef[datatype]['description']}"

    return f"{datatype}\nAn unknown/private datatype"


def get_suffixhelp(suffix: str, datatype: str) -> str:
    """
    Reads the description of the suffix in the schema/objects/suffixes.yaml file

    :param suffix:      The suffix for which the help text is obtained
    :param datatype:    The datatype of the suffix
    :return:            The obtained help text
    """

    if not suffix:
        return "Please provide a suffix"

    isderivative = ''
    if suffix in get_derivatives(datatype):
        isderivative = '\nNB: This is a BIDS derivatives datatype'

    # Return the description for the suffix or a default text
    if suffix in suffixes:
        return f"{suffixes[suffix]['display_name']}\n{suffixes[suffix]['description']}{isderivative}"

    return f"{suffix}\nAn unknown/private suffix"


def get_entityhelp(entitykey: str) -> str:
    """
    Reads the description of a matching entity=entitykey in the schema/entities.yaml file

    :param entitykey:   The bids key for which the help text is obtained
    :return:            The obtained help text
    """

    if not entitykey:
        return "Please provide a key-name"

    # Return the description from the entities or a default text
    for entity in entities:
        if entities[entity]['name'] == entitykey:
            return f"{entities[entity]['display_name']}\n{entities[entity]['description']}"

    return f"{entitykey}\nAn unknown/private entity"


def get_metahelp(metakey: str) -> str:
    """
    Reads the description of a matching schema/metadata/metakey.yaml file

    :param metakey: The meta key for which the help text is obtained
    :return:        The obtained help text
    """

    if not metakey:
        return "Please provide a key-name"

    # Return the description from the metadata file or a default text
    for field in metafields:
        if metakey == metafields[field].get('name'):
            description = metafields[field]['description']
            if metakey == 'IntendedFor':                            # IntendedFor is a special search-pattern field in BIDScoin
                description += ('\nNB: These associated files can be dynamically searched for'
                                '\nduring bidscoiner runtime with glob-style matching patterns,'
                                '\n"such as <<Reward*_bold><Stop*_epi>>" or <<dwi/*acq-highres*>>'
                                '\n(see documentation)')
            if metakey in ('B0FieldIdentifier', 'B0FieldSource'):   # <<session>> is a special dynamic value in BIDScoin
                description += ('\nNB: The `<<session>>` (sub)string will be replaced by the'
                                '\nsession label during bidscoiner runtime. In this way you can'
                                '\ncreate session-specific B0FieldIdentifier/Source tags (recommended)')

            return f"{metafields[field]['display_name']}\n{description}"

    return f"{metakey}\nAn unknown/private meta key"
