
from freemocap import fmc_trackdata_handler as df
from freemocap import openpose_data_mappings as data_mapping

### Make empty data structure
data_handler = df.FmcTracDataHandler()

### Set mapping
data_handler.set_parent_mapping(data_mapping.parent_mapping)
data_handler.set_point_name_mapping(data_mapping.point_name_mapping)

### Load openpose npy data into variable
import numpy as np
datafile_path = r"C:\Users\Rontc\Documents\GitHub\freemocap\FreeMocap_Data\sesh_21-07-29_104227\DataArrays\openPoseSkel_3d.npy"
data = np.load(datafile_path)

### Import data into data handler as an actor.
# This step can be repeated for multiple datasets, adding each as an individual actor
actor_name = "tester"
data_handler.import_actor_raw_data(actor_name, data)

### Saving data handler object to file
#file_path = "/absolute/path/to/file/filename" # Suffix is being set to FILE_SUFFIX automatically
save_file_path = datafile_path
df.save_obj_to_file(save_file_path, data_handler, override=False)

### Loading data handler from file

load_file_path = r"C:\Users\Rontc\Documents\GitHub\freemocap\FreeMocap_Data\sesh_21-07-29_104227\DataArrays\openPoseSkel_3d.fmcData"
data_h = df.load_obj_from_file(load_file_path)

