#!/usr/bin/env python
"""
Creates a bidsmap.yaml config file that maps the information from the data to the
BIDS modalities and BIDS labels (see also [bidsmapper.yaml] and [bidsmapper.py]).
You can edit the bidsmap file before passing it to [bidscoiner.py] which uses it
to cast the datasets into the BIDS folder structure

@author: Marcel Zwiers
"""

import os
import bids
import pandas as pd


def coin_dicom(session, heuristics, bidsfolder):
    """
    Converts the session dicom files into a nifti bids structure

    :param dict session:     Name of the subject/session folder
    :param dict heuristics:  Mapping from the bidsmap yaml-file
    :return:                 Personals extracted from the dicom header
    :rtype: dict
    """

    global logfile

    for series in bids.lsdirs(session):
        bids.printlog('Processing dicomfolder: ' + series, logfile)

        # Get the bids labels and filename and create a bidsfolder
        bidsname   =
        sub_sess   =
        bidsseries = os.path.join(bidsfolder, sub_sess)
        os.makedirs(bidsseries, exist_ok=True)

        # Convert the folder to nifti
        command = 'module add dcm2niix; dcm2niix {options} -f {filename} -o {outfolder} {infolder}'.format(
            options   = heuristics['Options']['dcm2niix'],
            filename  = bidsname,
            outfolder = bidsseries,
            infolder  = session)
        bids.printlog('Executing: ' + command, logfile)

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


def bidscoiner(rawfolder, bidsfolder, bidsmap='code/bidsmap.yaml', force=False):
    """
    Main function that processes all the subjects and session in the rawfolder and uses the
    bidsmap.yaml file in bidsfolder/code to cast the data into the BIDS folder.

    :param str rawfolder:  The root folder-name of the sub/ses/data/file tree containing the source data files
    :param str bidsfolder: The name of the BIDS root folder
    :param dict bidsmap:   The name of the bidsmap yaml-file
    :param bool force:     If True all subjects in the rawfolder will be processed, otherwise only subjects not in particpants.tsv
    :return: Nothing
    :rtype: NoneType
    """

    # Start logging
    global logfile
    logfile = os.path.join(bidsfolder, 'code', 'bidscoiner.log')
    bids.printlog('---------- START ----------\nbidscoiner {arg1} {arg2} {arg3} {arg4}'.format(
        arg1=rawfolder, arg2=bidsfolder, arg3=bidsmap, arg4=force), logfile)

    # Input checking
    rawfolder  = os.path.abspath(os.path.expanduser(rawfolder))
    bidsfolder = os.path.abspath(os.path.expanduser(bidsfolder))

    # Get the heuristics from the created bidsmap
    heuristics = bids.get_heuristics(bidsmap, bidsfolder)

    # See which subjects have not been processed
    participantsfile = os.path.join(bidsfolder, 'participants.tsv')
    if force and os.path.exists(participantsfile):
        participants = pd.read_table(participantsfile)

    else:
        participants = pd.DataFrame(columns = ['participant_id'])

    # Loop over all subjects and sessions and convert them using the bidsmap entries
    subjects = bids.lsdirs(rawfolder, 'sub-*')
    for subject in subjects:

        if subject in list(participants.participant_id): continue

        sessions = bids.lsdirs(subject, 'ses-*')
        if not sessions: sessions = subject
        for session in sessions:

            # Update / append the dicom mapping
            if heuristics['DICOM']:
                personals = coin_dicom(session, heuristics)

            # Update / append the PAR/REC mapping
            if heuristics['PAR']:
                personals_ = coin_par(session, heuristics)
                if personals_: personals = personals_

            # Update / append the P7 mapping
            if heuristics['P7']:
                personals_ = coin_p7(session, heuristics)
                if personals_: personals = personals_

            # Update / append the nifti mapping
            if heuristics['Nifti']:
                coin_nifti(session, heuristics)

            # Update / append the file-system mapping
            if heuristics['FileSystem']:
                coin_filesystem(session, heuristics)

            # Update / append the plugin mapping
            if heuristics['PlugIn']:
                personals_ = coin_plugin(session, heuristics)
                if personals_: personals = personals_

        personals['participant_id'] = os.path.basename(subject)

        # Write the collected personals to the participantsfile
        for key in personals:
            if key not in participants.columns:
                participants[key] = None
        participants = participants.append(personals, ignore_index=False, verify_integrity=True)
        participants.to_csv(participantsfile, sep='\t', encoding='utf-8', index=False)

    bids.printlog('---------- FINISHED! ----------', logfile)


# Shell usage
if __name__ == "__main__":

    # Check input arguments and run query(args)
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n  bidscoiner.py -f /project/raw /project/bids')
    parser.add_argument('rawfolder',    help='The source folder containing the raw data in sub-###/ses-##/series format')
    parser.add_argument('bidsfolder',   help='The destination folder with the bids data structure')
    parser.add_argument('bidsmap',      help='The bidsmap yaml-file with the study heuristics. Default: bidsfolder/code/bidsmap.yaml', nargs='?', default='bidsmap.yaml')
    parser.add_argument('-f','--force', help='If this flag is given all subjects in the rawfolder will be processed, otherwise only subjects not in particpants.tsv', action='store_true')
    args = parser.parse_args()

    bidscoiner(args.rawfolder, args.bidsfolder, args.bidsmapper, args.force)
