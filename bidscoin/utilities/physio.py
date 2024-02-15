"""
Module with helper functions to read and write PHYSIO data to a BIDS compliant tsv-file

Some functions in this module have been derived from the matlab code on (and pushed back to):
https://github.com/CMRR-C2P/MB

@author: Marcel Zwiers
"""

import pandas as pd
import json
import struct
import logging
import numpy as np
import matplotlib.pyplot as plt
import dateutil.parser
from importlib.metadata import version
from typing import Union
from pydicom import dcmread, tag, multival
from pathlib import Path

# Defaults
LOGVERSION = 'EJA_1'                # This is the file format this function expects; must match log file version
FREQ       = 1 / 2.5E-3             # Sampling frequency (the unit of SIEMENS ticks is 2.5 ms)

# Set-up logging
LOGGER = logging.getLogger(__name__)


def readparsefile(fn: Union[bytes,Path], logdatatype: str, firsttime: int=0, expectedsamples: int=0) -> tuple:
    """
    Read and parse physiological traces from the DICOM data or from individual logfiles

    :param fn:              Physiological data from DICOM or the basename of the physiological logfiles
    :param logdatatype:     Datatype that is extracted, e.g. 'ECG', 'RESP', 'PULS' or 'EXT'. Additional metadata is extracted if 'ACQUISITION_INFO'
    :param firsttime:       Value from readparsefile('ACQUISITION_INFO', ..) that has to be passed for parsing other logdatatypes
    :param expectedsamples: Number of samples of the parsed traces
    :return:                traces, UUID[, scandate, nrslices, nrvolumes, firsttime, lasttime, nrechoes] ([..] if logdatatype=='ACQUISITION_INFO')
    """

    # Echoes parameter was not added until R015a, so prefill a default value for compatibility with older data
    nrechoes = 1
    traces   = None

    # Parse the input data into a list of lines
    if isinstance(fn, bytes):                           # If fn is a bytestring, we read it directly from DICOM
        lines = fn.decode('UTF-8').splitlines()
    elif isinstance(fn, Path):                          # Otherwise, fn must be a filename
        LOGGER.verbose(f"Reading physio log-file: {fn}")
        lines = fn.read_text().splitlines()
    else:
        LOGGER.error(f"Wrong input {fn}: {type(fn)}"); raise FileNotFoundError(fn)

    # Extract the metadata and physiological traces
    LOGGER.verbose(f"Parsing {logdatatype} data...")
    for line in [line for line in lines if line]:

        # Strip any leading and trailing whitespace and comments
        line = line.split('#')[0].strip()

        if '=' in line:

            # This is an assigned value; parse it
            varname, value = [item.strip() for item in line.split('=')]

            if varname == 'UUID':
                UUID = value
            if varname == 'LogVersion':
                if value != LOGVERSION:
                    LOGGER.error(f"File format [{value}] not supported by this function (expected [{LOGVERSION}])"); raise NotImplementedError(f"Version{value}")
            if varname == 'LogDataType':
                if value != logdatatype:
                    LOGGER.error(f"Expected [{logdatatype}] data, found [{value}]? Check filenames?"); raise ValueError(value)
            if varname == 'SampleTime':
                if logdatatype == 'ACQUISITION_INFO':
                    LOGGER.error(f"Invalid [{varname}] parameter found"); raise ValueError(varname)
                sampletime = int(value)
            if varname == 'NumSlices':
                if logdatatype != 'ACQUISITION_INFO':
                    LOGGER.error(f"Invalid [{varname}] parameter found"); raise ValueError(varname)
                nrslices = int(value)
            if varname == 'NumVolumes':
                if logdatatype != 'ACQUISITION_INFO':
                    LOGGER.error(f"Invalid [{varname}] parameter found"); raise ValueError(varname)
                nrvolumes = int(value)
            if varname == 'FirstTime':
                if logdatatype != 'ACQUISITION_INFO':
                    LOGGER.error(f"Invalid [{varname}] parameter found"); raise ValueError(varname)
                firsttime = int(value)
            if varname == 'LastTime':
                if logdatatype != 'ACQUISITION_INFO':
                    LOGGER.error(f"Invalid [{varname}] parameter found"); raise ValueError(varname)
                lasttime = int(value)
            if varname == 'NumEchoes':
                if logdatatype != 'ACQUISITION_INFO':
                    LOGGER.error(f"Invalid [{varname}] parameter found"); raise ValueError(varname)
                nrechoes = int(value)
            if varname == 'ScanDate':
                scandate = value

        else:

            # This must be data; currently it is 3-5 columns, pad it with '0' if needed to always have 5 columns
            dataitems = line.split()
            dataitems = [dataitems[n] if n < len(dataitems) else '0' for n in range(5)]

            # If the first column isn't numeric, it is probably the header
            if not dataitems[0].isdigit():
                continue

            # Store data in output array based on the file type
            if logdatatype == 'ACQUISITION_INFO':

                if ('nrvolumes' not in locals() or nrvolumes < 1 or
                    'nrslices'  not in locals() or nrslices  < 1 or
                    'nrechoes'  not in locals() or nrechoes  < 1):
                    LOGGER.error('Failed reading ACQINFO header'); raise RuntimeError(fn)
                if nrvolumes == 1:
                    # This is probably R016a or earlier diffusion data, where NumVolumes is 1 (incorrect)
                    nrvolumes = (len(lines) - 11) / (nrslices * nrechoes)
                    LOGGER.warning(f"Found NumVolumes = 1; correcting to {nrvolumes} for R016a and earlier diffusion data")
                if traces is None:
                    traces = np.zeros((2, nrvolumes, nrslices, nrechoes), dtype=int)
                curvol    = int(dataitems[0])
                curslc    = int(dataitems[1])
                curstart  = int(dataitems[2])
                curfinish = int(dataitems[3])
                if len(dataitems[4]):
                    cureco = int(dataitems[4])
                    if traces[:, curvol, curslc, cureco].any():
                        LOGGER.error(f"Received duplicate timing data for vol{curvol} slc{curslc} eco{cureco}"); raise ValueError(fn)
                else:
                    cureco = 0
                    if traces[:, curvol, curslc, cureco]:
                        LOGGER.warning(f"Received duplicate timing data for vol{curvol} slc{curslc} (ignore for pre-R015a multi-echo data)")
                traces[:, curvol, curslc, cureco] = [curstart, curfinish]

            else:

                curstart   = int(dataitems[0]) - firsttime
                curchannel = dataitems[1]
                curvalue   = int(dataitems[2])

                if logdatatype == 'ECG':
                    if traces is None:
                        traces = np.zeros((expectedsamples, 4), dtype=int)
                    if curchannel not in ['ECG1', 'ECG2', 'ECG3', 'ECG4']:
                        LOGGER.error(f"Invalid ECG channel ID [{curchannel}]"); raise ValueError(curchannel)
                    chaidx = ['ECG1', 'ECG2', 'ECG3', 'ECG4'].index(curchannel)
                elif logdatatype == 'EXT':
                    if traces is None:
                        traces = np.zeros((expectedsamples, 2), dtype=int)
                    if curchannel not in ['EXT', 'EXT1', 'EXT2']:
                        LOGGER.error(f"Invalid EXT channel ID [{curchannel}]"); raise ValueError(curchannel)
                    if curchannel == 'EXT':
                        chaidx = 0
                    else:
                        chaidx = ['EXT1', 'EXT2'].index(curchannel)
                else:
                    if traces is None:
                        traces = np.zeros((expectedsamples, 1), dtype=int)
                    chaidx = 0

                traces[curstart:curstart+int(sampletime), chaidx] = curvalue

    if logdatatype == 'ACQUISITION_INFO':
        traces = traces - firsttime
        return traces, UUID, scandate, nrslices, nrvolumes, firsttime, lasttime, nrechoes
    else:
        return traces, UUID


def readphysio(fn: Union[str,Path]) -> dict:
    """
    Read and plots active (i.e. non-zero) signals from SIEMENS advanced physiological log / DICOM files (>=R013, >=VD13A)
    E. Auerbach, CMRR, 2015-9

    This function expects to find either a combination of individual logfiles (*_ECG.log, *_RESP.log, *_PULS.log, *_EXT.log,
    *_Info.log) generated by >=R013 sequences, or a single encoded "_PHYSIO" DICOM file generated by >=R015 sequences. It
    returns active (i.e. non-zero) physio traces for ECG1, ECG2, ECG3, ECG4, RESP, PULS, EXT/EXT1 and EXT2 signals:

    physio['UUID']:     Universally unique identifier string for this measurement
    physio['ScanDate']: The date/time string of the start of the data acquisition
    physio['Freq']:     Sampling frequency in Hz (= 1/clock-tick; The unit of time is clock-ticks, which normally is 2.5 ms)
    physio['SliceMap']: [2 x Volumes x Slices]     [1:2,:,:] = start & finish time stamp of each volume/slice
    physio['ACQ']:      [length = nr of samples]   True if acquisition is active at this time; False if not
    physio['ECG1']:     [length = nr of samples]   ECG signal on this channel
    physio['ECG2']:     [length = nr of samples]   [..]
    physio['ECG3']:     [length = nr of samples]   [..]
    physio['ECG4']:     [length = nr of samples]   [..]
    physio['RESP']:     [length = nr of samples]   RESP signal on this channel
    physio['PULS']:     [length = nr of samples]   PULS signal on this channel
    physio['EXT1']:     [length = nr of samples]   True if EXT/EXT1 signal detected; False if not
    physio['EXT2']:     [length = nr of samples]   True if EXT2 signal detected; False if not
    physio['Meta']:     Dictionary with additional meta-data from the DICOM header (e.g. 'SeriesNumber')

    :param fn:  Either the fullpath of the DICOM file or the basename of the PHYSIO logfiles (fullpath without suffix and file extension, e.g. 'foo/bar/Physio_DATE_TIME_UUID')
    :return:    The active (non-zero) physio traces for ECG1, ECG2, ECG3, ECG4, RESP, PULS, EXT1 and EXT2 signals
    """

    foundECG = foundRESP = foundPULS = foundEXT = False
    metadata = {}

    # Check input
    fn = Path(fn).resolve()

    # First, check if the input points to a valid DICOM file. If so, extract the physiological data
    if fn.is_file() and fn.name != 'DICOMDIR':
        LOGGER.verbose(f"Reading physio DICOM file: {fn}")
        dicomdata    = dcmread(fn, force=True)          # The DICM tag may be missing for anonymized DICOM files
        manufacturer = dicomdata.get('Manufacturer')
        physiotag    = tag.Tag(0x7fe1, 0x1010)          # A private Siemens tag
        if manufacturer and 'SIEMENS' not in manufacturer.upper():
            LOGGER.warning(f"Unsupported manufacturer: '{manufacturer}', this function is designed for SIEMENS advanced physiological logging data")
        if (dicomdata.get('ImageType')==['ORIGINAL','PRIMARY','RAWDATA','PHYSIO'] and dicomdata.get(physiotag).private_creator=='SIEMENS CSA NON-IMAGE') or \
           (dicomdata.get('ImageType')==['ORIGINAL','PRIMARY','RAWDATA',  'NONE'] and dicomdata.get('SpectroscopyData')) or \
           (dicomdata.get('ImageType') in (['ORIGINAL','PRIMARY','RAWDATA','NONE'], ['ORIGINAL','PRIMARY','OTHER','NONE']) and dicomdata.get(physiotag).private_creator=='SIEMENS MR IMA'):
            if dicomdata.get('SpectroscopyData'):
                physiodata = dicomdata['SpectroscopyData'].value    # XA30-bug. NB: The original Matlab code casts this to uint8 (i.e. to struct.unpack('<'+len(physiodata)*'B', physiodata)
            else:
                physiodata = dicomdata[physiotag].value
            rows    = int(dicomdata.AcquisitionNumber)
            columns = len(physiodata)/rows
            nrfiles = columns/1024
            if columns % 1 or nrfiles % 1:
                LOGGER.error(f"Invalid image size: [rows x columns] = [{rows} x {columns}]"); raise ValueError
            # Encoded DICOM format: columns = 1024*nrfiles
            #                       first row: uint32 datalen, uint32 filenamelen, char[filenamelen] filename
            #                       remaining rows: char[datalen] data
            for idx in range(int(nrfiles)):
                filedata    = physiodata[idx*rows*1024:(idx+1)*rows*1024]
                datalen     = struct.unpack('<L', filedata[0:4])[0]
                filenamelen = struct.unpack('<L', filedata[4:8])[0]
                filename    = filedata[8:8+filenamelen].decode('UTF-8')
                logdata     = filedata[1024:1024+datalen]
                LOGGER.verbose(f"Decoded: {filename}")
                if filename.endswith('_Info.log'):
                    fnINFO    = logdata
                elif filename.endswith('_ECG.log'):
                    fnECG     = logdata
                    foundECG  = True
                elif filename.endswith('_RESP.log'):
                    fnRESP    = logdata
                    foundRESP = True
                elif filename.endswith('_PULS.log'):
                    fnPULS    = logdata
                    foundPULS = True
                elif filename.endswith('_EXT.log'):
                    fnEXT     = logdata
                    foundEXT  = True
        else:
            LOGGER.error(f"{fn} is not a valid DICOM format file"); raise RuntimeError(f"Invalid DICOM: {fn}")

        # Add some (BIDS) meta-data from the DICOM header
        for key in ('Modality',
                    'Manufacturer',
                    'ManufacturerModelName',
                    'StationName',
                    'DeviceSerialNumber',
                    'SoftwareVersions',
                    'InstitutionName',
                    'InstitutionAddress',
                    'PatientPosition',
                    'BodyPartExamined',
                    'ImageType',
                    'ProtocolName',
                    'SeriesDescription',
                    'SeriesNumber',
                    'AcquisitionNumber'):
            val = dicomdata.get(key, '')
            if isinstance(val, multival.MultiValue):
                val = list(val)
            metadata[key] = val

    # If we don't have an encoded DICOM, check what text log files we have
    else:
        fnINFO = fn.with_name(fn.name + '_Info.log')
        fnECG  = fn.with_name(fn.name + '_ECG.log')
        fnRESP = fn.with_name(fn.name + '_RESP.log')
        fnPULS = fn.with_name(fn.name + '_PULS.log')
        fnEXT  = fn.with_name(fn.name + '_EXT.log')
        if not fnINFO.is_file():
            LOGGER.error(f"{fnINFO} not found"); raise FileNotFoundError(fnINFO)
        foundECG  = fnECG.is_file()
        foundRESP = fnRESP.is_file()
        foundPULS = fnPULS.is_file()
        foundEXT  = fnEXT.is_file()

    if not foundECG and not foundRESP and not foundPULS and not foundEXT:
        LOGGER.error('No data files (ECG/RESP/PULS/EXT) found'); raise FileNotFoundError(fn)

    # Read in and/or parse the data
    slicemap, UUID1, scandate, nrslices, nrvolumes, firsttime, lasttime, nrechoes = readparsefile(fnINFO, 'ACQUISITION_INFO')
    if lasttime <= firsttime:
        LOGGER.error(f"Last timestamp {lasttime} is not greater than first timestamp {firsttime}, aborting..."); raise ValueError(lasttime)
    actualsamples   = lasttime - firsttime + 1
    expectedsamples = actualsamples + 8         # Some padding at the end for worst case EXT sample at last timestamp

    if foundECG:
        ECG, UUID2 = readparsefile(fnECG, 'ECG', firsttime, expectedsamples)
        if UUID1 != UUID2:
            LOGGER.error('UUID mismatch between Info and ECG files'); raise ValueError(UUID2)

    if foundRESP:
        RESP, UUID3 = readparsefile(fnRESP, 'RESP', firsttime, expectedsamples)
        if UUID1 != UUID3:
            LOGGER.error('UUID mismatch between Info and RESP files'); raise ValueError(UUID3)

    if foundPULS:
        PULS, UUID4 = readparsefile(fnPULS, 'PULS', firsttime, expectedsamples)
        if UUID1 != UUID4:
            LOGGER.error('UUID mismatch between Info and PULS files'); raise ValueError(UUID4)

    if foundEXT:
        EXT, UUID5 = readparsefile(fnEXT, 'EXT', firsttime, expectedsamples)
        if UUID1 != UUID5:
            LOGGER.error('UUID mismatch between Info and EXT files'); raise ValueError(UUID5)

    LOGGER.verbose(f"Slices in scan:      {nrslices}")
    LOGGER.verbose(f"Volumes in scan:     {nrvolumes}")
    LOGGER.verbose(f"Echoes per slc/vol:  {nrechoes}")
    LOGGER.verbose(f"First timestamp:     {firsttime}")
    LOGGER.verbose(f"Last timestamp:      {lasttime}")
    LOGGER.verbose(f"Total scan duration: {actualsamples} ticks = {actualsamples / FREQ:.4f} s")

    LOGGER.verbose('Formatting ACQ data...')
    ACQ = np.full((expectedsamples, 1), False)
    for v in range(nrvolumes):
        for s in range(nrslices):
            for e in range(nrechoes):
                ACQ[slicemap[0,v,s,e]:slicemap[1,v,s,e]+1, 0] = True

    # Only return active (nonzero) physio traces
    physio             = {}
    physio['UUID']     = UUID1
    physio['ScanDate'] = dateutil.parser.parse(scandate, fuzzy=True).isoformat()
    physio['Freq']     = FREQ
    physio['SliceMap'] = slicemap
    physio['Meta']     = metadata
    physio['ACQ']      = ACQ[:,0]
    if foundECG and ECG.any():
        if sum(ECG[:,0]): physio['ECG1'] = ECG[:,0]
        if sum(ECG[:,1]): physio['ECG2'] = ECG[:,1]
        if sum(ECG[:,2]): physio['ECG3'] = ECG[:,2]
        if sum(ECG[:,3]): physio['ECG4'] = ECG[:,3]
    if foundRESP and RESP.any():
        if sum(RESP):     physio['RESP'] = RESP[:,0]
    if foundPULS and PULS.any():
        if sum(PULS):     physio['PULS'] = PULS[:,0]
    if foundEXT and EXT.any():
        if sum(EXT[:,0]): physio['EXT1'] = EXT[:,0]
        if sum(EXT[:,1]): physio['EXT2'] = EXT[:,1]

    return physio


def physio2tsv(physio: dict, tsvfile: Union[str, Path]):
    """
    Saves the physiological traces to a BIDS-compliant [tsvfile].tsv.nii and a [tsvfile].log file

    :param physio:  Physio data dictionary from readphysio
    :param tsvfile: Fullpath name of the (BIDS) output .tsv.gz/.json file
    :return:
    """

    # Check input
    tsvfile = Path(tsvfile).resolve().with_suffix('').with_suffix('.tsv.gz')

    # Set the clock at zero at the start of the MRI acquisition
    starttime = -physio['ACQ'].nonzero()[0][0] / physio['Freq']     # Assumes that the physiological acquisition always starts before the MRI acquisition

    # Add each trace to a data table and save the table as a BIDS-compliant gzipped tsv file
    physiotable = pd.DataFrame(columns=[key for key in physio if key not in ('UUID','ScanDate','Freq','SliceMap','ACQ','Meta')])
    for key in physiotable.columns:
        physiotable[key] = physio[key]
    LOGGER.verbose(f"Writing physiological traces to: '{tsvfile}'")
    physiotable.to_csv(tsvfile, header=False, index=False, sep='\t', compression='infer')

    # Write a json side-car file
    try:
        bidscoinversion = version('bidscoin')
    except Exception:
        bidscoinversion = 'n/a'
    physio['Meta']['SamplingFrequency'] = physio['Freq']
    physio['Meta']['StartTime']         = starttime
    physio['Meta']['AcquisitionTime']   = dateutil.parser.parse(physio['ScanDate']).strftime('%H:%M:%S')
    physio['Meta']['Columns']           = physiotable.columns.to_list()
    physio['Meta']['GeneratedBy']       = [{'name':'BIDScoin', 'Version':bidscoinversion, 'CodeURL':'https://github.com/Donders-Institute/bidscoin'}]
    with tsvfile.with_suffix('').with_suffix('.json').open('w') as json_fid:
        json.dump(physio['Meta'], json_fid, indent=4)


def plotphysio(physio:dict, showsamples: int=1000):
    """
    Plot the samples of the physiological traces in a rudimentary way. If too large, only plot the middle 'showsamples' ticks

    :param physio:      Physio data dictionary from readphysio
    :param showsamples: The nr of plotted samples of the physiological traces (nothing is plotted if showsamples==0)
    """

    miny, maxy = 5E4, -5E4      # Actual range is 0..4095
    nrsamples  = len(physio['ACQ'])
    starttick  = 0
    endtick    = nrsamples
    if nrsamples > showsamples:
        starttick = int(nrsamples / 2) - int(showsamples / 2)
        endtick   = starttick + showsamples
    ticks = np.arange(starttick, endtick)

    def plot_trace(logdatatype, scale, color):
        """Plot the trace and update minimum and maximum values"""
        if logdatatype not in physio: return
        nonlocal miny, maxy
        trace    = physio[logdatatype][starttick:endtick]
        mintrace = int(min(trace))      # type(ACQ)==bool
        maxtrace = int(max(trace))
        if scale and (miny != mintrace or maxy != maxtrace) and mintrace != maxtrace:
            trace = (trace - mintrace) * (maxy - miny)/(maxtrace - mintrace) + miny
        else:
            miny = min(miny, mintrace)  # Update the (non-local) minimum
            maxy = max(maxy, maxtrace)  # Update the (non-local) maximum
        if logdatatype == 'ACQ':
            plt.fill_between(ticks, trace, miny, color=color, label=logdatatype)
        else:
            plt.plot(ticks, trace, color=color, label=logdatatype)

    plt.figure(num=f"readphysio: UUID {physio['UUID']}")
    plot_trace('ECG1', False, 'green')
    plot_trace('ECG2', False, 'green')
    plot_trace('ECG3', False, 'green')
    plot_trace('ECG4', False, 'green')
    plot_trace('RESP', False, 'blue')
    plot_trace('PULS', False, 'red')
    plot_trace('EXT1', True,  'cyan')
    plot_trace('EXT2', True,  'olive')
    plot_trace('ACQ',  True,  'lightgray')

    plt.legend(loc='lower right')
    plt.axis([starttick, endtick-1, miny - maxy*0.05, maxy + maxy*0.05])
    plt.title('Physiological traces')
    plt.xlabel('Samples')
    plt.show()
