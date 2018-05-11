#!/usr/bin/env python
"""
Converts datasets in the rawfolder to nifti datasets in the bidsfolder according to the BIDS standard

@author: Marcel Zwiers
"""

import os
import bids
import pandas as pd
import subprocess


def coin_dicom(session, bidsmap, bidsfolder):
    """
    Converts the session dicom-files into BIDS-valid nifti-files in the corresponding bidsfolder

    :param str session:    The full-path name of the subject/session source folder
    :param dict bidsmap:   The full mapping heuristics from the bidsmap yaml-file
    :param str bidsfolder: The full-path name of the BIDS root-folder
    :return:               Personals extracted from the dicom header
    :rtype: dict
    """

    global logfile

    # Create the BIDS session-folder
    bidsseries = os.path.join(bidsfolder, session.rsplit('/sub-')[1])
    os.makedirs(bidsseries, exist_ok=True)

    # Process the individual series
    for series in bids.lsdirs(session):

        bids.printlog('Processing dicom-folder: ' + series, logfile)

        # Get the bids labels from a dicom-file and bidsmap to compose the BIDS filename
        dicomfile = bids.get_dicom_file(series)
        for modality in bids.bidsmodalities:
            series_ = bids.get_matching_series(series, bidsmap['DICOM'][modality])
            if series_:
                seriesdict =

        bidsname   = ''     # TODO

        # Convert the dicom-files in the source folder to nifti's in the BIDS-folder
        command = 'module add dcm2niix; dcm2niix {options} -f {filename} -o {outfolder} {infolder}'.format(
            options   = bidsmap['Options']['dcm2niix'],
            filename  = bidsname,
            outfolder = bidsseries,
            infolder  = series)
        bids.printlog('Executing: ' + command, logfile)
        process = subprocess.run(command, stdout=subprocess.PIPE, shell=True)
        bids.printlog('TODO: print dcm2niix stdout &> stderr', logfile)
        if process.returncode != 0:
            errormsg = 'Failed to process {} (errorcode {})'.format(series, process.returncode)
            bids.printlog(errormsg, logfile)


    # Collect personal data from the DICOM header
    dicomfile           = bids.get_dicom_file(series)
    personals           = dict()
    personals['age']    = bids.get_dicomfield('PatientAge',    dicomfile)
    personals['sex']    = bids.get_dicomfield('PatientSex',    dicomfile)
    personals['size']   = bids.get_dicomfield('PatientSize',   dicomfile)
    personals['weight'] = bids.get_dicomfield('PatientWeight', dicomfile)

    return personals


def coin_plugin(session, bidsmap, bidsfolder):
    """
    Run the plugin coiner to cast the series into the bids folder

    :param str session:     The full-path name of the subject/session source folder
    :param dict bidsmap:    The full mapping heuristics from the bidsmap yaml-file
    :param str bidsfolder:  The full-path name of the BIDS root-folder
    :return:                Personals extracted from the dicom header
    :rtype: dict
    """

    from importlib import import_module
    global logfile

    # Import and run the plugins
    for pluginfunction in bidsmap['PlugIn']:
        plugin    = import_module(os.path.join(__file__, 'plugins', pluginfunction))
        # TODO: check first if the plug-in function exist
        personals = plugin.bidscoiner(session, bidsmap, bidsfolder)

    return personals


def bidscoiner(rawfolder, bidsfolder, bidsmapfile='code/bidsmap.yaml', subjects=[], participants=False, force=False):
    """
    Main function that processes all the subjects and session in the rawfolder and uses the
    bidsmap.yaml file in bidsfolder/code to cast the data into the BIDS folder.

    :param str rawfolder:     The root folder-name of the sub/ses/data/file tree containing the source data files
    :param str bidsfolder:    The name of the BIDS root folder
    :param str bidsmapfile:   The name of the bidsmap yaml-file
    :param list subjects:     List of selected sub-# names / folders to be processed. Otherwise all subjects in the rawfolder will be selected
    :param bool participants: If True only subjects not in particpants.tsv will be processed
    :param bool force:        If True, subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise existing folders will be skipped
    :return: Nothing
    :rtype: NoneType
    """

    # Start logging
    global logfile
    logfile = os.path.join(bidsfolder, 'code', 'bidscoiner.log')
    bids.printlog('---------- START ----------\nbidscoiner {arg1} {arg2} {arg3} {arg4} {arg5} {arg6}'.format(
        arg1=rawfolder, arg2=bidsfolder, arg3=bidsmapfile, arg4=subjects, arg5=participants, arg6=force), logfile)

    # Input checking
    rawfolder  = os.path.abspath(os.path.expanduser(rawfolder))
    bidsfolder = os.path.abspath(os.path.expanduser(bidsfolder))
    if not subjects:
        subjects = bids.lsdirs(rawfolder, 'sub-*')

    # Get the bidsmap heuristics from the bidsmap yaml-file
    bidsmap = bids.get_heuristics(bidsmapfile, bidsfolder)

    # See which subjects have not been processed
    participants_file = os.path.join(bidsfolder, 'participants.tsv')
    if participants and os.path.exists(participants_file):
        participants_table = pd.read_table(participants_file)

    else:
        participants_table = pd.DataFrame(columns = ['participant_id'])

    # Loop over all subjects and sessions and convert them using the bidsmap entries
    for subject in subjects:

        if subject in list(participants_table.participant_id): continue

        sessions = bids.lsdirs(subject, 'ses-*')
        if not sessions: sessions = subject
        for session in sessions:

            # Check if we should skip the session-folder
            if not force and os.path.isdir(session):
                continue

            # Update / append the dicom mapping
            if bidsmap['DICOM']:
                personals = coin_dicom(session, bidsmap, bidsfolder)

            # Update / append the PAR/REC mapping
            if bidsmap['PAR']:
                personals_ = coin_par(session, bidsmap, bidsfolder)
                if personals_: personals = personals_

            # Update / append the P7 mapping
            if bidsmap['P7']:
                personals_ = coin_p7(session, bidsmap, bidsfolder)
                if personals_: personals = personals_

            # Update / append the nifti mapping
            if bidsmap['Nifti']:
                coin_nifti(session, bidsmap, bidsfolder)

            # Update / append the file-system mapping
            if bidsmap['FileSystem']:
                coin_filesystem(session, bidsmap, bidsfolder)

            # Update / append the plugin mapping
            if bidsmap['PlugIn']:
                personals_ = coin_plugin(session, bidsmap, bidsfolder)
                if personals_: personals = personals_

        personals['participant_id'] = os.path.basename(subject)

        # Write the collected personals to the participants_file
        for key in personals:
            if key not in participants_table.columns:
                participants_table[key] = None
        participants_table = participants_table.append(personals, ignore_index=False, verify_integrity=True)
        participants_table.to_csv(participants_file, sep='\t', encoding='utf-8', index=False)

    bids.printlog('---------- FINISHED! ----------', logfile)


# Shell usage
if __name__ == "__main__":

    # Parse the input arguments and run bidscoiner(args)
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n  bidscoiner.py -f /project/raw /project/bids')
    parser.add_argument('rawfolder',           help='The source folder containing the raw data in sub-#/ses-#/series format')
    parser.add_argument('bidsfolder',          help='The destination folder with the bids data structure')
    parser.add_argument('bidsmap',             help='The bidsmap yaml-file with the study heuristics. Default: bidsfolder/code/bidsmap.yaml', nargs='?', default='bidsmap.yaml')
    parser.add_argument('-s','--subjects',     help='Space seperated list of selected sub-# names / folders to be processed. Otherwise all subjects in the rawfolder will be selected')    # TODO: Add space seperated list options
    parser.add_argument('-p','--participants', help='If this flag is given only those subjects that are not in particpants.tsv will be processed', action='store_true')
    parser.add_argument('-f','--force',        help='If this flag is given subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise existing folders will be skipped', action='store_true')
    args = parser.parse_args()

    bidscoiner(args.rawfolder, args.bidsfolder, args.bidsmapper, args.subject, args.participants, args.force)
