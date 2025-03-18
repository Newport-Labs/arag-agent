import os

import yaml
from yaml import SafeLoader


# Register the constructor specifically for SafeLoader
def include_constructor(loader, node):
    filename = loader.construct_scalar(node)
    # Get the directory of the current file
    base_dir = os.path.dirname(loader.name) if hasattr(loader, "name") else os.getcwd()
    # Join with the included file path
    full_path = os.path.join(base_dir, filename)
    with open(full_path, "r") as f:
        return yaml.safe_load(f)


# Add the constructor to SafeLoader specifically
yaml.add_constructor("!include", include_constructor, SafeLoader)


def load_yaml(filepath: str) -> dict:
    with open(filepath, "r") as file:
        prompts = yaml.safe_load(file)
    return prompts
