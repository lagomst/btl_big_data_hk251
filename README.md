### Installation
0. Install conda (see here: https://www.anaconda.com/docs/getting-started/miniconda/install)

1. Install requirements:

  ```bash
  conda create --name newsrag python=3.14
  conda activate newsrag
  pip install -r requirements.txt
  ```

### Run
Before running, set-up environment variable as so:

  ```.env
  DEFAULT_KNOWLEDGE ="neo4j" # your first knowledge base name
  
  # OPENAI
  OPENAI_API_KEY=sk-proj-<your key here>
  # LLM SECRET_KEY
  LLM_API_KEY = sk-proj-<your key here>
  LLM_API_BASE=
  LLM_API_VERSION=
  LLM_API_MODEL='gpt-4o-mini' # or any other model you wish to use
  LLM_API_MAX_TOKENS=4096
  LLM_API_TEMPERATURE=0.0
  
  VERBOSE=true # for debug
  
  # Other setting
  INSERT_FILE_TIMEOUT=1000
  STREAM_TIMEOUT=120
  ```

To start the server, run this command:

`fastapi run main.py --port 9999 --workers 1`

Then navigate to http://localhost:9999
