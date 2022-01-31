from yaml import safe_load
from pathlib import Path
import pathlib
import sys
from os import getenv

def retrieve_config():
    with open('config.yml') as file:
        config = safe_load(file)

    return config

#returns directory where Artifice stores data
def get_datadir():

    home = pathlib.Path.home()

    if sys.platform.startswith("win"):
        os_path = getenv("LOCALAPPDATA")
    elif sys.platform.startswith("darwin"):
        os_path = "~/Library/Application Support"
    else:
        # linux
        os_path = getenv("XDG_DATA_HOME", "~/.local/share")

    path = Path(os_path) / "ARTIFICE"

    return path.expanduser() #/ file_name



config = retrieve_config()

RAMPART_PORT_1 = config['RAMPART_PORT_1']
RAMPART_PORT_2 = config['RAMPART_PORT_2']
ARCHIVED_RUNS = config['ARCHIVED_RUNS']
RUNS_DIR = str(get_datadir() / 'runs')
DOCKER_IMAGE = config['DOCKER_IMAGE']
FONT = config['FONT']
#BACKGROUND_COLOR = "#072429"

if __name__ == '__main__':
    #home = pathlib.Path.home()
    print(RUNS_DIR)