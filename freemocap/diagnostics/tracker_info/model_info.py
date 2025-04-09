from pathlib import Path
from typing import Union, Dict, List, Optional
import yaml
from dataclasses import dataclass
import itertools

@dataclass
class AspectInfo:
    tracked_points_names: List[str]
    num_tracked_points: int
    virtual_marker_definitions: Optional[Dict[str, Dict[str, List[Union[float, str]]]]] = None
    segment_connections: Optional[Dict[str, Dict[str, str]]] = None
    center_of_mass_definitions: Optional[Dict[str, Dict[str, float]]] = None
    joint_hierarchy: Optional[Dict[str, List[str]]] = None

class ModelInfo:
    """
    A class that loads and parses motion capture model configuration from YAML files.
    Attributes:
       name (str): Name identifier for this model
       tracker_name (str): Type/name of the motion capture tracker
       aspects (Dict[str, AspectInfo]): Information about each aspect (body, face, hands, etc.)
       tracked_point_names (List[str]): Combined list of all tracked point names
       num_tracked_points (int): Total number of tracked points across all aspects
       aspect_order_and_slices (Dict[str, slice]): How to slice numpy arrays by aspect

    """
    def __init__(self, config_path: Union[str, Path]):
        config_path = Path(config_path)
        config = self._load_config(config_path)
        self.name:str = config['name']
        self.tracker_name:str = config['tracker_name']
        self.aspects: Dict[str, AspectInfo] = self._parse_aspects(config=config)
        self.tracked_point_names: List[str] = [tp for aspect in self.aspects.values() for tp in aspect.tracked_points_names]
        self.num_tracked_points:str = sum([aspect.num_tracked_points for aspect in self.aspects.values()])
        self.aspect_order_and_slices: Dict[str, slice] = self._get_aspect_order_and_slices(config)

    def _load_config(self, config_path:Path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    
    def _parse_aspects(self, config):
        aspects = {}
        for aspect_name, aspect_info in config['aspects'].items():
            # Handle different ways of naming tracked points (names provided in a list vs. generating identifiers)
            if aspect_info['tracked_points']['type'] == 'list':
                tracked_points_names = aspect_info['tracked_points']['names']
            elif aspect_info['tracked_points']['type'] == 'generated':
                naming_convention = aspect_info['tracked_points']['names']['convention']
                count = aspect_info['tracked_points']['names']['count']
                tracked_points_names = [naming_convention.format(i) for i in range(count)]
            
            aspects[aspect_name] = AspectInfo(
                tracked_points_names = tracked_points_names,
                num_tracked_points= len(tracked_points_names),
                virtual_marker_definitions = aspect_info.get('virtual_marker_definitions'),
                segment_connections = aspect_info.get('segment_connections'),
                center_of_mass_definitions = aspect_info.get('center_of_mass_definitions'),
                joint_hierarchy = aspect_info.get('joint_hierarchy')
            )
        
        return aspects
    
    def _get_aspect_order_and_slices(self, config):
        """
        Get the proper order of every aspect included in the model info and how to slice it from a numpy array and put it into a dict
        """
        aspect_order_and_slices = {}
        current_index = 0
        for aspect in config['order']:
            aspect_order_and_slices[aspect] = slice(current_index, current_index + self.aspects[aspect].num_tracked_points)
            current_index = current_index + self.aspects[aspect].num_tracked_points
        return aspect_order_and_slices




class MediapipeModelInfo(ModelInfo):
    def __init__(self):
        super().__init__(config_path = Path(__file__).parent/'mediapipe_info.yaml')




f = 2
