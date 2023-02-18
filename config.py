import sys
from typing import Dict

import yaml
import logging


def load_config(config_path) -> Dict:
    with open(config_path, 'r') as stream:
        try:
            data = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            logging.error(exc)
            sys.exit(1)
    return data
