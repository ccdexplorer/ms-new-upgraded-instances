import os

# import ast
from dotenv import load_dotenv

load_dotenv()

COIN_API_KEY = os.environ.get("COIN_API_KEY")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
DEBUG = False if os.environ.get("DEBUG", False) == "False" else True
MAX_BLOCKS_PER_RUN = int(os.environ.get("MAX_BLOCKS_PER_RUN", 40))
RUN_ON_NET = os.environ.get("RUN_ON_NET")
MQTT_USER = os.environ.get("MQTT_USER")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_SERVER = os.environ.get("MQTT_SERVER")
MQTT_QOS = int(os.environ.get("MQTT_QOS"))
