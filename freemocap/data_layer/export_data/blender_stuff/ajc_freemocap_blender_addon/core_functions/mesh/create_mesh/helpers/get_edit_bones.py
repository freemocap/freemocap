def get_edit_bones(rig):
    edit_bones = {
    "spine" : rig.data.edit_bones['spine'],
    "spine_001" : rig.data.edit_bones['spine.001'],
    "shoulder_R" : rig.data.edit_bones['shoulder.R'],
    "shoulder_L" : rig.data.edit_bones['shoulder.L'],
    "neck" : rig.data.edit_bones['neck'],
    "hand_R" : rig.data.edit_bones['hand.R'],
    "hand_L" : rig.data.edit_bones['hand.L'],
    "thigh_R" : rig.data.edit_bones['thigh.R'],
    "thigh_L" : rig.data.edit_bones['thigh.L'],
    "shin_R" : rig.data.edit_bones['shin.R'],
    "shin_L" : rig.data.edit_bones['shin.L'],
    "foot_R" : rig.data.edit_bones['foot.R'],
    "foot_L" : rig.data.edit_bones['foot.L'],
    }
    return edit_bones
