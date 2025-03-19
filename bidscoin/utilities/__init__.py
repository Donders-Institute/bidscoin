"""A package of useful helper tools"""

import tempfile
import warnings
import re
import shutil
import logging
from typing import Union
from pathlib import Path
from pydicom import dcmread, fileset, config
from functools import lru_cache
from importlib.util import find_spec
from bidscoin import is_hidden, lsdirs, DEBUG

config.INVALID_KEY_BEHAVIOR = 'IGNORE'              # Ignores warnings such as "UserWarning: Invalid value 'filepath' used with the 'in' operator: must be an element tag as a 2-tuple or int, or an element"
config.IGNORE               = 0 if DEBUG else 1     # Ignores warnings such as "The value length (68) exceeds the maximum length of 64 allowed for VR LO" and "Invalid value for VR UI: [..]"

LOGGER = logging.getLogger(__name__)


def unpack(sesfolder: Path, wildcard: str='', workfolder: Path='', _subprefix: Union[str,None]='') -> tuple[set[Path], bool]:
    """
    Unpacks and sorts DICOM files in sourcefolder to a temporary folder if sourcefolder contains a DICOMDIR file or .tar.gz, .gz or .zip files

    :param sesfolder:   The full pathname of the folder with the source data
    :param wildcard:    A glob search pattern to select the tarball/zipped files (leave empty to skip unzipping)
    :param workfolder:  A root folder for temporary data
    :param _subprefix:  A pytest helper variable that is passed to dicomsort.sortsessions(args, subprefix=_subprefix)
    :return:            Either ({a set of unpacked session folders}, True), or ({sesfolder}, False)
    """

    # Avoid circular import
    from bidscoin.utilities import dicomsort

    # Search for zipped/tarball files
    tarzipfiles = [*sesfolder.glob(wildcard)] if wildcard else []

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
        sessions: set[Path] = set()
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
        sessions.update(dicomsort.sortsessions(worksesfolder, _subprefix, None, recursive=True))

        return sessions, True

    else:

        return {sesfolder}, False


# Profiling shows dcmread is currently the most expensive function, therefore the (primitive but effective) _DICOMDICT_CACHE optimization
_DICOMDICT_CACHE = _DICOMFILE_CACHE = None
@lru_cache(maxsize=65536)
def is_dicomfile(file: Path) -> bool:
    """
    Checks whether a file is a DICOM-file. As a quick test, it first uses the feature that Dicoms have the
    string DICM hardcoded at offset 0x80. If that fails and (the file has a normal DICOM extension, e.g. '.dcm')
    then it is tested whether pydicom can read the file

    :param file:    The full pathname of the file
    :return:        Returns true if a file is a DICOM-file
    """

    global _DICOMDICT_CACHE, _DICOMFILE_CACHE

    if file.is_file():

        # Perform a quick test first
        with file.open('rb') as fid:
            fid.seek(0x80, 1)
            if fid.read(4) == b'DICM':
                return True

        # Perform a proof of the pudding test (but avoid memory problems when reading a very large (e.g. EEG) source file)
        if file.suffix.lower() in ('.ima','.dcm','.dicm','.dicom',''):
            if file.name == 'DICOMDIR':
                return True
            if file != _DICOMFILE_CACHE:
                dicomdata = dcmread(file, force=True)  # The DICM tag may be missing for anonymized DICOM files. NB: Force=False raises an error for non-DICOM files
                _DICOMDICT_CACHE = dicomdata
                _DICOMFILE_CACHE = file
            else:
                dicomdata = _DICOMDICT_CACHE
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

    if is_hidden(Path(folder.name)):
        return Path()

    if (folder/'DICOMDIR').is_file():
        dicomdir = fileset.FileSet(folder/'DICOMDIR')
        files    = [Path(file.path) for file in dicomdir]
    else:
        files = sorted(folder.iterdir())

    idx = 0
    for file in files:
        if not is_hidden(file.relative_to(folder)) and is_dicomfile(file):
            if idx == index:
                return file
            else:
                idx += 1

    return Path()


def get_parfiles(folder: Path) -> list[Path]:
    """
    Gets the Philips PAR-file from the folder

    :param folder:  The full pathname of the folder
    :return:        The filenames of the PAR-files in the folder.
    """

    if is_hidden(Path(folder.name)):
        return []

    parfiles: list[Path] = []
    for file in sorted(folder.iterdir()):
        if not is_hidden(file.relative_to(folder)) and is_parfile(file):
            parfiles.append(file)

    return parfiles


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


@lru_cache(maxsize=65536)
def get_dicomfield(tagname: str, dicomfile: Path) -> Union[str, int]:
    """
    Robustly extracts a DICOM attribute/tag value from a dictionary or from vendor specific fields.

    A XA-20 enhanced DICOM hack is made, i.e. if `EchoNumbers` is empty then an attempt is made to
    read it from the ICE dims (see https://github.com/rordenlab/dcm2niix/blob/master/Siemens/README.md)

    Another hack is to get 'PhaseEncodingDirection` (see https://neurostars.org/t/determining-bids-phaseencodingdirection-from-dicom/612/10)

    :param tagname:     DICOM attribute name (e.g. 'SeriesNumber') or Pydicom-style tag number (e.g. '0x00200011', '(0x20,0x11)', '(0020,0011)')
    :param dicomfile:   The full pathname of the dicom-file
    :return:            Extracted tag-values as a flat string
    """

    global _DICOMDICT_CACHE, _DICOMFILE_CACHE

    # Skip the RunItem properties
    if tagname in ('provenance', 'properties', 'attributes', 'bids', 'meta', 'events'):     # = RunItem().properties but that creates a circular import
        return ''

    if not dicomfile.is_file():
        LOGGER.warning(f"{dicomfile} not found")
        value = ''

    elif not is_dicomfile(dicomfile):
        LOGGER.warning(f"{dicomfile} is not a DICOM file, cannot read {tagname}")
        value = ''

    else:
        with warnings.catch_warnings():
            if not DEBUG: warnings.simplefilter('ignore', UserWarning)
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

                try:
                    tagpattern = r'\(?0x[\dA-F]+,?(0x)?[\dA-F]*\)?'                                 # Pattern for hexadecimal DICOM tags, e.g. '0x00200011', '0x20,0x11' or '(0x20,0x11)'
                    if re.fullmatch(rf"\[{tagpattern}](\[\d+]\[{tagpattern}])+", tagname):  # Pass bracketed nested tags directly to pydicom, e.g. [0x0008,0x1250][0][0x0008,0x1140][0][(0x0008,0x1155)]
                        value = eval(f"dicomdata{tagname}.value")
                    elif re.fullmatch(tagpattern, tagname):                                         # Try Pydicom's hexadecimal tag number (must be a 2-tuple or int)
                        value = eval(f"dicomdata[{tagname}].value")                                 # NB: This may generate e.g. UserWarning: Invalid value 'filepath' used with the 'in' operator: must be an element tag as a 2-tuple or int, or an element keyword
                    else:
                        value = dicomdata.get(tagname,'') if tagname in dicomdata else ''       # Then try and see if it is an attribute name. NB: Do not use dicomdata.get(tagname, '') to avoid using its class attributes (e.g. 'filename')
                except Exception:
                    value = ''

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

                    # XA enhanced DICOM hack: Catch missing EchoNumbers from the private ICE_Dims field (0x21, 0x1106)
                    if tagname in ('EchoNumber', 'EchoNumbers') and not value:
                        for elem in dicomdata.iterall():
                            if elem.tag == (0x21,0x1106):
                                value = elem.value.split('_')[1] if '_' in elem.value else ''
                                LOGGER.bcdebug(f"Parsed `EchoNumber(s)` from Siemens ICE_Dims `{elem.value}` as: {value}")
                                break

                    # Try reading the Siemens CSA header. For VA/VB-versions the CSA header tag is (0029,1020), for XA-versions (0021,1019). TODO: see if dicom_parser is supporting this
                    if not value and value != 0 and 'SIEMENS' in dicomdata.get('Manufacturer').upper() and csareader.get_csa_header(dicomdata):

                        if find_spec('dicom_parser'):
                            from dicom_parser import Image
                            LOGGER.bcdebug(f"Parsing {tagname} from the CSA header using `dicom_parser`")
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
                            LOGGER.bcdebug(f"Parsing {tagname} from the CSA header using `nibabel`")
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
_TWIXHDR_CACHE = _TWIXFILE_CACHE = None
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
_PARDICT_CACHE = _PARFILE_CACHE = None
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
_SPARHDR_CACHE = _SPARFILE_CACHE = None
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
_P7HDR_CACHE = _P7FILE_CACHE = None
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
            if type(value) is bytes:
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
