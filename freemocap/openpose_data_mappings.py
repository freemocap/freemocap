# define point parents by name. Only points listed will have a parent. If a point is not listed, it will be without parents
# child_name : parent_name
parent_mapping = {
    'REye': 'Nose',
    'LKnee': 'LHip',
    'LWrist': 'LElbow',
    'LSmallToe': 'LBigToe',
    'RShoulder': 'Neck',
    'LBigToe': 'LAnkle',
    'RKnee': 'RHip',
    'LEar': 'LEye',
    'REar': 'REye',
    'RBigToe': 'RAnkle',
    'RAnkle': 'RKnee',
    'LElbow': 'LShoulder',
    'RElbow': 'RShoulder',
    'LAnkle': 'LKnee',
    'RHeel': 'RAnkle',
    'RWrist': 'RElbow',
    'RSmallToe': 'RBigToe',
    'RHip': 'MidHip',
    'Nose': 'Neck',
    'MidHip': 'Neck',
    'LShoulder': 'Neck',
    'LEye': 'Nose',
    'LHip': 'MidHip',
    'LHeel': 'LAnkle',
    'HandL15': 'HandL14',
    #'HandL13': 'HandL00',
    'HandL14': 'HandL13',
    'HandL20': 'HandL19',
    'RWrist': 'RElbow',
    'HandL12': 'HandL11',
    'HandL18': 'HandL17',
    #'HandL02': 'HandL01',
    'HandL03': 'HandL02',
    #'HandL17': 'HandL00',
    #'HandL01': 'HandL00',
    'HandL06': 'HandL05',
    'HandL07': 'HandL06',
    'HandL04': 'HandL03',
    #'HandL05': 'HandL00',
    'HandL11': 'HandL10',
    'HandL08': 'HandL07',
    #'HandL09': 'HandL00',
    'HandL19': 'HandL18',
    'HandL16': 'HandL15',
    'HandL10': 'HandL09',
    'HandR14': 'HandR13',
    'HandR08': 'HandR07',
    #'HandR09': 'HandR00',
    'HandR19': 'HandR18',
    'HandR18': 'HandR17',
    'HandR04': 'HandR03',
    #'HandR05': 'HandR00',
    'HandR06': 'HandR05',
    'HandR07': 'HandR06',
    #'HandR13': 'HandR00',
    #'HandR01': 'HandR00',
    #'HandR02': 'HandR01',
    'HandR03': 'HandR02',
    #'HandR17': 'HandR00',
    'HandR20': 'HandR19',
    'LWrist': 'LElbow',
    'HandR11': 'HandR10',
    'HandR12': 'HandR11',
    'HandR16': 'HandR15',
    'HandR10': 'HandR09',
    'HandR15': 'HandR14'
}


# point name corresponding to Open Pose list indices
# If the imported list is longer than the point_name_mapping, all residual points will be given a generic name
point_name_mapping = [
    "Nose", "Neck", "RShoulder", "RElbow", "RWrist", "LShoulder",               # limbs
    "LElbow", "LWrist", "MidHip", "RHip", "RKnee", "RAnkle", "LHip", "LKnee",   # limbs
    "LAnkle", "REye", "LEye", "REar", "LEar", "LBigToe", "LSmallToe", "LHeel",  # limbs
    "RBigToe", "RSmallToe", "RHeel",                                            # limbs
    "HandR00", "HandR01", "HandR02", "HandR03", "HandR04", "HandR05", "HandR06", "HandR07", "HandR08", "HandR09", "HandR10", "HandR11", "HandR12", "HandR13", "HandR14", "HandR15", "HandR16", "HandR17", "HandR18", "HandR19", "HandR20", # Right Hand
    "HandL00", "HandL01", "HandL02", "HandL03", "HandL04", "HandL05", "HandL06", "HandL07", "HandL08", "HandL09", "HandL10", "HandL11", "HandL12", "HandL13", "HandL14", "HandL15", "HandL16", "HandL17", "HandL18", "HandL19", "HandL20", # Left Hand
]
