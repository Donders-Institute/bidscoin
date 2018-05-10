#!/usr/bin/env python
"""
Converts datasets in the rawfolder to nifti datasets in the bidsfolder according to the BIDS standard

@author: Marcel Zwiers
"""

import os
import bids
import pandas as pd
import subprocess


def coin_dicom(session, heuristics, bidsfolder):
    """
    Converts the session dicom-files into BIDS-valid nifti files in the corresponding bidsfolder

    :param dict session:    The full-path name of the subject/session folder
    :param dict heuristics: Mapping heuristics from the bidsmap yaml-file
    :param str bidsfolder:  The full-path name of the BIDS root-folder
    :return:                Personals extracted from the dicom header
    :rtype: dict
    """

    global logfile

    for series in bids.lsdirs(session):

        bids.printlog('Processing dicomfolder: ' + series, logfile)

        # Get the bids labels and filename and create a bidsfolder
        bidsname   = ''     # TODO
        sub_sess   = ''     # TODO
        bidsseries = os.path.join(bidsfolder, sub_sess)
        os.makedirs(bidsseries, exist_ok=True)

        # Convert the folder to nifti
        command = 'module add dcm2niix; dcm2niix {options} -f {filename} -o {outfolder} {infolder}'.format(
            options   = heuristics['Options']['dcm2niix'],
            filename  = bidsname,
            outfolder = bidsseries,
            infolder  = session)
        bids.printlog('Executing: ' + command, logfile)
        process = subprocess.run(command, stdout=subprocess.PIPE, shell=True)
        bids.printlog('TODO: stdout &> stderr', logfile)
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


def coin_plugin(sessionfolder, heuristics):
    """
    Run the plugin coiner to cast the series into the bids folder

    :param str sessionfolder:
    :param dict heuristics:
    :return: personals
    :rtype: dict
    """

    from importlib import import_module
    global logfile

    # Import and run the plugins
    for pluginfunction in heuristics['PlugIn']:
        plugin    = import_module(os.path.join(__file__, 'plugins', pluginfunction))
        personals = plugin.coin(sessionfolder, heuristics)

    return personals


def bidscoiner(rawfolder, bidsfolder, bidsmap='code/bidsmap.yaml', subjects=[], participants=False, force=False):
    """
    Main function that processes all the subjects and session in the rawfolder and uses the
    bidsmap.yaml file in bidsfolder/code to cast the data into the BIDS folder.

    :param str rawfolder:     The root folder-name of the sub/ses/data/file tree containing the source data files
    :param str bidsfolder:    The name of the BIDS root folder
    :param str bidsmap:       The name of the bidsmap yaml-file
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
        arg1=rawfolder, arg2=bidsfolder, arg3=bidsmap, arg4=subjects, arg5=participants, arg6=force), logfile)

    # Input checking
    rawfolder  = os.path.abspath(os.path.expanduser(rawfolder))
    bidsfolder = os.path.abspath(os.path.expanduser(bidsfolder))
    if not subjects:
        subjects = bids.lsdirs(rawfolder, 'sub-*')

    # Get the heuristics from the created bidsmap
    heuristics = bids.get_heuristics(bidsmap, bidsfolder)

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
            if heuristics['DICOM']:
                personals = coin_dicom(session, heuristics, bidsfolder)

            # Update / append the PAR/REC mapping
            if heuristics['PAR']:
                personals_ = coin_par(session, heuristics, bidsfolder)
                if personals_: personals = personals_

            # Update / append the P7 mapping
            if heuristics['P7']:
                personals_ = coin_p7(session, heuristics, bidsfolder)
                if personals_: personals = personals_

            # Update / append the nifti mapping
            if heuristics['Nifti']:
                coin_nifti(session, heuristics, bidsfolder)

            # Update / append the file-system mapping
            if heuristics['FileSystem']:
                coin_filesystem(session, heuristics, bidsfolder)

            # Update / append the plugin mapping
            if heuristics['PlugIn']:
                personals_ = coin_plugin(session, heuristics, bidsfolder)
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
    parser.add_argument('rawfolder',           help='The source folder containing the raw data in sub-###/ses-##/series format')
    parser.add_argument('bidsfolder',          help='The destination folder with the bids data structure')
    parser.add_argument('bidsmap',             help='The bidsmap yaml-file with the study heuristics. Default: bidsfolder/code/bidsmap.yaml', nargs='?', default='bidsmap.yaml')
    parser.add_argument('-s','--subjects',     help='Space seperated list of selected sub-# names / folders to be processed. Otherwise all subjects in the rawfolder will be selected')    # TODO: Add space seperated list options
    parser.add_argument('-p','--participants', help='If this flag is given only those subjects that are not in particpants.tsv will be processed', action='store_true')
    parser.add_argument('-f','--force',        help='If this flag is given subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise existing folders will be skipped', action='store_true')
    args = parser.parse_args()

    bidscoiner(args.rawfolder, args.bidsfolder, args.bidsmapper, args.subject, args.participants, args.force)
