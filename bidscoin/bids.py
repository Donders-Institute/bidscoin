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
import pandas as pd
import ast
import datetime
import yaml
import jsonschema
import bidsschematools.schema as bst
import dateutil.parser
from fnmatch import fnmatch
from pathlib import Path
from typing import Union, Any, Iterable, NewType
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    import sys
    sys.path.append(str(Path(__file__).parents[1]))
from bidscoin import bcoin, schemafolder, templatefolder, is_hidden, __version__
from bidscoin.plugins import EventsParser

# Define custom data types (replace with proper classes or TypeAlias of Python >= 3.10)
Plugin     = NewType('Plugin',     dict[str, Any])
Plugins    = NewType('Plugin',     dict[str, Plugin])
Options    = NewType('Options',    dict[str, Any])
Properties = NewType('Properties', dict[str, Any])
Attributes = NewType('Attributes', dict[str, Any])
Bids       = NewType('Bids',       dict[str, Any])
Meta       = NewType('Meta',       dict[str, Any])

LOGGER = logging.getLogger(__name__)

# Read the BIDS schema data
bidsschema  = bst.load_schema(schemafolder)
"""The BIDS reference schema"""
filerules   = bidsschema.rules.files.raw
"""The entities that can/should be present for each BIDS data type"""
entityrules = bidsschema.rules.entities
"""The order in which the entities should appear within filenames"""
entities    = bidsschema.objects.entities
"""The descriptions of the entities present in BIDS filenames"""
extensions  = [ext.value for _,ext in bidsschema.objects.extensions.items() if ext.value not in ('.json', '.tsv', '.bval', '.bvec') and '/' not in ext.value]
"""The possible extensions of BIDS data files"""


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


class DataSource:
    """Reads properties, attributes and BIDS-related features to sourcefiles of a supported dataformat (e.g. DICOM or PAR)"""

    def __init__(self, sourcefile: Union[str, Path]='', plugins: Plugins=None, dataformat: str='', options: Options=None):
        """
        Reads (cached) properties and attributes from a source data file

        :param sourcefile:  The full filepath of the data source
        :param plugins:     The plugin dictionaries with their options
        :param dataformat:  The name of the dataformat (= section in the bidsmap, e.g. DICOM or PAR)
        :param options:     A (bidsmap) dictionary with 'subprefix' and 'sesprefix' fields
        """

        self.path       = Path(sourcefile or '')
        """The full path of a representative file for this data source"""
        self.dataformat = dataformat
        """The dataformat name of the plugin that interacts with the data source, e.g. DICOM or PAR"""
        self.plugins    = plugins or {}
        """The plugins that are used to interact with the source data type"""
        self.subprefix  = options['subprefix'] if options else ''
        """The subprefix used in the sourcefolder"""
        self.sesprefix  = options['sesprefix'] if options else ''
        """The sesprefix used in the sourcefolder"""
        self._cache     = {}

    def __eq__(self, other):
        """Equality test for all DataSource attributes"""

        if isinstance(other, DataSource):
            return (( self.path,  self.dataformat,  self.plugins,  self.subprefix,  self.sesprefix) ==
                    (other.path, other.dataformat, other.plugins, other.subprefix, other.sesprefix))
        else:
            return NotImplemented

    def __repr__(self):

        return (f"{self.__class__}\n"
                f"Path:\t\t{self.path}\n"
                f"Dataformat:\t{self.dataformat}\n"
                f"Plugins:\t{self.plugins}\n"
                f"Subprefix:\t{self.subprefix}\n"
                f"Sesprefix:\t{self.sesprefix}")

    def __str__(self):

        return f"[{self.dataformat}] {self.path}"

    @property
    def resubprefix(self) -> str:
        """Returns the subprefix with escaped regular expression characters (except '-'). A single '*' wildcard is returned as ''"""

        return '' if self.subprefix=='*' else re.escape(self.subprefix).replace(r'\-','-')

    @property
    def resesprefix(self) -> str:
        """Returns the sesprefix with escaped regular expression characters (except '-'). A single '*' wildcard is returned as ''"""

        return '' if self.sesprefix=='*' else re.escape(self.sesprefix).replace(r'\-','-')

    def has_support(self) -> str:
        """Find and return the dataformat supported by the plugins. If a dataformat is found, then update self.dataformat accordingly"""

        if not self.path.is_file() or self.path.is_dir():
            return ''

        for plugin, options in self.plugins.items():
            module = bcoin.import_plugin(plugin)
            if module:
                try:
                    supported = module.Interface().has_support(self.path, self.dataformat)
                except Exception as moderror:
                    supported = ''
                    LOGGER.exception(f"The {plugin} plugin crashed while reading {self.path}\n{moderror}")
                if supported:
                    if self.dataformat and self.dataformat != supported:
                        LOGGER.bcdebug(f"Inconsistent dataformat found, updating: {self.dataformat} -> {supported}")
                    self.dataformat: str = supported
                    return supported

        return ''

    def properties(self, tagname: str, runitem=None) -> Union[str, int]:
        """
        Gets the 'filepath[:regex]', 'filename[:regex]', 'filesize' or 'nrfiles' filesystem property. The filepath (with trailing "/")
        and filename can be parsed using an optional regular expression re.findall(regex, filepath/filename). The last match is returned
        for the filepath, the first match for the filename

        :param tagname: The name of the filesystem property key, e.g. 'filename', 'filename:sub-(.*?)_' or 'nrfiles'
        :param runitem: If given and tagname == 'nrfiles' then the nrfiles is dependent on the other filesystem matching-criteria
        :return:        The property value (posix with a trailing "/" if tagname == 'filepath') or '' if the property could not be parsed from the datasource
        """

        try:
            if tagname.startswith('filepath:') and len(tagname) > 9:
                match = re.findall(tagname[9:], self.path.parent.as_posix() + '/')
                if len(match) > 1:
                    LOGGER.warning(f"Multiple matches {match} found when extracting '{tagname}' from '{self.path.parent.as_posix() + '/'}'. Using: {match[-1]}")
                return match[-1] if match else ''               # The last match is most likely the most informative
            elif tagname == 'filepath':
                return self.path.parent.as_posix() + '/'

            if tagname.startswith('filename:') and len(tagname) > 9:
                match = re.findall(tagname[9:], self.path.name)
                if len(match) > 1:
                    LOGGER.warning(f"Multiple matches {match} found when extracting '{tagname}' from '{self.path.name}'. Using: {match[0]}")
                return match[0] if match else ''                # The first match is most likely the most informative (?)
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
                if runitem:                                         # Currently not used but keep the option open for future use
                    def match(file): return ((match_runvalue(file.parent,         runitem.properties['filepath']) or not runitem.properties['filepath']) and
                                             (match_runvalue(file.name,           runitem.properties['filename']) or not runitem.properties['filename']) and
                                             (match_runvalue(file.stat().st_size, runitem.properties['filesize']) or not runitem.properties['filesize']))
                    return len([file for file in self.path.parent.iterdir() if match(file)])
                else:
                    return len([*self.path.parent.iterdir()])

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

                elif self.dataformat or self.has_support():
                    for plugin, options in self.plugins.items():
                        module = bcoin.import_plugin(plugin)
                        if module:
                            attributeval = module.Interface().get_attribute(self.dataformat, self.path, attributekey, options)
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
                LOGGER.warning(f"Skipping unexpectedly formatted metadata in: {jsonfile}")
                return Attributes({})
            self._cache.update(attributes)

        return Attributes(attributes)

    def subid_sesid(self, subid: str=None, sesid: str=None) -> tuple[str, str]:
        """
        Extract the cleaned-up subid and sesid from the datasource properties or attributes

        :param subid:   The subject identifier, i.e. name of the subject folder (e.g. 'sub-001' or just '001') or a dynamic source attribute.
                        Can be left unspecified/None (but not '') to use the default <<filepath:regex>> extraction
        :param sesid:   The optional session identifier, same as subid, except that sesid='' will return sesid='' instead of sesid='ses-'
        :return:        Updated (subid, sesid) tuple, including the BIDS-compliant 'sub-'/'ses-' prefixes
        """

        # Add the default value for subid and sesid if unspecified/None
        if subid is None:
            subid = f"<<filepath:/{self.resubprefix}(.*?)/>>"
        if sesid is None:
            sesid = f"<<filepath:/{self.resubprefix}.*?/{self.resesprefix}(.*?)/>>"

        # Parse the sub-/ses-id's
        subid_ = self.dynamicvalue(subid, runtime=True)
        sesid  = self.dynamicvalue(sesid, runtime=True)
        if not subid_:
            LOGGER.error(f"Could not parse required sub-<label> label from {self} using: {subid} -> 'sub-'")
        subid = subid_

        # Add sub- and ses- prefixes if they are not there
        subid =  'sub-' + sanitize(re.sub(f"^{self.resubprefix}", '', subid))
        sesid = ('ses-' + sanitize(re.sub(f"^{self.resesprefix}", '', sesid))) if sesid else ''

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


class RunItem:
    """
    Reads and writes to/from a YAML runitem dictionary, i.e. the provenance string, the properties and attributies input
    dictionaries and the bids and meta output dictionaries (bidsmap > dataformat > datatype > run-item)
    """

    def __init__(self, dataformat: str='', datatype: str='', data: dict=None, options: Options=None, plugins: Plugins=None):
        """
        Create a run-item with the proper structure, provenance info and a data source. NB: Updates to the attributes propagate to the
        datasource, but not vice versa

        :param dataformat: The name of the dataformat (= section in the bidsmap)
        :param datatype:   The name of the datatype (= section in a dataformat)
        :param data:       The YAML run-item dictionary with the following keys: provenance, properties, attributes, bids, meta, events
        :param options:    The dictionary with the BIDScoin options
        :param plugins:    The plugin dictionaries with their options
        """

        # Create a YAML data dictionary with all required attribute keys
        data = data or {}
        for key, val in {'provenance': '', 'properties': {}, 'attributes': {}, 'bids': {'suffix':''}, 'meta': {}, 'events': {}}.items():
            if key not in data: data[key] = val
        super().__setattr__('_data', data)      # Use super() to initialize _data directly (without recurrence)

        # Set the regular attributes
        self.datasource = DataSource(data['provenance'], plugins, dataformat, options)
        """A DataSource object created from the run-item provenance"""
        self.dataformat = dataformat
        """The name of the dataformat"""
        self.datatype   = datatype
        """The name of the data type"""
        self.options    = options
        """The dictionary with the BIDScoin options"""
        self.plugins    = plugins
        """The plugin dictionaries with their options"""

        # Set the data attributes. TODO: create data classes instead?
        self.provenance = data['provenance']
        """The file path of the data source"""
        self.properties = Properties(data['properties'])
        """The file system properties from the data source that can be matched against other data sources"""
        for key, val in {'filepath': '', 'filename': '', 'filesize': '', 'nrfiles': None}.items():
            if key not in self.properties:
                self.properties[key] = val
        self.attributes = Attributes(data['attributes'])
        """The (header) attributes from the data source that can be matched against other data sources"""
        self.bids       = Bids(data['bids'])
        """The BIDS output dictionary (used for construting the BIDS filename)"""
        self.meta       = Meta(data['meta'])
        """The meta output dictionary (will be appended to the json sidecar file)"""
        self.events     = data['events']
        """The options to parse the stimulus presentation log file (if any) to BIDS compliant events"""

    def __getattr__(self, name: str):

        _name    = f"_{name}"
        _getattr = super().__getattribute__     # Using super() avoids infinite recurrence / deepcopy issues

        return _getattr('_data')[name] if name in _getattr('_data') else _getattr(_name)

    def __setattr__(self, name, value):

        _name    = f"_{name}"
        _getattr = super().__getattribute__     # Using super() avoids infinite recurrence / deepcopy issues
        _setattr = super().__setattr__          # Using super() avoids infinite recurrence / deepcopy issues

        if name in _getattr('_data'):
            _getattr('_data')[name] = value
        else:
            _setattr(_name, value)

        # Keep the datasource in sync with the provenance (just in case someone changes this)
        if name == 'provenance':
            self.datasource.path = Path(value)

        # Also update the identical twin attributes of the datasource (this should never happen)
        if name in ('dataformat', 'plugins', 'options'):
            setattr(self.datasource, name, value)

    def __str__(self):

        return f"[{self.dataformat}/{self.datatype}] {self.provenance}"

    def __repr__(self):

        return (f"{self.__class__}\n"
                f"Datasource:\t{self.datasource}\n"
                f"Dataformat:\t{self.dataformat}\n"
                f"Datatype:\t{self.datatype}\n"
                f"Provenance:\t{self.provenance}\n"
                f"Properties:\t{self.properties}\n"
                f"Attributes:\t{self.attributes}\n"
                f"Bids:\t\t{self.bids}\n"
                f"Meta:\t\t{self.meta}\n"
                f"Events:\t\t{self.events}")

    def __eq__(self, other):
        """A deep test for the RunItem attributes and YAML data"""

        if isinstance(other, RunItem):
            return (self.dataformat, self.datatype, self._data) == (other.dataformat, other.datatype, other._data)
        else:
            return NotImplemented

    def check(self, checks: tuple[bool, bool, bool]=(False, False, False)) -> tuple[Union[bool, None], Union[bool, None], Union[bool, None]]:
        """
        Check run for required and optional entities using the BIDS schema files

        :param checks:      Booleans to report if all (bidskeys, bids-suffixes, bids-values) in the run are present according to the BIDS schema specifications
        :return:            True/False if the keys, suffixes or values are bids-valid or None if they cannot be checked
        """

        run_keysok   = None
        run_suffixok = None
        run_valsok   = None
        datatype     = self.datatype
        bids         = self.bids
        provenance   = self.provenance

        # Check if we have provenance info
        if all(checks) and not provenance:
            LOGGER.info(f"No provenance info found for {datatype}/*_{bids['suffix']}")

        # Check if we have a suffix and data type rules
        if 'suffix' not in bids:
            if checks[1]: LOGGER.warning(f'Invalid bidsmap: The {datatype} "suffix" key is missing ({datatype} -> {provenance})')
            return run_keysok, False, run_valsok                # The suffix is not BIDS-valid, we cannot check the keys and values
        if datatype not in filerules:
            return run_keysok, run_suffixok, run_valsok         # We cannot check anything

        # Use the suffix to find the right typegroup
        suffix = bids.get('suffix')
        if self.datasource.path.is_file():
            suffix = self.datasource.dynamicvalue(suffix, True, True)
        for typegroup in filerules[datatype]:

            if '<' not in suffix or '>' not in suffix:
                run_suffixok = False                            # We can now check the suffix

            if suffix in filerules[datatype][typegroup].suffixes:

                run_keysok   = True                             # We can now check the key
                run_suffixok = True                             # The suffix is valid
                run_valsok   = True                             # We can now check the value

                # Check if all expected entity-keys are present in the run and if they are properly filled
                for entity in filerules[datatype][typegroup].entities:
                    entitykey    = entities[entity].name
                    entityformat = entities[entity].format      # E.g. 'label' or 'index' (the entity type always seems to be 'string')
                    bidsvalue    = bids.get(entitykey)
                    dynamicvalue = True if isinstance(bidsvalue, str) and ('<' in bidsvalue and '>' in bidsvalue) else False
                    if entitykey in ('sub', 'ses'): continue
                    if isinstance(bidsvalue, list):
                        bidsvalue = bidsvalue[bidsvalue[-1]]    # Get the selected item
                    if entitykey not in bids:
                        if checks[0]: LOGGER.warning(f'Invalid bidsmap: The "{entitykey}" key is missing ({datatype}/*_{bids["suffix"]} -> {provenance})')
                        run_keysok = False
                    if bidsvalue and not dynamicvalue and bidsvalue!=sanitize(bidsvalue):
                        if checks[2]: LOGGER.warning(f'Invalid {entitykey} value: "{bidsvalue}" ({datatype}/*_{bids["suffix"]} -> {provenance})')
                        run_valsok = False
                    elif not bidsvalue and filerules[datatype][typegroup].entities[entity]== 'required':
                        if checks[2]: LOGGER.warning(f'Required "{entitykey}" value is missing ({datatype}/*_{bids["suffix"]} -> {provenance})')
                        run_valsok = False
                    if bidsvalue and not dynamicvalue and entityformat=='index' and not str(bidsvalue).isdecimal():
                        if checks[2]: LOGGER.warning(f'Invalid {entitykey}-index: "{bidsvalue}" is not a number ({datatype}/*_{bids["suffix"]} -> {provenance})')
                        run_valsok = False

                # Check if all the bids-keys are present in the schema file
                entitykeys = [entities[entity].name for entity in filerules[datatype][typegroup].entities]
                for bidskey in bids:
                    if bidskey not in entitykeys + ['suffix']:
                        if checks[0]: LOGGER.warning(f'Invalid bidsmap: The "{bidskey}" key is not allowed according to the BIDS standard ({datatype}/*_{bids["suffix"]} -> {provenance})')
                        run_keysok = False
                        if run_valsok: run_valsok = None

                break

        # Hack: There are physio, stim and events entities in the 'task'-rules, which can be added to any datatype. They can have a `.tsv` or a `.tsv.gz` file extension
        if suffix in filerules.task.events.suffixes + filerules.task.timeseries.suffixes:
            bidsname = self.bidsname(validkeys=False, runtime=self.datasource.path.is_file())
            for ext in ('.tsv', '.tsv.gz'):  # NB: `ext` used to be '.json', which is more generic (but see https://github.com/bids-standard/bids-validator/issues/2113)
                if run_suffixok := bids_validator.BIDSValidator().is_bids(f"/sub-unknown/{datatype}/{bidsname}{ext}"): break    # NB: Using the BIDSValidator sounds nice but doesn't give any control over the BIDS-version
            run_valsok = run_suffixok
            LOGGER.bcdebug(f"bidsname (suffixok={run_suffixok}): /sub-unknown/{datatype}/{bidsname}.*")

        if checks[0] and run_keysok in (None, False):
            LOGGER.bcdebug(f'Invalid "{run_keysok}" key-checks in run-item: "{bids["suffix"]}" ({datatype} -> {provenance})\nRun["bids"]:\t{bids}')

        if checks[1] and run_suffixok is False:
            LOGGER.warning(f'Invalid run-item with suffix: "{bids["suffix"]}" ({datatype} -> {provenance})')
            LOGGER.bcdebug(f"Run['bids']:\t{bids}")

        if checks[2] and run_valsok in (None, False):
            LOGGER.bcdebug(f'Invalid "{run_valsok}" val-checks in run-item: "{bids["suffix"]}" ({datatype} -> {provenance})\nRun["bids"]:\t{bids}')

        return run_keysok, run_suffixok, run_valsok

    def strip_suffix(self):
        """
        Certain attributes such as SeriesDescriptions (but not ProtocolName!?) may get a suffix like '_SBRef' from the vendor,
        try to strip it off from the BIDS entities
        """

        # See if we have a suffix for this datatype
        bids = self.bids
        if 'suffix' in bids and bids['suffix']:
            suffix = bids['suffix'].lower()
        else:
            return

        # See if any of the BIDS labels ends with the same suffix. If so, then remove it
        for key in bids:
            if key == 'suffix':
                continue
            if isinstance(bids[key], str) and bids[key].lower().endswith(suffix):
                bids[key] = bids[key][0:-len(suffix)]       # NB: This will leave the added '_' and '.' characters, but they will be taken out later (as they are not BIDS-valid)

    def bidsname(self, subid: str='unknown', sesid: str='', validkeys: bool=False, runtime: bool=False, cleanup: bool=True) -> str:
        """
        Composes a filename as it should be according to the BIDS standard using the BIDS keys in run. The bids values are
        dynamically updated and cleaned, and invalid bids keys and empty bids values are ignored

        :param subid:       The subject identifier, i.e. name of the subject folder (e.g. 'sub-001' or just '001')
        :param sesid:       The optional session identifier, i.e. name of the session folder (e.g. 'ses-01' or just '01'). Can be left empty
        :param validkeys:   Removes non-BIDS-compliant bids-keys if True
        :param runtime:     Replaces dynamic bidsvalues if True
        :param cleanup:     Sanitizes non-BIDS-compliant characters from the filename if True
        :return:            The composed BIDS file-name (without file-extension)
        """

        # Try to update the sub/ses-ids
        subid = re.sub(f'^sub-', '', subid)
        sesid = re.sub(f'^ses-', '', sesid) if sesid else ''            # Catch sesid = None
        if cleanup:
            subid = sanitize(subid)
            sesid = sanitize(sesid)

        # Compose the bidsname
        bidsname    = f"sub-{subid}{'_ses-'+sesid if sesid else ''}"                # Start with the subject/session identifier
        entitiekeys = [entities[entity].name for entity in entityrules]        # Use the valid keys from the BIDS schema
        if not validkeys:                                                           # Use the (ordered valid + invalid) keys from the run item
            entitiekeys = [key for key in entitiekeys if key in self.bids] + \
                          [key for key in self.bids if key not in entitiekeys and key!='suffix']
        for entitykey in entitiekeys:
            bidsvalue = self.bids.get(entitykey)                                  # Get the entity data from the run item
            if not bidsvalue:
                bidsvalue = ''
            if isinstance(bidsvalue, list):
                bidsvalue = bidsvalue[bidsvalue[-1]]                                # Get the selected item
            elif runtime and not (entitykey=='run' and (bidsvalue.replace('<','').replace('>','').isdecimal() or bidsvalue == '<<>>')):
                bidsvalue = self.datasource.dynamicvalue(bidsvalue, cleanup=True, runtime=runtime)
            if cleanup:
                bidsvalue = sanitize(bidsvalue)
            if bidsvalue:
                bidsname = f"{bidsname}_{entitykey}-{bidsvalue}"                    # Append the key-value data to the bidsname
        suffix = self.bids.get('suffix')
        if runtime:
            suffix = self.datasource.dynamicvalue(suffix, runtime=runtime)
        if cleanup:
            suffix = sanitize(suffix)
        bidsname = f"{bidsname}{'_'+suffix if suffix else ''}"                      # And end with the suffix

        return bidsname

    def increment_runindex(self, outfolder: Path, bidsname: str, scans_table: pd.DataFrame=None, targets: set[Path]=()) -> str:
        """
        Checks if a file with the same bidsname already exists in the folder and then increments the dynamic runindex
        (if any) until no such file is found.

        NB: For <<>> runs, if the run-less file already exists, then add 'run-2' to bidsname and rename run-less files
        to 'run-1', and, optionally, do the same for entries in scans_table and targets (i.e. keep them in sync)

        :param outfolder:   The full pathname of the bids output folder
        :param bidsname:    The bidsname with a provisional runindex, e.g. from RunItem.bidsname()
        :param scans_table  The scans.tsv table that need to remain in sync when renaming a run-less file
        :param targets:     The set of output targets that need to remain in sync when renaming a run-less file
        :return:            The bidsname with the original or incremented runindex
        """

        # Check input
        runval = str(self.bids.get('run') or '')
        if not (runval.startswith('<<') and runval.endswith('>>') and (runval.replace('<','').replace('>','').isdecimal() or runval == '<<>>')):
            return bidsname
        bidsext  = ''.join(Path(bidsname).suffixes)
        bidsname = bidsname.split('.')[0]

        # Make an inventory of the runs
        runless_name  = insert_bidskeyval(bidsname, 'run', '', False)
        run1_name     = insert_bidskeyval(bidsname, 'run', '1', False)
        runless_files = [*outfolder.glob(f"{runless_name}.*")]
        run1_files    = [*outfolder.glob(f"{run1_name}.*")]

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

    def eventsparser(self) -> EventsParser:
        """Returns a plugin EventsParser instance to parse the stimulus presentation log file (if any)"""

        for name in self.plugins:
            if plugin := bcoin.import_plugin(name, (f"{self.dataformat}Events",)):
                return getattr(plugin, f"{self.dataformat}Events")(self.provenance, self.events, self.plugins[name])


class DataType:
    """Reads and writes to/from a YAML datatype dictionary (bidsmap > dataformat > datatype)"""

    def __init__(self, dataformat: str, datatype: str, data: list, options: Options, plugins: Plugins):
        """
        Reads from a YAML data type dictionary

        :param dataformat: The name of the dataformat (= section in the bidsmap)
        :param datatype:   The name of the datatype (= section in a dataformat)
        :param data:       The YAML data type dictionary, i.e. a list of runitems
        :param options:    The dictionary with the BIDScoin options
        :param plugins:    The plugin dictionaries with their options
        """

        self.dataformat = dataformat
        """The name of the dataformat"""
        self.datatype   = datatype
        """The name of the datatype"""
        self.options    = options
        """The dictionary with the BIDScoin options"""
        self.plugins    = plugins
        """The plugin dictionaries with their options"""
        self._data      = data
        """The YAML datatype dictionary, i.e. a list of runitems"""

    def __str__(self):

        return f"{self.datatype}"   # NB: Changing this likely breaks DataType support

    def __repr__(self):

        return f"{self.__class__} {self.datatype} ({len(self.runitems)})"

    def __eq__(self, other):
        """A shallow test if the DataType name is equal (so irrespective whether their runitems differ)"""

        if isinstance(other, (DataType, str)):
            return str(self) == str(other)
        else:
            return NotImplemented

    def __hash__(self):

        return hash(str(self))

    @property
    def runitems(self) -> list[RunItem]:
        """Returns a list of the RunItem objects for this datatype"""

        return [RunItem(self.dataformat, self.datatype, rundata, self.options, self.plugins) for rundata in self._data]

    def delete_run(self, provenance: str):
        """
        Delete a run-item from the datatype section

        :param provenance:  The provenance identifier of/or the run-item that is deleted
        """

        for index, runitem in enumerate(self.runitems):
            if Path(runitem.provenance) == Path(provenance):
                LOGGER.bcdebug(f"Deleting run: {runitem}")
                del self._data[index]
                return

        LOGGER.error(f"Could not find (and delete) this [{self.dataformat}][{self}] run: '{provenance}")

    def insert_run(self, runitem: RunItem, position: int=None):
        """
        Inserts a run-item (as is) to the DataType

        :param runitem:     The run item that is inserted in the list of run items
        :param position:    The position at which the run is inserted. The run is appended at the end if position is None
        """

        LOGGER.bcdebug(f"Inserting run: {runitem}")
        self._data.insert(len(self._data) if position is None else position, runitem._data)

    def replace_run(self, runitem: RunItem):
        """
        Replaces the existing run-item with the same provenance with a new run-item

        :param runitem: The new run-item
        """

        for index, rundata in enumerate(self._data):
            if Path(rundata.get('provenance') or '') == Path(runitem.provenance):
                LOGGER.bcdebug(f"Replacing run: {runitem} (unchanged = {self._data[index] == runitem._data})")
                self._data[index] = runitem._data
                return

        LOGGER.error(f"Could not replace {runitem} because it could not be found")


class DataFormat:
    """Reads and writes to/from a YAML dataformat dictionary (bidsmap > dataformat)"""

    def __init__(self, dataformat: str, data: dict, options: Options, plugins: Plugins):
        """
        Reads from a YAML dataformat dictionary

        :param dataformat: The name of the dataformat (= section in the bidsmap)
        :param data:       The YAML dataformat dictionary, i.e. participant items + a set of datatypes
        :param options:    The dictionary with the BIDScoin options
        :param plugins:    The plugin dictionaries with their options
        """

        # Initialize the getter/setter data dictionary
        self.__dict__['_data'] = {}

        self.dataformat = dataformat
        """The name of the dataformat"""
        self.options    = options
        """The dictionary with the BIDScoin options"""
        self.plugins    = plugins
        """The plugin dictionaries with their options"""
        self._data      = data
        """The YAML dataformat dictionary, i.e. participant items + a set of datatypes"""

    def __str__(self):

        return f"{self.dataformat}"   # NB: Changing this likely breaks DataFormat support

    def __repr__(self):

        datatypes = '\n'.join([f"\t{repr(dtype)}" for dtype in self.datatypes])
        return f"{self.__class__} {self.dataformat}\n{datatypes}"

    def __eq__(self, other):
        """A shallow test if the DataFormat name is equal (so irrespective whether their datatypes differ)"""

        if isinstance(other, (DataFormat, str)):
            return str(self) == str(other)
        else:
            return NotImplemented

    def __hash__(self):

        return hash(str(self))

    @property
    def participant(self) -> dict:
        """The data to populate the participants.tsv table"""

        return self._data['participant']

    @participant.setter
    def participant(self, value: dict):

        self._data['participant'] = value

    @property
    def subject(self) -> str:
        """The regular expression for extracting the subject identifier"""

        return self._data['participant']['participant_id']['value']

    @subject.setter
    def subject(self, value: str):

        self._data['participant']['participant_id']['value'] = value

    @property
    def session(self) -> str:
        """The regular expression for extracting the session identifier"""

        return self._data['participant']['session_id']['value']

    @session.setter
    def session(self, value: str):
        self._data['participant']['session_id']['value'] = value

    @property
    def datatypes(self) -> list[DataType]:
        """Gets a list of DataType objects for the dataformat"""

        return [DataType(self.dataformat, datatype, self._data[datatype], self.options, self.plugins) for datatype in self._data if datatype not in ('participant',)]

    def datatype(self, datatype: Union[str, DataType]) -> DataType:
        """Gets the DataType object for the dataformat"""

        return DataType(self.dataformat, str(datatype), self._data[str(datatype)], self.options, self.plugins)

    def add_datatype(self, datatype: Union[str, DataType]):
        """Adds a new datatype item to the dataformat"""

        _data    = datatype._data if isinstance(datatype, DataType) else []
        datatype = str(datatype)
        if datatype not in self._data:
            self._data[datatype] = _data
            LOGGER.bcdebug(f"Adding the '{datatype}' datatype to {self}")
        else:
            LOGGER.bcdebug(f"The {self} dataformat already contains the '{datatype}' datatype")

    def remove_datatype(self, datatype: Union[str, DataType]):
        """Removes a datatype from the dataformat"""

        datatype = str(datatype)
        if datatype not in self._data:
            LOGGER.bcdebug(f"The '{datatype}' datatype could not be removed from {self}")
            return
        else:
            self._data.pop(datatype, None)
            LOGGER.bcdebug(f"The '{datatype}' datatype was removed from {self}")

    def delete_runs(self, datatype: Union[str, DataType]=''):
        """Delete all run-items from the dataformat or only from a datatype section"""

        if not datatype:
            for datatype in self.datatypes:
                self.delete_runs(datatype)
        else:
            self._data[str(datatype)] = []


class BidsMap:
    """Reads and writes mapping heuristics from the bidsmap YAML-file"""

    def __init__(self, yamlfile: Path, folder: Path=templatefolder, plugins: Iterable[Union[Path,str]]=(), checks: tuple[bool,bool,bool]=(True,True,True)):
        """
        Read and standardize the bidsmap (i.e. add missing information and perform checks). If yamlfile is not fullpath, then the (bidscoin) 'folder' is first
        searched before the default 'heuristics'. If yamfile is empty, then first 'bidsmap.yaml' is searched for, then 'bidsmap_template'. So fullpath
        has precedence over folder and bidsmap.yaml has precedence over the bidsmap_template.

        :param yamlfile:    The full path or base name of the bidsmap yaml-file
        :param folder:      Used when yamlfile=base name and not in the pwd: yamlfile is then assumed to be in the (bids/code/bidscoin)folder. A bidsignore file in folder will be added to the bidsmap bidsignore items
        :param plugins:     List of plugins to be used (with default options, overrules the plugin list in the study/template bidsmaps). Leave empty to use all plugins in the bidsmap
        :param checks:      Booleans to check if all (bidskeys, bids-suffixes, bids-values) in the run are present according to the BIDS schema specifications
        """

        # Initialize the getter/setter data dictionary
        self.__dict__['_data'] = {}

        # Input checking
        self.plugins = plugins = plugins or {}
        """The plugins that are used to interact with the source data type"""
        self.store = {}
        """The in- and output folders for storing samples in the provenance store (NB: this is set by bidsmapper)"""
        if not yamlfile.suffix:
            yamlfile = yamlfile.with_suffix('.yaml')                # Add a standard file-extension if needed
        if len(yamlfile.parents) == 1 and not yamlfile.is_file():
            yamlfile = folder/yamlfile                              # Get the full path to the bidsmap yaml-file
        self.filepath = yamlfile = yamlfile.resolve()
        """The full path to the bidsmap yaml-file"""
        if not yamlfile.is_file():
            if yamlfile.name: LOGGER.info(f"No bidsmap file found: {yamlfile}")
            return

        # Read the heuristics from the bidsmap file
        if any(checks):
            LOGGER.info(f"Reading: {yamlfile}")
        with yamlfile.open('r') as stream:
            bidsmap_data = yaml.safe_load(stream)
        self._data = bidsmap_data
        """The raw YAML data"""

        # Issue a warning if the version in the bidsmap YAML-file is not the same as the bidscoin version
        options        = self.options
        bidsmapversion = options.get('version', 'Unknown')
        if bidsmapversion.rsplit('.', 1)[0] != __version__.rsplit('.', 1)[0] and any(checks):
            LOGGER.warning(f'BIDScoiner version conflict: {yamlfile} was created with version {bidsmapversion}, but this is version {__version__}')
        elif bidsmapversion != __version__ and any(checks):
            LOGGER.info(f'BIDScoiner version difference: {yamlfile} was created with version {bidsmapversion}, but this is version {__version__}. This is normally OK but check the https://bidscoin.readthedocs.io/en/latest/CHANGELOG.html')

        # Make sure subprefix and sesprefix are strings
        subprefix = options['subprefix'] = options['subprefix'] or ''
        sesprefix = options['sesprefix'] = options['sesprefix'] or ''

        # Append the existing .bidsignore data from the bidsfolder and make sure bidsignore, unknowntypes and ignoretypes are lists
        if isinstance(options.get('bidsignore'), str):
            options['bidsignore'] = options['bidsignore'].split(';')
        bidsignorefile = folder.parents[1]/'.bidsignore'
        if bidsignorefile.is_file():
            options['bidsignore'] = [*set([*options['bidsignore']] + bidsignorefile.read_text().splitlines())]
        options['bidsignore']     = sorted(set(options.get('bidsignore'))) or []
        options['unknowntypes']   = options.get('unknowntypes')  or []
        options['ignoretypes']    = options.get('ignoretypes')   or []

        # Make sure we get a proper plugin options and dataformat sections (use plugin default bidsmappings when a template bidsmap is loaded)
        if plugins:
            for plugin in [plugin for plugin in self.plugins if plugin not in plugins]:
                del self.plugins[plugin]
        for plugin in plugins if plugins else self.plugins:
            module = bcoin.import_plugin(plugin)
            if not self.plugins.get(plugin):
                LOGGER.info(f"Adding default bidsmap options from the {plugin} plugin")
                self.plugins[plugin] = module.OPTIONS if hasattr(module, 'OPTIONS') else {}
            if hasattr(module, 'BIDSMAP') and yamlfile.parent == templatefolder:
                for dataformat, datasection in module.BIDSMAP.items():
                    if dataformat not in bidsmap_data:
                        LOGGER.info(f"Adding default bidsmappings from the {plugin} plugin")
                        bidsmap_data[dataformat] = datasection

        # Add missing provenance info, run dictionaries and bids entities
        for dataformat in self.dataformats:
            for datatype in dataformat.datatypes:
                for index, runitem in enumerate(datatype.runitems):

                    # Add missing provenance info
                    if not runitem.provenance:
                        runitem.provenance = str(Path(f"{subprefix.replace('*', '')}unknown/{sesprefix.replace('*', '')}unknown/{dataformat}_{datatype}_id{index + 1:03}"))

                    # Update the provenance store paths if needed (e.g. when the bids-folder was moved)
                    provenance = Path(runitem.provenance)
                    if not provenance.is_file():
                        for n, part in enumerate(provenance.parts):
                            if part == 'bidscoin' and provenance.parts[n + 1] == 'provenance':           # = old bidscoin folder, i.e. bidsfolder/code/bidscoin[/provenance]
                                store = folder/provenance.relative_to(Path(*provenance.parts[0:n + 1]))  # = new bidscoin folder, i.e. folder/provenance (relative to old bidscoin folder)
                                if store.is_file():
                                    LOGGER.bcdebug(f"Updating provenance: {provenance} -> {store}")
                                    runitem.provenance = str(store)

                    # Add missing bids entities
                    suffix = runitem.bids.get('suffix')
                    if runitem.datasource.has_support():
                        suffix = runitem.datasource.dynamicvalue(suffix, True, True)
                    for typegroup in filerules.get(datatype.datatype, {}):                  # E.g. typegroup = 'nonparametric'
                        if suffix in filerules[datatype.datatype][typegroup].suffixes:      # run_found = True
                            for entity in filerules[datatype.datatype][typegroup].entities:
                                entitykey = entities[entity].name
                                if entitykey not in runitem.bids and entitykey not in ('sub', 'ses'):
                                    LOGGER.info(f"Adding missing {dataformat}>{datatype}>{suffix} bidsmap entity key: {entitykey}")
                                    runitem.bids[entitykey] = ''
                                if entitykey == 'part' and not isinstance(runitem.bids['part'], list) and runitem.bids['part'] in ('', 'mag', 'phase', 'real', 'imag', None):
                                    runitem.bids['part'] = ['', 'mag', 'phase', 'real', 'imag', ('', 'mag', 'phase', 'real', 'imag').index(runitem.bids['part'] or '')]

        # Validate the bidsmap entries
        self.check(checks)

    def __str__(self):

        return f"{self.filepath}"

    def __repr__(self):

        dataformats = '\n'.join([f"{repr(dformat)}" for dformat in self.dataformats])
        return (f"{self.__class__}\n"
                f"Filepath:\t{self.filepath}\n"
                f"Plugins:\t{[plugin for plugin in self.plugins]}\n"
                f"Dataformats:\n{dataformats}")

    def __iter__(self):

        return iter(self.dataformats)

    @property
    def options(self) -> Options:
        """The dictionary with the BIDScoin options"""

        return self._data['Options']['bidscoin']

    @options.setter
    def options(self, options: dict):
        self._data['Options']['bidscoin'] = options

    @property
    def plugins(self) -> Plugins:
        """The plugin dictionaries with their options"""

        return self._data['Options']['plugins']

    @plugins.setter
    def plugins(self, plugins: Plugins):
        if 'Options' not in self._data:
            self._data['Options'] = {}
        self._data['Options']['plugins'] = plugins

    @property
    def dataformats(self):
        """Gets a list of the DataFormat objects in the bidsmap (e.g. DICOM)"""

        return [DataFormat(dataformat, self._data[dataformat], self.options, self.plugins) for dataformat in self._data if dataformat not in ('$schema', 'Options')]

    def dataformat(self, dataformat: str) -> DataFormat:
        """Gets the DataFormat object from the bidsmap"""

        return DataFormat(dataformat, self._data[dataformat], self.options, self.plugins)

    def add_dataformat(self, dataformat: Union[str, DataFormat]):
        """Adds a DataFormat to the bidsmap"""

        _data      = dataformat._data if isinstance(dataformat, DataFormat) else {}
        dataformat = str(dataformat)
        if dataformat not in self._data:
            LOGGER.bcdebug(f"Adding the '{dataformat}' dataformat to {self}")
            self._data[dataformat] = _data
        else:
            LOGGER.bcdebug(f"The {self} bidsmap already contains the '{dataformat}' dataformat")

    def remove_dataformat(self, dataformat: str):
        """Removes a DataFormat from the bidsmap"""

        dataformat = str(dataformat)
        if dataformat not in self._data:
            LOGGER.bcdebug(f"The '{dataformat}' dataformat could not be removed from {self}")
            return
        else:
            self._data.pop(dataformat, None)
            LOGGER.bcdebug(f"The '{dataformat}' dataformat was removed from {self}")

    def save(self, filename: Path=None):
        """
        Save the BIDSmap as a YAML text file

        :param filename: Full pathname of the bidsmap file (otherwise the existing filename will be used)
        """

        # Validate the bidsmap entries
        self.check((False, True, True))

        filename = filename or self.filepath
        filename.parent.mkdir(parents=True, exist_ok=True)
        LOGGER.info(f"Saving bidsmap in: {filename}")
        with filename.open('w') as stream:
            yaml.dump(self._data, stream, NoAliasDumper, sort_keys=False, allow_unicode=True)

    def validate(self, level: int=1) -> bool:
        """
        Test the bidsname of runs in the bidsmap using the bids-validator

        :param level:  (-2) as 2 but no logging reports,
                       (-1) as 1 but no logging reports,
                        (0) as 1 but only report invalid runs,
                        (1) test only BIDS datatypes, i.e. datatypes not in `.bidsignore` or `ignoretypes`,
                        (2) test all converted datatypes, i.e. datatypes not in `ignoretypes`,
                        (3) test all datatypes
        :return:        True if all tested runs in bidsmap were bids-valid, otherwise False
        """

        valid       = True
        ignoretypes = self.options.get('ignoretypes', [])
        bidsignore  = self.options.get('bidsignore', [])

        # Test all the runs in the bidsmap
        LOGGER.info(f"bids-validator {bids_validator.__version__} test results (* = in .bidsignore):")
        for dataformat in self.dataformats:
            for datatype in dataformat.datatypes:
                for runitem in datatype.runitems:
                    bidsname = runitem.bidsname(f"sub-{sanitize(dataformat)}", '', False)
                    ignore   = check_ignore(datatype, bidsignore) or check_ignore(bidsname+'.json', bidsignore, 'file')
                    ignore_1 = datatype in ignoretypes or ignore
                    ignore_2 = datatype in ignoretypes
                    for ext in extensions + ['.tsv' if runitem.bids['suffix']=='events' else '.dum']:      # NB: `ext` used to be '.json', which is more generic (but see https://github.com/bids-standard/bids-validator/issues/2113)
                        if bidstest := bids_validator.BIDSValidator().is_bids(f"/sub-{sanitize(dataformat)}/{datatype}/{bidsname}{ext}"): break
                    if level==3 or (abs(level)==2 and not ignore_2) or (-2<level<2 and not ignore_1):
                        valid = valid and bidstest
                    if (level==0 and not bidstest) or (level==1 and not ignore_1) or (level==2 and not ignore_2) or level==3:
                        LOGGER.info(f"{bidstest}{'*' if ignore else ''}:\t{datatype}/{bidsname}.*")

        if valid:
            LOGGER.success('All generated bidsnames are BIDS-valid')
        else:
            LOGGER.warning('Not all generated bidsnames are BIDS-valid (make sure they are BIDS-ignored')

        return valid

    def check(self, checks: tuple[bool, bool, bool]=(True, True, True)) -> tuple[Union[bool, None], Union[bool, None], Union[bool, None]]:
        """
        Check all non-ignored runs in the bidsmap for required and optional entities using the BIDS schema files

        :param checks:  Booleans to check if all (bids-keys, bids-suffixes, bids-values) in the run are present according to the BIDS schema specifications
        :return:        False if the keys, suffixes or values are proven to be invalid, otherwise None or True
        """

        results = (None, None, None)

        if not any(checks):
            return results

        # Check all the runs in the bidsmap
        LOGGER.info('Checking the bidsmap run-items:')
        for dataformat in self.dataformats:
            for datatype in dataformat.datatypes:
                if datatype in self.options['ignoretypes']:            continue     # E.g. 'exclude'
                if check_ignore(datatype, self.options['bidsignore']): continue
                if datatype.runitems and results == (None, None, None):
                    results = (True, True, True)                                    # We can now check the bidsmap
                for runitem in datatype.runitems:
                    bidsname = runitem.bidsname(validkeys=False)
                    if check_ignore(bidsname+'.json', self.options['bidsignore'], 'file'): continue
                    isvalid = runitem.check(checks)
                    results = [result and valid for result, valid in zip(results, isvalid)]

        if all([result is True for result, check in zip(results, checks) if check is True]):
            LOGGER.success('All run-items in the bidsmap are valid')
        elif any([result is False for result, check in zip(results, checks) if check is True]):
            LOGGER.warning('Not all run-items in the bidsmap are valid')
        else:
            LOGGER.verbose('Could not validate every run-item in the bidsmap')

        return results

    def check_template(self) -> bool:
        """
        Check all the datatypes in the template bidsmap for required and optional entities using the BIDS schema files

        :return:            True if the template bidsmap is valid, otherwise False
        """

        valid       = True
        ignoretypes = self.options.get('ignoretypes', [])
        bidsignore  = self.options.get('bidsignore', [])

        # Check all the datatypes in the bidsmap
        LOGGER.verbose('Checking the template bidsmap datatypes:')
        for dataformat in self.dataformats:
            for datatype in dataformat.datatypes:
                if not (datatype.datatype in bidsschema.objects.datatypes or datatype in ignoretypes or check_ignore(datatype, bidsignore)):
                    LOGGER.warning(f"Invalid {dataformat} datatype: '{datatype}' (you may want to add it to the 'bidsignore' list)")
                    valid = False
                if datatype in ignoretypes: continue
                datatypesuffixes = set()
                for runitem in datatype.runitems:
                    datatypesuffixes.add(runitem.bids['suffix'])
                    for key, val in runitem.attributes.items():
                        try:
                            re.compile(str(val))
                        except re.error:
                            LOGGER.warning(f"Invalid regex pattern in the {key} value '{val}' in: {runitem}\nThis may cause run-matching errors unless '{val}' is a literal attribute value")
                for typegroup in filerules.get(datatype.datatype, {}):
                    for suffix in filerules[datatype.datatype][typegroup].suffixes:
                        if not (suffix in datatypesuffixes or suffix in str(bidsignore) or
                                '[DEPRECATED]'             in bidsschema.objects.suffixes[suffix].description or
                                '**Change:** Removed from' in bidsschema.objects.suffixes[suffix].description or
                                '**Change:** Replaced by'  in bidsschema.objects.suffixes[suffix].description):
                            LOGGER.info(f"Missing '{suffix}' run-item in: bidsmap[{dataformat}][{datatype}] (NB: this may perhaps be fine / a deprecated item)")
                            # valid = False # TODO: Fix this for sparse events2bids mappings

        # Validate against the json schema
        with (templatefolder/'schema.json').open('r') as stream:
            schema = json.load(stream)
        try:
            jsonschema.validate(self._data, schema)
        except jsonschema.ValidationError as bidsmaperror:
            LOGGER.warning(f"Invalid template bidsmap:\n{bidsmaperror}")
            valid = False

        if valid:
            LOGGER.success('All datatypes and options in the template bidsmap are valid')
        else:
            LOGGER.warning('Not all datatypes and options in the template bidsmap are valid')

        return valid

    def dir(self, dataformat: Union[str, DataFormat]) -> list[Path]:
        """
        Make a provenance list of all the runs in the bidsmap[dataformat]

        :param dataformat:  The dataformat section in the bidsmap that is listed, e.g. 'DICOM'
        :return:            List of all provenances
        """

        provenance = []
        for datatype in self.dataformat(str(dataformat)).datatypes:
            for runitem in datatype.runitems:
                if not runitem.provenance:
                    LOGGER.warning(f'The bidsmap {datatype} run does not contain provenance data')
                else:
                    provenance.append(Path(runitem.provenance))

        provenance.sort()

        return provenance

    def exist_run(self, runitem: RunItem, datatype: Union[str, DataType]='') -> bool:
        """
        Checks the bidsmap to see if there is already an entry in runlist with the same properties and attributes as in the input run

        :param runitem:     The run-item that is searched for in the bidsmap
        :param datatype:    The datatype that is searched in, e.g. 'anat'. Empty values will search through all datatypes
        :return:            True if the run exists in runlist, otherwise False
        """

        datatype = str(datatype)

        # Search recursively
        if not datatype:
            for dtype in self.dataformat(runitem.dataformat).datatypes:
                if self.exist_run(runitem, dtype):
                    return True

        if datatype not in self.dataformat(runitem.dataformat).datatypes:
            return False

        for _runitem in self.dataformat(runitem.dataformat).datatype(datatype).runitems:

            # Begin with match = True unless all run properties and attributes are empty
            match = any([getattr(_runitem, attr)[key] not in (None,'') for attr in ('properties','attributes') for key in getattr(_runitem, attr)])

            # TODO: Test if the run has more attributes than the runitem

            # Test if all properties and attributes of the runitem match with the run
            for attr in ('properties', 'attributes'):
                for itemkey, itemvalue in getattr(runitem, attr).items():
                    value = getattr(_runitem, attr).get(itemkey)     # Matching labels which exist in one datatype but not in the other -> None
                    match = match and match_runvalue(itemvalue, value)
                    if not match:
                        break                                       # There is no point in searching further within the run now that we've found a mismatch

            # Stop searching if we found a matching runitem (i.e. which is the case if match is still True after all run tests)
            if match:
                return True

        return False

    def get_matching_run(self, sourcefile: Union[str, Path], dataformat: str='', runtime: bool=False) -> tuple[RunItem, str]:
        """
        Find the first run in the bidsmap with properties and attributes that match with the data source. Only non-empty
        properties and attributes are matched, except when runtime is True, then the empty attributes are also matched.
        The datatypes are searched for in this order:

        ignoredatatypes (e.g. 'exclude') -> normal datatypes (e.g. 'anat') -> unknowndatatypes (e.g. 'extra_data')

        :param sourcefile:  The full filepath of the data source for which to get a run-item
        :param dataformat:  The dataformat section in the bidsmap in which a matching run is searched for, e.g. 'DICOM'. Leave empty to recursively search through all dataformats
        :param runtime:     Dynamic <<values>> are expanded if True
        :return:            (run, provenance) A vanilla run that has all its attributes populated with the source file attributes.
                            If there is a match, the provenance of the bidsmap entry is returned, otherwise it will be ''
        """

        # Iterate over all dataformats if dataformat is not given
        if not dataformat:
            runitem, provenance = RunItem(), ''
            for dformat in self.dataformats:
                runitem, provenance = self.get_matching_run(sourcefile, dformat.dataformat, runtime)
                if provenance: break
            return runitem, provenance

        # Defaults
        datasource       = DataSource(sourcefile, self.plugins, dataformat, options=self.options)
        unknowndatatypes = self.options.get('unknowntypes') or ['unknown_data']
        ignoredatatypes  = self.options.get('ignoretypes') or []
        normaldatatypes  = [dtype.datatype for dtype in self.dataformat(dataformat).datatypes if dtype not in unknowndatatypes + ignoredatatypes]
        rundata          = {'provenance': str(sourcefile), 'properties': {}, 'attributes': {}, 'bids': {}, 'meta': {}, 'events': {}}
        """The a run-item data structure. NB: Keep in sync with the RunItem() data attributes"""

        # Iterate over all datatypes and runs; all info goes cleanly into runitem (to avoid formatting problem of the CommentedMap)
        if 'fmap' in normaldatatypes:
            normaldatatypes.insert(0, normaldatatypes.pop(normaldatatypes.index('fmap')))   # Put fmap at the front (to catch inverted polarity scans first
        for datatype in ignoredatatypes + normaldatatypes + unknowndatatypes:                      # The ordered datatypes in which a matching run is searched for
            if datatype not in self.dataformat(dataformat).datatypes: continue
            for runitem in self.dataformat(dataformat).datatype(datatype).runitems:

                # Begin with match = True unless all properties and attributes are empty
                match = any([getattr(runitem, attr)[key] not in (None,'') for attr in ('properties','attributes') for key in getattr(runitem, attr)])

                # Initialize a clean run-item data structure
                rundata = {'provenance': str(sourcefile), 'properties': {}, 'attributes': {}, 'bids': {}, 'meta': {}, 'events': {}}

                # Test if the data source matches all the non-empty run-item properties, but do NOT populate them
                for propkey, propvalue in runitem.properties.items():

                    # Check if the property value matches with the info from the sourcefile
                    if propvalue:
                        sourcevalue = datasource.properties(propkey)
                        match       = match and match_runvalue(sourcevalue, propvalue)

                    # Keep the matching expression
                    rundata['properties'][propkey] = propvalue

                # Test if the data source matches all the run-item attributes and populate all of them
                for attrkey, attrvalue in runitem.attributes.items():

                    # Check if the attribute value matches with the info from the sourcefile
                    sourcevalue = datasource.attributes(attrkey, validregexp=True)
                    if attrvalue or runtime:
                        match = match and match_runvalue(sourcevalue, attrvalue)

                    # Populate the empty attribute with the info from the sourcefile
                    rundata['attributes'][attrkey] = sourcevalue

                # Try to fill the bids-labels
                for bidskey, bidsvalue in runitem.bids.items():

                    # Replace the dynamic bids values, except the dynamic run-index (e.g. <<>>)
                    if bidskey == 'run' and bidsvalue and (bidsvalue.replace('<','').replace('>','').isdecimal() or bidsvalue == '<<>>'):
                        rundata['bids'][bidskey] = bidsvalue
                    else:
                        rundata['bids'][bidskey] = datasource.dynamicvalue(bidsvalue, runtime=runtime)

                # Try to fill the metadata
                for metakey, metavalue in runitem.meta.items():

                    # Replace the dynamic meta values, except the IntendedFor value (e.g. <<task>>)
                    if metakey == 'IntendedFor':
                        rundata['meta'][metakey] = metavalue
                    elif metakey in ('B0FieldSource', 'B0FieldIdentifier') and fnmatch(str(metavalue), '*<<session*>>*'):
                        rundata['meta'][metakey] = metavalue
                    else:
                        rundata['meta'][metakey] = datasource.dynamicvalue(metavalue, cleanup=False, runtime=runtime)

                # Copy the events-data
                for eventskey, eventsvalue in runitem.events.items():

                    # Replace the dynamic bids values, except the dynamic run-index (e.g. <<>>)
                    rundata['events'][eventskey] = copy.deepcopy(eventsvalue)

                # Stop searching the bidsmap if we have a match
                if match:
                    LOGGER.bcdebug(f"Found bidsmap match: {runitem}")
                    runitem = RunItem(dataformat, datatype, copy.deepcopy(rundata), self.options, self.plugins)

                    # SeriesDescriptions (and ProtocolName?) may get a suffix like '_SBRef' from the vendor, try to strip it off
                    runitem.strip_suffix()

                    return runitem, runitem.provenance

        # We don't have a match (all tests failed, so datatype should be the *last* one, e.g. unknowndatatype)
        LOGGER.bcdebug(f"Found no bidsmap match for: {sourcefile}")
        if datatype not in unknowndatatypes:
            LOGGER.warning(f"Data type was expected to be in {unknowndatatypes}, instead it is '{datatype}' -> {sourcefile}")

        runitem = RunItem(dataformat, datatype, copy.deepcopy(rundata), self.options, self.plugins)
        runitem.strip_suffix()
        return runitem, ''

    def get_run(self, datatype: Union[str, DataType], suffix_idx: Union[int, str], datasource: DataSource) -> RunItem:
        """
        Find the (first) run in bidsmap[dataformat][bidsdatatype] with run.bids['suffix_idx'] == suffix_idx

        :param datatype:    The datatype in which a matching run is searched for (e.g. 'anat')
        :param suffix_idx:  The name of the suffix that is searched for (e.g. 'bold') or the datatype index number
        :param datasource:  The datasource with the provenance file from which the properties, attributes and dynamic values are read
        :return:            A populated run-item that is deepcopied from bidsmap[dataformat][bidsdatatype] with the matching suffix_idx,
                            otherwise an empty dict
        """

        if not datasource.dataformat and not datasource.has_support():
            LOGGER.bcdebug(f"No dataformat/plugin support found when getting a run for: {datasource}")

        datatype = str(datatype)

        for index, _runitem in enumerate(self.dataformat(datasource.dataformat).datatype(datatype).runitems):
            if index == suffix_idx or _runitem.bids['suffix'] == suffix_idx:

                runitem = copy.deepcopy(_runitem)
                runitem.provenance = str(datasource.path)

                for propkey, propvalue in runitem.properties.items():
                    runitem.properties[propkey] = propvalue

                for attrkey, attrvalue in runitem.attributes.items():
                    if datasource.path.name:
                        runitem.attributes[attrkey] = datasource.attributes(attrkey, validregexp=True)
                    else:
                        runitem.attributes[attrkey] = attrvalue

                # Replace the dynamic bids values, except the dynamic run-index (e.g. <<>>)
                for bidskey, bidsvalue in runitem.bids.items():

                    if bidskey == 'run' and bidsvalue and (bidsvalue.replace('<','').replace('>','').isdecimal() or bidsvalue == '<<>>'):
                        runitem.bids[bidskey] = bidsvalue
                    else:
                        runitem.bids[bidskey] = datasource.dynamicvalue(bidsvalue)

                # Replace the dynamic meta values, except the IntendedFor value (e.g. <<task>>)
                for metakey, metavalue in runitem.meta.items():

                    if metakey == 'IntendedFor':
                        runitem.meta[metakey] = metavalue
                    elif metakey in ('B0FieldSource', 'B0FieldIdentifier') and fnmatch(str(metavalue), '*<<session*>>*'):
                        runitem.meta[metakey] = metavalue
                    else:
                        runitem.meta[metakey] = datasource.dynamicvalue(metavalue, cleanup=False)

                return runitem

        LOGGER.error(f"A '{datatype}' run with suffix_idx '{suffix_idx}' cannot be found in bidsmap['{datasource.dataformat}']")

    def find_run(self, provenance: str, dataformat: Union[str, DataFormat]='', datatype: Union[str, DataType]='') -> RunItem:
        """
        Find the (first) run in bidsmap[dataformat][bidsdatatype] with run.provenance == provenance

        :param provenance:  The unique provenance that is used to identify the run
        :param dataformat:  The dataformat section in the bidsmap in which a matching run is searched for, e.g. 'DICOM'. Otherwise, all dataformats are searched
        :param datatype:    The datatype in which a matching run is searched for (e.g. 'anat'). Otherwise, all datatypes are searched
        :return:            The unpopulated run-item that is taken as is from the bidsmap[dataformat][bidsdatatype]
        """

        dataformat = str(dataformat)
        datatype   = str(datatype)

        for dataformat in [self.dataformat(dataformat)] if dataformat else self.dataformats:
            datatypes = [dataformat.datatype(datatype)] if datatype in dataformat.datatypes else [] if datatype else dataformat.datatypes
            for dtype in datatypes:
                for runitem in dtype.runitems:
                    if Path(runitem.provenance) == Path(provenance):
                        return runitem

        LOGGER.bcdebug(f"Could not find this [{dataformat}][{datatype}] run: '{provenance}")

    def delete_run(self, provenance: Union[RunItem, str], datatype: Union[str, DataType]='', dataformat: Union[str, DataFormat]=''):
        """
        Delete the first matching run from the BIDS map using its provenance

        :param provenance:  The provenance identifier of/or the run-item that is deleted
        :param datatype:    The datatype that of the deleted runitem, e.g. 'anat'
        :param dataformat:  The dataformat section in the bidsmap in which the run is deleted, e.g. 'DICOM'. Otherwise,
                            all dataformat sections searched for
        """

        if isinstance(provenance, str):
            runitem = self.find_run(provenance, dataformat, datatype)
        else:
            runitem    = provenance
            provenance = runitem.provenance
        if not runitem.provenance:
            return

        dformat = self.dataformat(str(dataformat) or runitem.dataformat)
        dtype   = dformat.datatype(str(datatype) or runitem.datatype)
        dtype.delete_run(provenance)

    def delete_runs(self):
        """Delete all run-items from the bidsmap"""

        for dataformat in self.dataformats:
            dataformat.delete_runs()

    def insert_run(self, runitem: RunItem, position: int=None):
        """
        Inserts a run-item (as is) to the BIDS map (e.g. allowing you to insert a run-item from another bidsmap).
        Optionally, a copy of the datasource is stored in the provenance store

        :param runitem:     The (typically cleaned orphan) run item that is appended to the list of run items of its datatype
        :param position:    The position at which the run is inserted. The run is appended at the end if position is None
        """

        # Work from the provenance store if given (the store source and target are set during bidsmapper runtime)
        sourcefile = Path(runitem.provenance)
        if self.store and sourcefile.is_file():
            targetfile = self.store['target']/sourcefile.relative_to(self.store['source'])
            if not targetfile.is_file():
                targetfile.parent.mkdir(parents=True, exist_ok=True)
                LOGGER.verbose(f"Storing a copy of the discovered sample: {targetfile}")
                runitem.provenance = str(shutil.copyfile(sourcefile, targetfile))

        # Insert the run item
        self.add_dataformat(runitem.dataformat)                             # Add the dataformat if it doesn't exist
        self.dataformat(runitem.dataformat).add_datatype(runitem.datatype)  # Add the datatype if it doesn't exist
        self.dataformat(runitem.dataformat).datatype(runitem.datatype).insert_run(runitem, position)

    def update(self, source_datatype: Union[str, DataType], runitem: RunItem):
        """
        Update the BIDS map if the runitem datatype has changed:
        1. Remove the runitem from the old datatype section
        2. Append the (cleaned and deepcopied) runitem to its new datatype section

        Else:
        1. Use the provenance to look up its index number
        2. Replace the runitem

        :param source_datatype: The old datatype, e.g. 'anat'
        :param runitem:         The run item that is being moved to its new runitem.datatype
        """

        new_datatype = runitem.datatype
        num_runs_in  = len(self.dir(runitem.dataformat))

        if source_datatype != new_datatype:

            # Warn the user if the target run already exists when the run is moved to another datatype
            if self.find_run(runitem.provenance, runitem.dataformat, new_datatype):
                LOGGER.error(f'The "{source_datatype}" run already exists in {runitem}')

            # Delete the source run
            self.delete_run(runitem, source_datatype, runitem.dataformat)

            # Append the (cleaned-up) target run
            self.insert_run(runitem)

        else:

            self.dataformat(runitem.dataformat).datatype(new_datatype).replace_run(runitem)

        num_runs_out = len(self.dir(runitem.dataformat))
        if num_runs_out != num_runs_in:
            LOGGER.error(f"Number of runs in bidsmap['{runitem.dataformat}'] changed unexpectedly: {num_runs_in} -> {num_runs_out}")


def get_datasource(sourcedir: Path, plugins: Plugins, recurse: int=8) -> DataSource:
    """Gets a data source from the sourcedir inputfolder and its recursive subfolders"""

    datasource = DataSource()
    if sourcedir.is_dir():
        for sourcepath in sorted(sourcedir.iterdir()):
            if is_hidden(sourcepath.relative_to(sourcedir)):
                continue
            if sourcepath.is_dir() and recurse:
                datasource = get_datasource(sourcepath, plugins, recurse-1)
            elif sourcepath.is_file():
                datasource = DataSource(sourcepath, plugins)
            if datasource.has_support():
                return datasource

    return datasource


def check_ignore(entry, bidsignore: Union[str,list], filetype: str= 'dir') -> bool:
    """
    A rudimentary check whether `entry` should be BIDS-ignored. This function should eventually be replaced by bids_validator functionality
    See also https://github.com/bids-standard/bids-specification/issues/131

    :param entry:       The entry that is checked against the bidsignore (e.g. a directory/datatype such as `anat` or a file such as `sub-001_ct.nii.gz`)
    :param bidsignore:  The list or semicolon separated bidsignore pattern (e.g. from the bidscoin Options such as `mrs/;extra_data/;sub-*_ct.*`)
    :param filetype:    The entry filetype, i.e. 'dir' or 'file', that can be used to limit the check
    :return:            True if the entry should be ignored, else False
    """

    # Parse bidsignore to be a list (legacy bidsmaps)
    if isinstance(bidsignore, str):
        bidsignore = bidsignore.split(';')

    ignore = False
    for item in set(bidsignore + ['code/', 'sourcedata/', 'derivatives/']):
        if filetype == 'dir' and not item.endswith('/'): continue
        if filetype == 'file'    and item.endswith('/'): continue
        if item.endswith('/'):
            item = item[0:-1]
        if fnmatch(str(entry), item):
            ignore = True
            break

    return ignore


def sanitize(label: Union[str, DataFormat, DataType]):
    """
    Converts a given label to a cleaned-up label that can be used as a BIDS label. Remove leading and trailing spaces;
    convert other spaces, special BIDS characters and anything that is not an alphanumeric to a ''. This will for
    example map "Joe's reward_task" to "Joesrewardtask"

    :param label:   The label that potentially contains undesired characters
    :return:        The cleaned-up/BIDS-valid string label or the original (non-string) label
    """

    if label is None or label == '':
        return ''
    if not isinstance(label, (str, DataFormat, DataType)):
        return label
    label = str(label)

    special_characters = (' ', '_', '-','.')

    for special in special_characters:
        label = label.strip().replace(special, '')

    return re.sub(r'(?u)[^-\w.]', '', label)


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
    if str(attribute) == str(pattern) or (not attribute and not pattern):
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


def get_bidsvalue(bidsfile: Union[str, Path], bidskey: str, newvalue: str='') -> Union[Path, str]:
    """
    Sets the bidslabel, i.e. '*_bidskey-*_' is replaced with '*_bidskey-bidsvalue_'. If the key exists but is not in the
    bidsname (e.g. 'fallback') then, as a fallback, the newvalue is appended to the acquisition label. If newvalue is empty
    (= default), then the parsed existing bidsvalue is returned and nothing is set

    :param bidsfile:    The bidsname (e.g. as returned from RunItem.bidsname() or fullpath)
    :param bidskey:     The name of the bidskey, e.g. 'echo' or 'suffix'
    :param newvalue:    The new bidsvalue. NB: remove non-BIDS compliant characters beforehand (e.g. using sanitize)
    :return:            The bidsname with the new bidsvalue or, if newvalue is empty, the existing bidsvalue
    """

    # Check input
    if not bidsfile or (not bidskey and newvalue):
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

    :param bidsfile:    The bidsname (e.g. as returned from RunItem.bidsname() or fullpath)
    :param bidskey:     The name of the new bidskey, e.g. 'echo' or 'suffix'
    :param newvalue:    The value of the new bidskey
    :param validkeys:   Removes non-BIDS-compliant bids-keys if True
    :return:            The bidsname with the new bids key-value pair
    """

    bidspath = Path(bidsfile).parent
    bidsname = Path(bidsfile).with_suffix('').stem
    bidsext  = ''.join(Path(bidsfile).suffixes)

    # Parse the key-value pairs and store all the run info
    runitem = RunItem()
    subid   = ''
    sesid   = ''
    for keyval in bidsname.split('_'):
        if '-' in keyval:
            key, val = keyval.split('-', 1)
            if key == 'sub':
                subid = keyval
            elif key == 'ses':
                sesid = keyval
            else:
                runitem.bids[key] = val
        else:
            runitem.bids['suffix'] = f"{runitem.bids.get('suffix','')}_{keyval}"     # account for multiple suffixes (e.g. _bold_e1_ph from dcm2niix)
    if runitem.bids.get('suffix','').startswith('_'):
        runitem.bids['suffix'] = runitem.bids['suffix'][1:]

    # Insert the key-value pair in the run
    if bidskey == 'sub':
        subid = newvalue
    elif bidskey == 'ses':
        sesid = newvalue
    else:
        runitem.bids[bidskey] = newvalue

    # Compose the new filename
    newbidsfile = (bidspath/runitem.bidsname(subid, sesid, validkeys, cleanup=False)).with_suffix(bidsext)

    if isinstance(bidsfile, str):
        newbidsfile = str(newbidsfile)
    return newbidsfile


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
                        if (acq_time - acq_prev).total_seconds() < 0:
                            LOGGER.warning(f"Acquisition times do not increase with the run-indices. Please check `{scans_tsv}`")
                            return False

    return True


def limitmatches(fmap: str, matches: list[str], limits: str, niifiles: set[str], scans_table: pd.DataFrame):
    """
    Helper function for addmetadata() to check if there are multiple field map runs and get the lower- and upperbound from
    the AcquisitionTime to bound the grand list of matches to adjacent runs. The resulting list is appended to niifiles

    :param fmap:        The field map (relative to the session folder)
    :param matches:     The images (relative to the session folder) associated with the field map
    :param limits:      The bounding limits from the dynamic value: '[lowerlimit:upperlimit]'
    :param niifiles:    The list to which the bounded results are appended
    :param scans_table: The scans table with the acquisition times
    :return:
    """

    # Check the input
    if limits == '[]':
        limits = '[:]'

    # Set fallback upper and lower bounds if parsing the scans-table is not possible
    fmaptime   = dateutil.parser.parse('1925-01-01')    # Use the BIDS stub acquisition time
    lowerbound = fmaptime.replace(year=1900)            # Use an ultra-wide lower limit for the search
    upperbound = fmaptime.replace(year=2100)            # Idem for the upper limit

    # There may be more field maps, hence try to limit down the matches to the adjacent acquisitions
    try:
        fmaptime = dateutil.parser.parse(scans_table.loc[fmap, 'acq_time'])
        runindex = get_bidsvalue(fmap, 'run')
        prevfmap = get_bidsvalue(fmap, 'run', str(int(runindex) - 1))
        nextfmap = get_bidsvalue(fmap, 'run', str(int(runindex) + 1))
        if prevfmap in scans_table.index:
            lowerbound = dateutil.parser.parse(scans_table.loc[prevfmap, 'acq_time'])  # Narrow the lower search limit down to the preceding field map
        if nextfmap in scans_table.index:
            upperbound = dateutil.parser.parse(scans_table.loc[nextfmap, 'acq_time'])  # Narrow the upper search limit down to the succeeding field map
    except (TypeError, ValueError, KeyError, dateutil.parser.ParserError) as acqtimeerror:
        pass  # Raise this only if there are limits and matches, i.e. below

    # Limit down the matches if the user added a range specifier/limits
    if limits and matches:
        try:
            limits     = limits[1:-1].split(':', 1)     # limits: '[lowerlimit:upperlimit]' -> ['lowerlimit', 'upperlimit']
            lowerlimit = int(limits[0]) if limits[0].strip() else float('-inf')
            upperlimit = int(limits[1]) if limits[1].strip() else float('inf')
            acqtimes   = []
            for match in set(matches):
                acqtimes.append((dateutil.parser.parse(scans_table.loc[match, 'acq_time']), match))  # Time + filepath relative to the session-folder
            acqtimes.sort(key=lambda acqtime: acqtime[0])
            offset = sum([acqtime[0] < fmaptime for acqtime in acqtimes])  # The nr of preceding runs
            for nr, acqtime in enumerate(acqtimes):
                if (lowerbound < acqtime[0] < upperbound) and (lowerlimit <= nr-offset <= upperlimit):
                    niifiles.add(acqtime[1])
        except Exception as matcherror:
            LOGGER.error(f"Could not bound the field maps using <*:{limits}> as it requires a *_scans.tsv file with acq_time values for: {fmap}\n{matcherror}")
            niifiles.update(matches)
    else:
        niifiles.update(matches)


def addmetadata(bidsses: Path):
    """
    Adds the special field map metadata (IntendedFor, TE, etc.)

    :param bidsses: The session folder with the BIDS session data
    """

    subid = bidsses.name if bidsses.name.startswith('sub-') else bidsses.parent.name
    sesid = bidsses.name if bidsses.name.startswith('ses-') else ''

    # Add IntendedFor search results and TE1+TE2 metadata to the field map json-files. This has been postponed until all datatypes have been processed (i.e. so that all target images are indeed on disk)
    if (bidsses/'fmap').is_dir():

        scans_tsv = bidsses/f"{subid}{'_'+sesid if sesid else ''}_scans.tsv"
        if scans_tsv.is_file():
            scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
        else:
            scans_table = pd.DataFrame(columns=['acq_time'])

        for fmap in [fmap.relative_to(bidsses).as_posix() for fmap in sorted((bidsses/'fmap').glob('sub-*.nii*'))]:

            # Load the existing metadata
            jsondata = {}
            jsonfile = (bidsses/fmap).with_suffix('').with_suffix('.json')
            if jsonfile.is_file():
                with jsonfile.open('r') as sidecar:
                    jsondata = json.load(sidecar)

            # Populate the dynamic IntendedFor values
            intendedfor = jsondata.get('IntendedFor')
            if intendedfor and isinstance(intendedfor, str) and not intendedfor.startswith('bids:'):

                # Search with multiple patterns for matching NIfTI-files in all runs and store the relative paths to the session folder
                niifiles = set()
                if intendedfor.startswith('<') and intendedfor.endswith('>'):
                    intendedfor = intendedfor[2:-2].split('><')
                elif not isinstance(intendedfor, list):
                    intendedfor = [intendedfor]
                for part in intendedfor:
                    pattern = part.split(':',1)[0].strip()          # part = 'pattern: [lowerlimit:upperlimit]'
                    limits  = part.split(':',1)[1].strip() if ':' in part else ''
                    matches = [niifile.relative_to(bidsses).as_posix() for niifile in sorted(bidsses.rglob(f"*{pattern}*")) if pattern and '.nii' in niifile.suffixes]
                    limitmatches(fmap, matches, limits, niifiles, scans_table)

                # Add the IntendedFor data. NB: The BIDS URI paths need to use forward slashes and be relative to the bids root folder
                if niifiles:
                    LOGGER.verbose(f"Adding IntendedFor to: {jsonfile}")
                    jsondata['IntendedFor'] = [f"bids::{(Path(subid)/sesid/niifile).as_posix()}" for niifile in niifiles]
                else:
                    LOGGER.warning(f"Empty 'IntendedFor' field map value in {jsonfile}: the search for {intendedfor} gave no results")
                    jsondata['IntendedFor'] = None

            elif not (intendedfor or jsondata.get('B0FieldSource') or jsondata.get('B0FieldIdentifier')):
                LOGGER.warning(f"Empty IntendedFor/B0FieldSource/B0FieldIdentifier field map values in {jsonfile} (i.e. the field map may not be used)")

            # Work-around because the bids-validator (v1.8) cannot handle `null` values / unused IntendedFor fields
            if not jsondata.get('IntendedFor'):
                jsondata.pop('IntendedFor', None)

            # Populate the dynamic B0FieldIdentifier/Source values with a run-index string if they contain a range specifier
            b0fieldtag = jsondata.get('B0FieldIdentifier')              # TODO: Refactor the code below to deal with B0FieldIdentifier lists (anywhere) instead of assuming it's a string (inside the fmap folder)
            if isinstance(b0fieldtag, str) and fnmatch(b0fieldtag, '*<<*:[[]*[]]>>*'):  # b0fieldtag = 'tag<<session:[lowerlimit:upperlimit]>>tag'

                # Search in all runs for the b0fieldtag and store the relative paths to the session folder
                niifiles = set()
                matches  = []
                dynamic  = b0fieldtag.split('<<')[1].split('>>')[0]         # dynamic = 'session:[lowerlimit:upperlimit]'
                limits   = dynamic.split(':',1)[1].strip()                  # limits = '[lowerlimit:upperlimit]'
                for match in bidsses.rglob(f"sub-*.nii*"):
                    if match.with_suffix('').with_suffix('.json').is_file():
                        with match.with_suffix('').with_suffix('.json').open('r') as sidecar:
                            metadata = json.load(sidecar)
                        for b0fieldkey in ('B0FieldSource', 'B0FieldIdentifier'):
                            b0fieldtags = metadata.get(b0fieldkey)
                            if b0fieldtag == b0fieldtags or (isinstance(b0fieldtags, list) and b0fieldtag in b0fieldtags):
                                matches.append(match.relative_to(bidsses).as_posix())
                limitmatches(fmap, matches, limits, niifiles, scans_table)

                # In the b0fieldtags, replace the limits with field map runindex
                runindex      = get_bidsvalue(fmap, 'run')
                newb0fieldtag = b0fieldtag.replace(':'+limits, '_'+runindex if runindex else '')
                for niifile in niifiles:
                    metafile = (bidsses/niifile).with_suffix('').with_suffix('.json')
                    LOGGER.bcdebug(f"Updating the b0fieldtag ({b0fieldtag} -> {newb0fieldtag}) for: {metafile}")
                    if niifile == fmap:
                        metadata = jsondata
                    elif metafile.is_file():
                        with metafile.open('r') as sidecar:
                            metadata = json.load(sidecar)
                    else:
                        continue
                    for b0fieldkey in ('B0FieldSource', 'B0FieldIdentifier'):
                        b0fieldtags = metadata.get(b0fieldkey)
                        if b0fieldtag == b0fieldtags:
                            metadata[b0fieldkey] = newb0fieldtag
                        elif isinstance(b0fieldtags, list) and b0fieldtag in b0fieldtags:
                            metadata[b0fieldkey][b0fieldtags.index(b0fieldtag)] = newb0fieldtag
                    if niifile != fmap:
                        with metafile.open('w') as sidecar:
                            json.dump(metadata, sidecar, indent=4)

            # Extract the echo times from magnitude1 and magnitude2 and add them to the phasediff json-file
            if jsonfile.name.endswith('phasediff.json') and None in (jsondata.get('EchoTime1'), jsondata.get('EchoTime2')):
                json_magnitude = [None, None]
                echotime       = [None, None]
                for n in (0,1):
                    json_magnitude[n] = jsonfile.parent/jsonfile.name.replace('_phasediff', f"_magnitude{n+1}")
                    if not json_magnitude[n].is_file():
                        LOGGER.error(f"Could not find expected magnitude{n+1} image associated with: {jsonfile}\nUse the bidseditor to verify that the fmap images that belong together have corresponding BIDS output names")
                    else:
                        with json_magnitude[n].open('r') as sidecar:
                            data = json.load(sidecar)
                        echotime[n] = data.get('EchoTime')
                jsondata['EchoTime1'] = jsondata.get('EchoTime1') or echotime[0]
                jsondata['EchoTime2'] = jsondata.get('EchoTime2') or echotime[1]
                if None in (jsondata['EchoTime1'], jsondata['EchoTime2']):
                    LOGGER.error(f"Cannot find and add valid EchoTime1={jsondata['EchoTime1']} and EchoTime2={jsondata['EchoTime2']} data to: {jsonfile}")
                elif jsondata['EchoTime1'] > jsondata['EchoTime2']:
                    LOGGER.error(f"Found invalid EchoTime1={jsondata['EchoTime1']} > EchoTime2={jsondata['EchoTime2']} for: {jsonfile}")
                else:
                    LOGGER.verbose(f"Adding EchoTime1: {jsondata['EchoTime1']} and EchoTime2: {jsondata['EchoTime2']} to {jsonfile}")

            # Save the collected metadata to disk
            if jsondata:
                with jsonfile.open('w') as sidecar:
                    json.dump(jsondata, sidecar, indent=4)


def poolmetadata(datasource: DataSource, targetmeta: Path, usermeta: Meta, metaext: Iterable, sourcemeta: Path=Path()) -> Meta:
    """
    Load the metadata from the target (json sidecar), then add metadata from the source (json sidecar) and finally add
    the user metadata (meta table). Source metadata other than json sidecars are copied over to the target folder. Special
    dynamic <<session>> values are replaced with the session label, and unused B0-field tags are removed

    NB: In future versions this function could also support more source metadata formats, e.g. yaml, csv- or Excel-files

    :param datasource:  The data source from which dynamic values are read
    :param targetmeta:  The filepath of the target data file with metadata
    :param usermeta:    A user metadata dict, e.g. the meta table from a run-item
    :param metaext:     A list of file extensions of the source metadata files, e.g. as specified in bidsmap.plugins['plugin']['meta']
    :param sourcemeta:  The filepath of the source data file with associated/equally named metadata files (name may include wildcards). Leave empty to use datasource.path
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
    for ext in metaext:
        for sourcefile in sourcemeta.parent.glob(sourcemeta.with_suffix('').with_suffix(ext).name):
            LOGGER.verbose(f"Copying source data from: '{sourcefile}''")

            # Put the metadata in metadict
            if ext == '.json':
                with sourcefile.open('r') as json_fid:
                    metadata = json.load(json_fid)
                if not isinstance(metadata, dict):
                    LOGGER.error(f"Skipping unexpectedly formatted metadata in: {sourcefile}")
                    continue
                for metakey, metaval in metadata.items():
                    if metapool.get(metakey) and metapool.get(metakey) != metaval:
                        LOGGER.info(f"Overruling {metakey} sourcefile values in {targetmeta}: {metapool[metakey]} -> {metaval}")
                    else:
                        LOGGER.bcdebug(f"Adding '{metakey}: {metaval}' to: {targetmeta}")
                    metapool[metakey] = metaval or None

            # Or just copy over the metadata file
            else:
                targetfile = targetmeta.parent/sourcefile.name
                if not targetfile.is_file():
                    shutil.copyfile(sourcefile, targetfile)

    # Add all the metadata to the metadict. NB: the dynamic `IntendedFor` value is handled separately later
    for metakey, metaval in usermeta.items():
        if metakey != 'IntendedFor' and not (metakey in ('B0FieldSource', 'B0FieldIdentifier') and fnmatch(str(metaval), '*<<session*>>*')):
            metaval = datasource.dynamicvalue(metaval, cleanup=False, runtime=True)
            try:
                metaval = ast.literal_eval(str(metaval))  # E.g. convert stringified list or int back to list or int
            except (ValueError, SyntaxError):
                pass
        if metapool.get(metakey) and metapool.get(metakey) != metaval:
            LOGGER.info(f"Overruling {metakey} bidsmap values in {targetmeta}: {metapool[metakey]} -> {metaval}")
        else:
            LOGGER.bcdebug(f"Adding '{metakey}: {metaval}' to: {targetmeta}")
        metapool[metakey] = metaval or None

    # Update <<session>> in B0FieldIdentifiers/Sources. NB: Leave range specifiers (<<session:[-2:2]>>) untouched (-> bidscoiner)
    for key in ('B0FieldSource', 'B0FieldIdentifier'):

        # Replace <<session>> with the actual session label
        if fnmatch(str(metapool.get(key)), '*<<session*>>*'):
            ses = get_bidsvalue(targetmeta, 'ses')
            if isinstance(metapool[key], str):
                metapool[key] = metapool[key].replace('<<session', f"<<ses{ses}")
            elif isinstance(metapool[key], list):
                metapool[key] = [item.replace('<<session', f"<<ses{ses}") for item in metapool[key]]

        # Remove unused (but added from the template) B0FieldIdentifiers/Sources
        if not metapool.get(key):
            metapool.pop(key, None)

    return Meta(metapool)


def addparticipant(participants_tsv: Path, subid: str='', sesid: str='', data: dict=None, dryrun: bool=False) -> pd.DataFrame:
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
        table = pd.read_csv(participants_tsv, sep='\t', dtype=str, index_col='participant_id')
    else:
        table = pd.DataFrame()
        table.index.name = 'participant_id'

    # Add the participant row
    data_added = False
    if subid:
        if subid not in table.index:
            if sesid:
                table.loc[subid, 'session_id'] = sesid
            data_added                = True
        for key in data:
            if key not in table or pd.isnull(table.loc[subid, key]) or table.loc[subid, key] == 'n/a':
                table.loc[subid, key] = data[key]
                data_added            = True

        # Write the data to the participants tsv-file
        if data_added:
            LOGGER.verbose(f"Writing {subid} subject data to: {participants_tsv}")
            if not dryrun:
                table.mask(table == '').to_csv(participants_tsv, sep='\t', encoding='utf-8', na_rep='n/a')

    return table


def addparticipant_meta(participants_json: Path, bidsmap: BidsMap=None) -> dict:
    """
    Read and/or write a participant sidecar file using the participant "meta" fields in the bidsmap

    :param participants_json:   The participants.json sidecar file
    :param bidsmap:             The bidsmap with the participants' metadata. Leave empty to just read the sidecar metadata (write nothing)
    :return:                    The sidecar metadata
    """

    # Read the participants json sidecar
    if participants_json.is_file():
        with participants_json.open('r') as json_fid:
            metadata = json.load(json_fid)
    else:
        metadata = {}

    # Populate the metadata using the bidsmap
    if bidsmap:

        # If we miss metadata then use any participant "meta" field in the bidsmap
        participants_df = addparticipant(participants_json.with_suffix('.tsv'))
        for column in ['participant_id'] + list(participants_df.columns):
            for dataformat in bidsmap.dataformats:
                if not metadata.get(column) and column in dataformat.participant:
                    metadata[column] = dataformat.participant[column].get('meta', {})

        # Save the data
        with participants_json.open('w') as json_fid:
            metadata = json.dump(metadata, json_fid, indent=4)

    return metadata


def bidsprov(bidsfolder: Path, source: Path=Path(), runitem: RunItem=None, targets: Iterable[Path]=()) -> pd.DataFrame:
    """
    Save data transformation information in the bids/code/bidscoin folder (in the future this may be done in accordance with BEP028)

    You can use bidsprov(bidsfolder) to read and return the provenance dataframe

    :param bidsfolder   The bids root folder or one of its subdirectories (e.g. a session folder)
    :param source:      The source file or folder that is being converted
    :param runitem:     The runitem that was used to map the source data, e.g. as returned from get_matching_run()
    :param targets:     The set of output files
    :return:            The dataframe with the provenance data (index_col='source', columns=['runid', 'datatype', 'targets'])
    """

    # Check the input
    while bidsfolder.name and not (bidsfolder/'dataset_description.json').is_file():
        bidsfolder = bidsfolder.parent
    if not bidsfolder.name:
        LOGGER.error(f"Could not resolve the BIDS root folder from {bidsfolder}")
    provfile = bidsfolder/'code'/'bidscoin'/'bidscoiner.tsv'
    targets  = [target.relative_to(bidsfolder) for target in sorted(targets)]
    runitem  = runitem or RunItem()

    # Read the provenance data and add the new data to it
    if provfile.is_file():
        provdata = pd.read_csv(provfile, sep='\t', index_col='source')
    else:
        provdata = pd.DataFrame(columns=['runid', 'datatype', 'targets'])
        provdata.index.name = 'source'

    # Write the provenance data
    if source.name:
        LOGGER.bcdebug(f"Writing provenance data to: {provfile}")
        provdata.loc[str(source)] = [runitem.provenance, runitem.datatype or 'n/a', ', '.join([f"{target.parts[1]+':' if target.parts[0]=='derivatives' else ''}{target.name}" for target in targets])]
        provdata.sort_index().to_csv(provfile, sep='\t')

    return provdata
