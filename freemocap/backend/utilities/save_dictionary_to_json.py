import json
import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def save_dictionary_to_json(save_path: Union[Path, str], dictionary: dict, file_name: str):
    if file_name.split(".")[-1] != "json":
        file_name = f"{file_name}.json"

    json_file_path = Path(save_path) / file_name
    json_file_path.write_text(json.dumps(dictionary, indent=4))

    logger.info(f"Saved dictionary {file_name} as json  at: {json_file_path}")
