from app import BBDCProcessor
import schedule
import time
from config import load_config

# load config
config = load_config("config_prod.yaml")

if __name__ == "__main__":
    try:
        bbdc = BBDCProcessor(config)
        bbdc.run()
    except Exception as e:
        bbdc.browser.quit()
        print(e)

