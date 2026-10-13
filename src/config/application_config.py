from pathlib import Path
from yaml import safe_load
import logging

logger = logging.getLogger(__file__)

app_config = {}
BASE_PATH = str(Path(__file__).resolve().parent.parent)

def load_config():
    global app_config
    try:
        with open(
            BASE_PATH + "/resources/application-config.yaml", encoding="utf-8"
        ) as fh:
            app_config = safe_load(fh)
            print(app_config)
    except FileNotFoundError as fe:
        logger.error(
            "Exception while loading application configuration", fe, exc_info=True
        )

def get_config(key: str):
    return app_config[key]

if __name__ == "__main__":
    load_config()
    print(get_config("ELASTIC_URL"))
