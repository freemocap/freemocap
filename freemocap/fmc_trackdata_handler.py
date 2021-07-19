import numpy as np
from pathlib import Path

FILE_SUFFIX = ".fmcData"

class FmcTracDataHandler(object):
    """
    # data structure:
    {
    "header":{
        "version": str(),
        "tags": list(),
        "author": str(),
        "export_date": datetime(),
        "camera_count": int(),
        "license": str(),
        "calibration_obj": class,
        },
    "content":{
        str(actor_name): {
            "sample_count": int(),
            "tracking_points": {
                str(tracking_point_name): {"parents": list(), samples: list()}
            }
        }
    },
    }
    """

    def __init__(self):
        self.data = {"header":{}, "content":{}}

    def has_actor(self, actor_name):
        return actor_name in self.data["content"]

    def has_trackingpoint_name(self, actor_name, point_name):
        return self.has_actor(actor_name) and point_name in self.data["content"][actor_name]["tracking_points"]

    def set_point_name_mapping(self, point_name_mapping):
        self.point_name_mapping = point_name_mapping

    def set_parent_mapping(self, parent_mapping):
        self.parent_mapping = parent_mapping

    def init_actor(self, actor_name):
        if not self.has_actor(actor_name):
            self.data["content"][actor_name] = {}
        else:
            raise Exception("Actor already exist in dataset. Please remove it before re-adding")

    def init_tracking_point_name(self, actor_name, point_name):
        if not self.has_actor(actor_name):
            self.init_actor(actor_name)
        if not "tracking_points" in self.data["content"][actor_name]:
            self.data["content"][actor_name]["tracking_points"] = {}
        self.data["content"][actor_name]["tracking_points"][point_name] = {}

    def set_actor_data(self, actor_name, data_label, data):
        if not self.has_actor(actor_name):
            self.init_actor(actor_name)
        self.data["content"][actor_name][data_label] = data


    def set_tracking_point_samples(self, actor_name, point_name, samples):
        if not self.has_trackingpoint_name(actor_name, point_name):
            self.init_tracking_point_name(actor_name, point_name)
        self.data["content"][actor_name]["tracking_points"][point_name]["samples"] = samples

    def set_tracking_point_parents(self, actor_name, point_name, parents):
        if not self.has_trackingpoint_name(actor_name, point_name):
            self.init_tracking_point_name(actor_name, point_name)
        self.data["content"][actor_name]["tracking_points"][point_name]["parents"] = parents

    def set_actor_sample_count(self, actor_name, sample_count):
        if self.has_actor(actor_name):
            self.data["content"][actor_name]["sample_count"] = sample_count
        else:
            raise ValueError("Object does not contain an actor called: %s" % actor_name)

    def set_header(key, value):
        self.data["header"][key] = value

    def set_version(self, version):
        self.set_header("version", version)

    def set_tags(self, tag_list):
        self.set_header("tags", tag_list)

    def set_author(self, author):
        self.set_header("author", author)

    def set_date(self, datetime_obj):
        self.set_header("export_date", datetime_obj)

    def set_camera_count(self, camera_count):
        self.set_header("camera_count", camera_count)

    def set_license(self, license_string):
        self.set_header("license", license_string)

    def set_calibration_obj(self, calibration_obj):
        self.set_header("calibration_obj", calibration_obj)

    def import_actor_raw_data(self, actor_label, raw_data):
        mapped_data = self.map_point_names(raw_data)
        parent_mapping = self.get_parent_mapping()

        sample_count = False
        for point_name in mapped_data:
            parent_list = []
            if point_name in parent_mapping:
                parent_list.append(parent_mapping[point_name])

            #print("Trackingpoint: %s" % point_name)
            samples = mapped_data[point_name]
            self.set_tracking_point_samples(actor_label, point_name, samples)
            self.set_tracking_point_parents(actor_label, point_name, parent_list)

            if sample_count == False:
                sample_count = len(samples)
            else:
                if not sample_count == len(samples):
                    raise NotImplementedError("Tracking points have different sample count. This is not supported yet")
                else:
                    sample_count = len(samples)
        self.set_actor_sample_count(actor_label, sample_count)


    def get_data(self):
        return self.data

    def get_actor_data(self, actor_label):
        if self.has_actor(actor_name):
            return self.data["content"][actor_label]
        else:
            raise ValueError("Object has no actor named %s" % actor_label)

    def list_actors(self):
        return list(self.data["content"].keys())

    def get_actor_tracking_points(self, actor_name):
        return self.data["content"][actor_name]["tracking_points"]

    def get_point_parents(self, actor_name, point_name):
        return self.data["content"][actor_name]["tracking_points"][point_name]["parents"]

    def get_actor_sample_count(self, actor_name):
        if self.has_actor(actor_name):
            return self.data["content"][actor_name]["sample_count"]
        else:
            raise ValueError("Object does not contain an actor called: %s" % actor_name)





    ### OpenPose mapping
    ################################################################################
    def map_point_names(self, data):
        """
        input data of format:
            [sample_idx][point_index] = (x,y,z)

        output format
            {point_name:
                [(x,y,z), (x,y,z),...]} # list of samples
        """
        point_names = self.get_point_name_mapping()

        # initiating data container for each point in point_names, added generated names for indices beyond length of point_names
        first_sample = data[0]
        if len(first_sample) > len(point_names): # Check if there is an equal amount of names points and indices in the data
            surplus_sample_points = len(first_sample) - len(point_names)
            for i in range(surplus_sample_points):
                point_names.append("generatedName%s" % str(i).zfill(3))

        # reordering data to be ["point_name"][sample_i][x,y,z]
        data_reform = {}
        for i, point_name in enumerate(point_names):
            data_reform[point_name] = data[:,i,:]

        return data_reform



    def get_parent_mapping(self):
        """
        Returns a dictionary that maps point names to their parent point
        """
        if not self.parent_mapping == False:
            return self.parent_mapping
        else:
            raise ValueError("No parent mapping is set. Use set_parent_mapping() to define an appropriate map")

    def get_point_name_mapping(self):
        """
        Returns a list of names corresponding to the data positions
        """
        if not self.point_name_mapping == False:
            return self.point_name_mapping
        else:
            raise ValueError("No point name mapping is set. Use set_point_name_mapping() to define an appropriate map")





def load_obj_from_file(file_path):
    # Loads file saved through this class
    f = Path(file_path)

    if f.is_file():
        if f.suffix.lower() == FILE_SUFFIX:
            print(f"Reading file from: {f.absolute()}")
            with open(file_path, "rb") as infile:
                data = pickle.load(infile)
            if not isinstance(data, FmcTracDataHandler):
                raise ValueError("Loaded data is not an instance of FmcTracDataHandler")
        else:
            raise ValueError("File has wrong extension. Should be '%s'" % FILE_SUFFIX)
    else:
        raise ValueError("File does not exist")

    return data




def save_obj_to_file(self, file_path, fmxDataObj, override=False):
    f = Path(file_path)
    f= f.with_suffix(FILE_SUFFIX)
    if f.exists() and override == False:
        raise NotImplementedError(f"File already exists, Skipping\nFilepath: {f.absolute()}")
    with open(f, 'wb') as handle:
        pickle.dump(fmxDataObj, handle, protocol=2)
        print(f"Saved file to: {f.absolute()}")
