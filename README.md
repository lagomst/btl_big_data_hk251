### Installation
0. Install conda (see here: https://www.anaconda.com/docs/getting-started/miniconda/install)

1. Install requirements:

`conda create --name newsrag python=3.14`

`conda activate newsrag`

`pip install -r requirements.txt`

### Run
Run this command:

`fastapi run main.py --port 9999 --workers 1`
