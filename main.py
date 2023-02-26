import logging
import sys

from app import BBDCProcessor
from config import load_config


def main():
    config_path = "config.yaml"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    logging.info(f"using config file: {config_path}")

    try:
        config = load_config(config_path)
        bbdc = BBDCProcessor(config)
        bbdc.run()
    except Exception as e:
        bbdc.browser.quit()
        print(e)


if __name__ == "__main__":
    main()



