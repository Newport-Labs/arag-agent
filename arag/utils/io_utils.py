import os

import pkg_resources
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
    # Check if filepath is absolute
    if os.path.isabs(filepath):
        yaml_path = filepath
    else:
        # Try to get the filepath as a package resource
        try:
            yaml_path = pkg_resources.resource_filename("arag", filepath)
        except (ImportError, pkg_resources.DistributionNotFound):
            # Fall back to relative path
            yaml_path = filepath
    
    with open(yaml_path, "r") as file:
        prompts = yaml.safe_load(file)
    return prompts
