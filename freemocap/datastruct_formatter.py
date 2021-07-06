import pickle
import numpy as np
from pathlib import Path




class DataStructure(object):
    """
    Main class containing mmcap dataset

    Attributes:
        header: Dictionary with all header information
        content: List of Actor objects
    """
    def __init__(self):
        self.header = {
                "version": False, #str()
                "tags": False, #list(),
                "author": False, #str(),
                "export_date": False, #datetime(),
                "sample_rate": False, #float(),
                "camera_count": False, #int(),
                "license": False, #str(),
                "calibration_obj": False, #CalibrationObj(),
            }
        self.content = [] # list of Actor objects

    def set_version(self, version):
        self.header["version"] = version

    def set_tags(self, tag_list):
        self.header["tags"] = tag_list

    def set_author(self, author):
        self.header["author"] = author

    def set_date(self, datetime_obj):
        self.header["export_date"] = datetime_obj

    def set_camera_count(self, camera_count):
        self.header["camera_count"] = camera_count

    def set_license(self, license_string):
        self.header["license"] = license_string

    def set_calibration_obj(self, calibration_obj):
        self.header["calibration_obj"] = calibration_obj

    def add_actor(self, actor_obj):
        if isinstance(actor_obj, Actor):
            self.content.append(actor_obj)
        else:
            raise TypeError("actor_obj should be of type Actor")

    def get_header(self):
        return self.header

    def get_actors(self):
        return self.content

    def get_actor(self, actor_name):
        for actor in self.content:
            if actor.get_name() == actor_name:
                return actor
        raise ValueError(f"Actor %s not found in content {actor_name}")

    def list_actor_names(self):
        actor_list = []
        for actor in self.content:
            actor_list.append(actor.get_name())
        return actor_list

    def print_stats(self):
        print("\n### Header")
        header = self.get_header()
        for attr in header:
            print(attr, ":", header[attr])

        print("\n### Content")
        actor_name_list = self.list_actor_names()
        print("Contains %s actor(s): %s" %(len(actor_name_list), actor_name_list))

        for actor_name in actor_name_list:
            actor = self.get_actor(actor_name)

            act_type = actor.get_type()
            sample_rate = actor.get_sample_rate()
            sample_length = actor.get_length()
            point_names = actor.list_points()

            print(f"\nActor: '{actor_name}'\nsample rate: {sample_rate}\nsample length: {sample_length}\nnumber of points: {len(point_names)}")

    def get_as_dict(self):
        # WARNING: Overrides "content" attribute in place
        actors = self.get_actors()
        out_dict = vars(self)
        out_dict["content"] = []

        for actor in actors:
            out_dict["content"].append(vars(actor))
        return out_dict


class CalibrationObj(object):
    """
    Handling the calibration object which has yet to be defined
    """
    def __init__(self):
        pass


class Actor(object):
    """
    Class for handling data related to an individual actor as recorded through the mmcap system

    Attributes
        name: String identifier of actor, eg. name
        actor_type: type of actor, be it human or beast
        sample_rate: sample rate that the current tracking points have been recorded with
        sample_length: number of samples in each tracking point
        tracking_points: dictionary containing all tracking points, indexed by point name
    """
    def __init__(self, name, actor_type, sample_rate, sample_length):
        self.name = name
        self.actor_type = actor_type
        self.sample_rate = sample_rate
        self.sample_length = sample_length
        self.tracking_points = False

    def add_parent(self, child_pnt_name, parent_pnt_name):
        if self.tracking_points != False and child_pnt_name in self.tracking_points:
            self.tracking_points[child_pnt_name]["parents"].append(parent_pnt_name)

    def add_tracking_point(self, name, sample_rate, samples, parents_list):
        """
        input:
            name: string identifier of tracking point
            sample_rate: float defining sample rate that the data is meant to be using
            samples: list of tuples with 3 floats defining x,y,z at each sample
            parents_list: list of tracking_point Names that this point should draw lines to
        """
        if not self.tracking_points:
            self.tracking_points = {}

        if name in self.tracking_points:
            raise NotImplementedError("# Actor.add_tracking_point: Name %s already in tracking_points. Skipping" % name)

        if len(samples) != self.sample_length:
            raise NotImplementedError("# Actor.add_tracking_point: new tracking point sample length %s does not match Actor sample length %s" % (len(samples), self.sample_length))

        self.tracking_points[name] = {"samples": samples, "sample_rate": sample_rate, "parents":parents_list}

    def get_name(self):
        return self.name

    def get_type(self):
        return self.actor_type

    def get_sample_rate(self):
        return self.sample_rate

    def get_length(self):
        return self.sample_length

    def get_tracking_point_data_dict(self):
        return self.tracking_points

    def get_tracking_point_name_list(self):
        return list(self.tracking_points.keys())

    def get_point_parents(self, point_name):
        if self.__has_point(point_name):
            return self.tracking_points[point_name]["parents"]
        else:
            raise NotImplementedError("Actor.get_point_parents: No point named %s" % point_name)

    def get_point_sample_list(self, point_name):
        if self.__has_point(point_name):
            return self.tracking_points[point_name]["samples"]
        else:
            raise NotImplementedError("Actor.get_point_location_list: No point named %s" % point_name)

    def get_point_sample_rate(self, point_name):
        if self.__has_point(point_name):
            return self.tracking_points[point_name]["sample_rate"]
        else:
            raise NotImplementedError("Actor.get_point_location_list: No point named %s" % point_name)

    def list_points(self):
        return list(self.tracking_points.keys())


    def __has_point(self, pnt_name):
        return pnt_name in self.tracking_points









def make_actor_from_npy(npy_data, actor_name, actor_type, sample_rate):

    mapped_data = map_npy_sample_to_point_names(npy_data)
    parent_mapping = get_parent_mapping()

    point_names = list(mapped_data.keys())
    sample_length = len(mapped_data[point_names[0]]) # assuming length of first point sample count
    actor = Actor(actor_name, actor_type, sample_rate, sample_length)

    for point_name in mapped_data:
        parent_list = []
        try:
            parent_list.append(parent_mapping[point_name])
        except KeyError:
            pass
        actor.add_tracking_point(point_name, sample_rate, mapped_data[point_name], parent_list)

    return actor





def load_datastruct_from_file(file_path):
    # Loads file saved through this class
    f = Path(file_path)
    if f.is_file():
        print(f"Reading file from: {f.absolute()}")
        with open(file_path, "rb") as infile:
            datastruct = pickle.load(infile)
    else:
        raise ValueError("File does not exist")

    if not isinstance(datastruct, DataStructure):
        raise NotImplementedError("Loaded data is not an instance of DataStructure")

    return datastruct




def save_datastruct_to_file(file_path, datastruct, override=False):
    if isinstance(datastruct, DataStructure):
        suffix = ".mmcds"
    elif type(datastruct) == type(dict()):
        suffix = ".mmcdict"
    else:
        raise NotImplementedError("Input data is neither a dict nor of type DataStructure. This is not supported yet")

    f = Path(file_path)
    f= f.with_suffix(suffix)
    if f.exists() and override == False:
        raise NotImplementedError(f"File already exists, Skipping\nFilepath: {f.absolute()}")
    with open(f, 'wb') as handle:
        pickle.dump(datastruct, handle, protocol=2)
        print(f"Saved file to: {f.absolute()}")







### OpenPose mapping
################################################################################
def map_npy_sample_to_point_names(data):
    """
    input data of format:
        [sample_idx][point_index] = (x,y,z)

    output format
        {point_name:
            [(x,y,z), (x,y,z),...]} # list of samples
    """

    # making a complete point_names list
    limbs_arr = ["Nose", "Neck", "RShoulder", "RElbow", "RWrist", "LShoulder",
    "LElbow", "LWrist", "MidHip", "RHip", "RKnee", "RAnkle", "LHip", "LKnee",
    "LAnkle", "REye", "LEye", "REar", "LEar", "LBigToe", "LSmallToe", "LHeel",
    "RBigToe", "RSmallToe", "RHeel"]
    handr_arr = [ "HandR00", "HandR01", "HandR02", "HandR03", "HandR04", "HandR05", "HandR06", "HandR07", "HandR08", "HandR09", "HandR10", "HandR11", "HandR12", "HandR13", "HandR14", "HandR15", "HandR16", "HandR17", "HandR18", "HandR19", "HandR20"]
    handl_arr = [ "HandL00", "HandL01", "HandL02", "HandL03", "HandL04", "HandL05", "HandL06", "HandL07", "HandL08", "HandL09", "HandL10", "HandL11", "HandL12", "HandL13", "HandL14", "HandL15", "HandL16", "HandL17", "HandL18", "HandL19", "HandL20"]

    point_names = limbs_arr + handr_arr + handl_arr



    # initiating data container for each point in point_names, added generated names for indices beyond length of point_names
    first_sample = data[0]
    if len(first_sample) > len(point_names): # Check if there is an equal amount of names points and indices in the data
        surplus_sample_points = len(first_sample) - len(point_names)
        for i in range(surplus_sample_points):
            point_names.append("generatedName%s" % str(i).zfill(3))

    #initiate dictionary container with point_names as keys
    data_reform = {}
    for point_name in point_names:
        data_reform[point_name] = []

    # add data to data container
    for sample in data:
        for i in range(len(sample)):
            data_reform[point_names[i]].append(sample[i])

    # convert coordinates to numpy arrays
    for point_name in data_reform:
        data_reform[point_name] = np.array(data_reform[point_name])

    return data_reform





def get_parent_mapping():
    """
    Returns a dictionary that maps point names to their parent point
    """
    # making a dictionary of the shape: {point1: parent, point2: parent}
    parent_mapping_body = {'REye': 'Nose', 'LKnee': 'LHip', 'LWrist': 'LElbow', 'LSmallToe': 'LBigToe', 'RShoulder': 'Neck', 'LBigToe': 'LAnkle', 'RKnee': 'RHip', 'LEar': 'LEye', 'REar': 'REye', 'RBigToe': 'RAnkle', 'RAnkle': 'RKnee', 'LElbow': 'LShoulder', 'RElbow': 'RShoulder', 'LAnkle': 'LKnee', 'RHeel': 'RAnkle', 'RWrist': 'RElbow', 'RSmallToe': 'RBigToe', 'RHip': 'MidHip', 'Nose': 'Neck', 'MidHip': 'Neck', 'LShoulder': 'Neck', 'LEye': 'Nose', 'LHip': 'MidHip', 'LHeel': 'LAnkle'}
    parent_mapping_lhand = {'HandL15': 'HandL14', 'HandL13': 'HandL00', 'HandL14': 'HandL13', 'HandL20': 'HandL19', 'RWrist': 'HandL00', 'HandL12': 'HandL11', 'HandL18': 'HandL17', 'HandL02': 'HandL01', 'HandL03': 'HandL02', 'HandL17': 'HandL00', 'HandL01': 'HandL00', 'HandL06': 'HandL05', 'HandL07': 'HandL06', 'HandL04': 'HandL03', 'HandL05': 'HandL00', 'HandL11': 'HandL10', 'HandL08': 'HandL07', 'HandL09': 'HandL00', 'HandL19': 'HandL18', 'HandL16': 'HandL15', 'HandL10': 'HandL09'}
    parent_mapping_rhand = {'HandR14': 'HandR13', 'HandR08': 'HandR07', 'HandR09': 'HandR00', 'HandR19': 'HandR18', 'HandR18': 'HandR17', 'HandR04': 'HandR03', 'HandR05': 'HandR00', 'HandR06': 'HandR05', 'HandR07': 'HandR06', 'HandR13': 'HandR00', 'HandR01': 'HandR00', 'HandR02': 'HandR01', 'HandR03': 'HandR02', 'HandR17': 'HandR00', 'HandR20': 'HandR19', 'LWrist': 'HandR00', 'HandR11': 'HandR10', 'HandR12': 'HandR11', 'HandR16': 'HandR15', 'HandR10': 'HandR09', 'HandR15': 'HandR14'}

    dict_list = [parent_mapping_body, parent_mapping_lhand, parent_mapping_rhand]
    parent_mapping = {}
    for d in dict_list:
        for k in d:
            parent_mapping[k]=d[k]

    return parent_mapping
