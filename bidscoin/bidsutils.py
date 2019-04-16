"""
Module with helper functions
"""

import os
import logging
import ruamel.yaml as yaml


logger = logging.getLogger('bidscoin')


BIDS_LABELS = [
    'acq_label',
    'modality_label',
    'ce_label',
    'rec_label',
    'task_label',
    'echo_index',
    'dir_label',
    'suffix'
]


def show_label(label):
    """Determine if label needs to be shown in BIDS name. """
    if label is None or label == "":
        return False
    else:
        return True


def get_bids_name_array(subid, sesid, modality, bids_values, run):
    """Return the components of the BIDS name as an array. """
    bids_name_array = []

    if modality == 'anat':
        defacemask = False # TODO: account for defacemask possibility
        suffix = bids_values.get('modality_label', '')
        mod = ''

        # bidsname: sub-<participant_label>[_ses-<session_label>][_acq-<label>][_ce-<label>][_rec-<label>][_run-<index>][_mod-<label>]_suffix
        bids_name_array = [
            {
                'prefix': 'sub-',
                'label': subid,
                'show': True # mandatory
            },
            {
                'prefix': 'ses-',
                'label': sesid,
                'show': show_label(sesid)
            },
            {
                'prefix': 'acq-',
                'label': bids_values['acq_label'],
                'show': show_label(bids_values['acq_label'])
            },
            {
                'prefix': 'ce-',
                'label': bids_values['ce_label'],
                'show': show_label(bids_values['ce_label'])
            },
            {
                'prefix': 'rec-',
                'label': bids_values['rec_label'],
                'show': show_label(bids_values['rec_label'])
            },
            {
                'prefix': 'run-',
                'label': run,
                'show': show_label(run)
            },
            {
                'prefix': 'mod-',
                'label': mod,
                'show': show_label(mod)
            },
            {
                'prefix': '',
                'label': suffix,
                'show': True # mandatory
            }
        ]

    elif modality == 'func':
        # bidsname: sub-<participant_label>[_ses-<session_label>]_task-<task_label>[_acq-<label>][_rec-<label>][_run-<index>][_echo-<index>]_suffix
        bids_name_array = [
            {
                'prefix': 'sub-',
                'label': subid,
                'show': True # mandatory
            },
            {
                'prefix': 'ses-',
                'label': sesid,
                'show': show_label(sesid)
            },
            {
                'prefix': 'task-',
                'label': bids_values['task_label'],
                'show': True # mandatory
            },
            {
                'prefix': 'acq-',
                'label': bids_values['acq_label'],
                'show': show_label(bids_values['acq_label'])
            },
            {
                'prefix': 'rec-',
                'label': bids_values['rec_label'],
                'show': show_label(bids_values['rec_label'])
            },
            {
                'prefix': 'run-',
                'label': run,
                'show': show_label(run)
            },
            {
                'prefix': 'echo-',
                'label': bids_values['echo_index'],
                'show': show_label(bids_values['echo_index'])
            },
            {
                'prefix': '',
                'label': suffix,
                'show': True # mandatory
            }
        ]

    elif modality == 'dwi':
        # bidsname: sub-<participant_label>[_ses-<session_label>][_acq-<label>][_run-<index>]_suffix
        bids_name_array = [
            {
                'prefix': 'sub-',
                'label': subid,
                'show': True # mandatory
            },
            {
                'prefix': 'ses-',
                'label': sesid,
                'show': show_label(sesid)
            },
            {
                'prefix': 'acq-',
                'label': bids_values['acq_label'],
                'show': show_label(bids_values['acq_label'])
            },
            {
                'prefix': 'run-',
                'label': run,
                'show': show_label(run)
            },
            {
                'prefix': '',
                'label': suffix,
                'show': True # mandatory
            }
        ]

    elif modality == 'fmap':
        # TODO: add more fieldmap logic?
        # bidsname: sub-<participant_label>[_ses-<session_label>][_acq-<label>][_dir-<dir_label>][_run-<run_index>]_suffix
        bids_name_array = [
            {
                'prefix': 'sub-',
                'label': subid,
                'show': True # mandatory
            },
            {
                'prefix': 'ses-',
                'label': sesid,
                'show': show_label(sesid)
            },
            {
                'prefix': 'acq-',
                'label': bids_values['acq_label'],
                'show': show_label(bids_values['acq_label'])
            },
            {
                'prefix': 'dir-',
                'label': bids_values['dir_label'],
                'show': show_label(bids_values['dir_label'])
            },
            {
                'prefix': 'run-',
                'label': run,
                'show': show_label(run)
            },
            {
                'prefix': '',
                'label': suffix,
                'show': True # mandatory
            }
        ]

    elif modality == 'beh':
        # bidsname: sub-<participant_label>[_ses-<session_label>]_task-<task_name>_suffix
        bids_name_array = [
            {
                'prefix': 'sub-',
                'label': subid,
                'show': True # mandatory
            },
            {
                'prefix': 'ses-',
                'label': sesid,
                'show': show_label(sesid)
            },
            {
                'prefix': 'task-',
                'label': bids_values['task_label'],
                'show': True # mandatory
            },
            {
                'prefix': '',
                'label': suffix,
                'show': True # mandatory
            }
        ]

    elif modality == 'pet':
        # bidsname: sub-<participant_label>[_ses-<session_label>]_task-<task_label>[_acq-<label>][_rec-<label>][_run-<index>]_suffix
        bids_name_array = [
            {
                'prefix': 'sub-',
                'label': subid,
                'show': True # mandatory
            },
            {
                'prefix': 'ses-',
                'label': sesid,
                'show': show_label(sesid)
            },
            {
                'prefix': 'task-',
                'label': bids_values['task_label'],
                'show': True # mandatory
            },
            {
                'prefix': 'acq-',
                'label': bids_values['acq_label'],
                'show': show_label(bids_values['acq_label'])
            },
            {
                'prefix': 'rec-',
                'label': bids_values['rec_label'],
                'show': show_label(bids_values['rec_label'])
            },
            {
                'prefix': 'run-',
                'label': run,
                'show': show_label(run)
            },
            {
                'prefix': '',
                'label': suffix,
                'show': True # mandatory
            }
        ]

    return bids_name_array


def get_bids_name(bids_name_array):
    array = []
    for i, component in enumerate(bids_name_array):
        if component['show']:
            label = ""
            if component['label'] is not None:
                label = component['label']
            array.append(component['prefix'] + label)
    return '_'.join(array)


def obtain_initial_bidsmap_yaml(filename):
    """Obtain the initial BIDSmap as yaml string. """
    if not os.path.exists(filename):
        raise Exception("File not found: {}".format(filename))

    bidsmap_yaml = ""
    with open(filename) as fp:
        bidsmap_yaml = fp.read()
    return bidsmap_yaml


def obtain_initial_bidsmap_info(bidsmap_yaml):
    """Obtain the initial BIDSmap info. """
    contents = {}
    try:
        contents = yaml.safe_load(bidsmap_yaml)
    except yaml.YAMLError as exc:
        raise Exception('Error: {}'.format(exc))

    bidsmap_info = []
    contents_dicom = contents.get('DICOM', {})

    for modality in ["anat", "func", "dwi", "fmap", "beh", "pet", "extra_data"]:

        if modality == "extra_data":
            identified = False
        else:
            identified = True

        contents_dicom_modality = contents_dicom.get(modality, None)
        if contents_dicom_modality is not None:
            for item in contents_dicom.get(modality, None):
                if item is not None:

                    provenance = item.get('provenance', None)
                    if provenance is not None:
                        provenance_file = os.path.basename(provenance)
                        provenance_path = os.path.dirname(provenance)
                    else:
                        provenance_file = ""
                        provenance_path = ""

                    attributes = item.get('attributes', None)
                    if attributes is not None:
                        dicom_attributes = attributes
                    else:
                        dicom_attributes = {}

                    bids_attributes = item.get('bids', None)
                    if bids_attributes is not None:
                        bids_values = bids_attributes
                    else:
                        bids_values = {}

                    bidsmap_info.append({
                        "modality": modality,
                        "identified": identified,
                        "provenance": {
                            "path": provenance_path,
                            "filename": provenance_file
                        },
                        "dicom_attributes": dicom_attributes,
                        "bids_values": bids_values
                    })

    return bidsmap_info


def get_list_files(bidsmap_info):
    """Get the list of files from the BIDS info data structure. """
    list_dicom_files = []
    list_bids_names = []
    for item in bidsmap_info:
        dicom_file = item["provenance"]["filename"]
        if item['identified']:
            subid = '*'
            sesid = '*'
            modality = item["modality"]
            bids_values = item["bids_values"]
            run = '*'
            bids_name_array = bidsutils.get_bids_name_array(subid, sesid, modality, bids_values, run)
            bids_name = bidsutils.get_bids_name(bids_name_array)
        else:
            bids_name = ""
        list_dicom_files.append(dicom_file)
        list_bids_names.append(bids_name)
    return list_dicom_files, list_bids_names
