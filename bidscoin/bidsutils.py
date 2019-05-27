"""
Module with helper functions
"""

import os
import logging
import copy
import ruamel
try:
    from bidscoin import bids
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed

logger = logging.getLogger('bidscoin')

MODALITY_LABELS = [
    'T1w',
    'T2w',
    'T1rho',
    'T1map',
    'T2map',
    'T2star',
    'FLAIR',
    'FLASH',
    'PD',
    'PDmap',
    'PDT2',
    'inplaneT1',
    'inplaneT2',
    'angio',
    'defacemask',
    'SWImagandphase'
]


def get_list_summary(bidsmap) -> dict:
    """
    Get the list of files from the BIDS map.

    :param bidsmap:     Full BIDS bidsmap data structure, with all options, BIDS labels and attributes, etc
    :return:            A summary of the DICOM series
    """

    list_summary = []

    for modality in bids.bidsmodalities:

        for series in bidsmap['DICOM'][modality]:

            provenance_file = os.path.basename(bidsmap['DICOM'][modality]['provenance'])
            provenance_path = os.path.dirname( bidsmap['DICOM'][modality]['provenance'])

            bids_name = bids.get_bidsname('001', '01', modality, series)

            list_summary.append({
                "modality": modality,
                "provenance_file": provenance_file,
                "provenance_path": provenance_path,
                "bids_name": bids_name
            })

    return list_summary


def delete_sample(bidsmap, modality, index):
    """Delete a sample from the BIDS map. """
    if not modality in bids.bidsmodalities:
        raise ValueError("invalid modality '{}'".format(modality))

    num_samples = get_num_samples(bidsmap, modality)
    if index > num_samples:
        raise IndexError("invalid index {} ({} items found)".format(index, num_samples+1))

    bidsmap_dicom = bidsmap.get('DICOM', ruamel.yaml.comments.CommentedMap())
    bidsmap_dicom_modality = bidsmap_dicom.get(modality, None)
    if bidsmap_dicom_modality is not None:
        del bidsmap['DICOM'][modality][index]
    else:
        logger.warning('modality not found {}'.format(modality))

    return bidsmap


def append_sample(bidsmap, modality, sample):
    """Append a sample to the BIDS map. """
    if not modality in bids.bidsmodalities:
        raise ValueError("invalid modality '{}'".format(modality))

    bidsmap_dicom = bidsmap.get('DICOM', ruamel.yaml.comments.CommentedMap())
    bidsmap_dicom_modality = bidsmap_dicom.get(modality, None)
    if bidsmap_dicom_modality is not None:
        bidsmap['DICOM'][modality].append(sample)
    else:
        bidsmap['DICOM'][modality] = [sample]

    return bidsmap


def update_bidsmap(source_bidsmap, source_modality, source_index, target_modality, target_sample):
    """Update the BIDS map:
    1. Remove the source sample from the source modality section
    2. Add the target sample to the target modality section
    """
    if not source_modality in bids.bidsmodalities:
        raise ValueError("invalid modality '{}'".format(source_modality))

    if not target_modality in bids.bidsmodalities:
        raise ValueError("invalid modality '{}'".format(target_modality))

    target_bidsmap = copy.deepcopy(source_bidsmap)

    # Delete the source sample
    target_bidsmap = delete_sample(target_bidsmap, source_modality, source_index)

    # Append the target sample
    target_bidsmap = append_sample(target_bidsmap, target_modality, target_sample)

    return target_bidsmap
