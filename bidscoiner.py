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

    # Get the subject and session identifiers from the foldername
    subid = 'sub-' + session.rsplit('/sub-',1)[1].split('/ses-',1)[0]
    if '/ses-' in session:
        sesid = 'ses-' + session.rsplit('/ses-')[1]
    else:
        sesid = ''

    # Create the BIDS session-folder
    bidsseries = os.path.join(bidsfolder, subid, sesid)         # NB: This gives a trailing '/' if ses=='', but that should be ok
    os.makedirs(bidsseries, exist_ok=True)

    # Process the individual series
    for series in bids.lsdirs(session):

        bids.printlog('Processing dicom-folder: ' + series, logfile)

        # Get the cleaned-up bids labels from a dicom-file and bidsmap
        dicomfile = bids.get_dicomfile(series)
        result    = bids.get_matching_dicomseries(dicomfile, bidsmap)
        series_   = result['series']
        modality  = result['modality']

        # Create the BIDS session/modality folder
        bidsmodality = os.path.join(bidsseries, modality)
        os.makedirs(bidsmodality, exist_ok=True)

        # Compose the BIDS filename using the bids labels and run-index
        runindex = bids.get_runindex(series)
        bidsname = bids.get_bidsname(subid, sesid, modality, series_, str(runindex))

        # Convert the dicom-files in the source folder to nifti's in the BIDS-folder
        command = 'module add dcm2niix; dcm2niix {options} -f {filename} -o {outfolder} {infolder}'.format(
            options   = bidsmap['Options']['dcm2niix'],
            filename  = bidsname,
            outfolder = bidsmodality,
            infolder  = series)
        bids.printlog('$ ' + command, logfile)
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        bids.printlog(process.stdout.decode('utf-8'), logfile)
        if process.returncode != 0:
            errormsg = 'Failed to process {} (errorcode {})'.format(series, process.returncode)
            bids.printlog(errormsg, logfile)

    # Collect personal data from the DICOM header
    dicomfile           = bids.get_dicomfile(series)
    personals           = dict()
    personals['age']    = bids.get_dicomfield('PatientAge',    dicomfile)
    personals['sex']    = bids.get_dicomfield('PatientSex',    dicomfile)
    personals['size']   = bids.get_dicomfield('PatientSize',   dicomfile)
    personals['weight'] = bids.get_dicomfield('PatientWeight', dicomfile)

    return personals


def coin_par(session, bidsmap, bidsfolder):
    """

    :param str session:     The full-path name of the subject/session source folder
    :param dict bidsmap:    The full mapping heuristics from the bidsmap yaml-file
    :param str bidsfolder:  The full-path name of the BIDS root-folder
    :return:                Nothing
    :rtype: NoneType
    """

    global logfile
    bids.printlog('coin_par is WIP!!!', logfile)


def coin_p7(session, bidsmap, bidsfolder):
    """

    :param str session:     The full-path name of the subject/session source folder
    :param dict bidsmap:    The full mapping heuristics from the bidsmap yaml-file
    :param str bidsfolder:  The full-path name of the BIDS root-folder
    :return:                Nothing
    :rtype: NoneType
    """

    global logfile
    bids.printlog('coin_p7 is WIP!!!', logfile)


def coin_nifti(session, bidsmap, bidsfolder):
    """

    :param str session:     The full-path name of the subject/session source folder
    :param dict bidsmap:    The full mapping heuristics from the bidsmap yaml-file
    :param str bidsfolder:  The full-path name of the BIDS root-folder
    :return:                Nothing
    :rtype: NoneType
    """

    global logfile
    bids.printlog('coin_nifti is WIP!!!', logfile)


def coin_filesystem(session, bidsmap, bidsfolder):
    """

    :param str session:     The full-path name of the subject/session source folder
    :param dict bidsmap:    The full mapping heuristics from the bidsmap yaml-file
    :param str bidsfolder:  The full-path name of the BIDS root-folder
    :return:                Nothing
    :rtype: NoneType
    """

    global logfile
    bids.printlog('coin_filesystem is WIP!!!', logfile)


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


def bidscoiner(rawfolder, bidsfolder, subjects=[], force=False, participants=False, bidsmapfile='code/bidsmap.yaml'):
    """
    Main function that processes all the subjects and session in the rawfolder and uses the
    bidsmap.yaml file in bidsfolder/code to cast the data into the BIDS folder.

    :param str rawfolder:     The root folder-name of the sub/ses/data/file tree containing the source data files
    :param str bidsfolder:    The name of the BIDS root folder
    :param list subjects:     List of selected sub-# names / folders to be processed. Otherwise all subjects in the rawfolder will be selected
    :param bool force:        If True, subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise existing folders will be skipped
    :param bool participants: If True only subjects not in particpants.tsv will be processed (this could be used e.g. to protect these subjects from being reprocessed)
    :param str bidsmapfile:   The name of the bidsmap yaml-file
    :return: Nothing
    :rtype: NoneType
    """

    # Input checking
    rawfolder  = os.path.abspath(os.path.expanduser(rawfolder))
    bidsfolder = os.path.abspath(os.path.expanduser(bidsfolder))

    # Start logging
    global logfile
    logfile = os.path.join(bidsfolder, 'code', 'bidscoiner.log')
    bids.printlog('------------ START ------------\n>>> bidscoiner rawfolder={arg1} bidsfolder={arg2} subjects={arg3} force={arg4} participants={arg5} bidsmap={arg6}'.format(
        arg1=rawfolder, arg2=bidsfolder, arg3=subjects, arg4=force, arg5=participants, arg6=bidsmapfile), logfile)

    # Get the bidsmap heuristics from the bidsmap yaml-file
    bidsmap = bids.get_heuristics(bidsmapfile, os.path.join(bidsfolder,'code'))

    # Read the table with subjects that have been processed
    participants_file = os.path.join(bidsfolder, 'participants.tsv')
    if participants and os.path.exists(participants_file):
        participants_table = pd.read_table(participants_file)

    else:
        participants_table = pd.DataFrame(columns = ['participant_id'])

    # Get the list of subjects
    if not subjects:
        subjects = bids.lsdirs(rawfolder, 'sub-*')
    else:
        subjects = [os.path.join(rawfolder,subject) for subject in subjects if os.path.isdir(os.path.join(rawfolder,subject))]

    # Loop over all subjects and sessions and convert them using the bidsmap entries
    for subject in subjects:

        if subject in list(participants_table.participant_id): continue

        sessions = bids.lsdirs(subject, 'ses-*')
        if not sessions: sessions = subject
        for session in sessions:

            # Check if we should skip the session-folder
            personals = dict()
            if not force and os.path.isdir(session.replace(rawfolder, bidsfolder)):
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

        if personals:
            personals['participant_id'] = os.path.basename(subject)

            # Write the collected personals to the participants_file
            for key in personals:
                if key not in participants_table.columns:
                    participants_table[key] = None
            participants_table = participants_table.append(personals, ignore_index=True, verify_integrity=True)
            participants_table.to_csv(participants_file, sep='\t', encoding='utf-8', index=False)

    bids.printlog('------------ FINISHED! ------------', logfile)


# Shell usage
if __name__ == "__main__":

    # Parse the input arguments and run bidscoiner(args)
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n  bidscoiner.py /project/raw /project/bids\n  bidscoiner.py -f /project/raw /project/bids -s sub-009 sub-030')
    parser.add_argument('rawfolder',           help='The source folder containing the raw data in sub-#/ses-#/series format')
    parser.add_argument('bidsfolder',          help='The destination folder with the bids data structure')
    parser.add_argument('-s','--subjects',     help='Space seperated list of selected sub-# names / folders to be processed. Otherwise all subjects in the rawfolder will be selected', nargs='*')
    parser.add_argument('-f','--force',        help='If this flag is given subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise existing folders will be skipped', action='store_true')
    parser.add_argument('-p','--participants', help='If this flag is given only those subjects that are not in particpants.tsv will be processed (this could be used e.g. to protect these subjects from being reprocessed)', action='store_true')
    parser.add_argument('-b','--bidsmap',      help='The bidsmap yaml-file with the study heuristics. Default: bidsfolder/code/bidsmap.yaml', default='bidsmap.yaml')
    args = parser.parse_args()

    bidscoiner(rawfolder=args.rawfolder, bidsfolder=args.bidsfolder, subjects=args.subjects, force=args.force, participants=args.participants, bidsmapfile=args.bidsmap)
