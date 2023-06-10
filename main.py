import logging
import os
import re
from ftplib import FTP
from time import sleep

import paho.mqtt.client as mqtt
import yaml


class Context:
    def __init__(self):
        self.mqtt_client = None
        self.devices = []
        self.config = self.read_config()

    def read_config(self):
        with open("config/default.yml", 'r', encoding="utf-8") as yml_file:
            raw_default_config = yaml.safe_load(yml_file)
        try:
            with open("config/local.yml", 'r', encoding="utf-8") as yml_file:
                raw_local_config = yaml.safe_load(yml_file)
                raw_default_config.update(raw_local_config)
        except IOError:
            logging.info("No local config file found")
        return Config(raw_default_config, self.devices)


class Config:
    interval = 10
    logging_level = "WARNING"
    mqtt_port = 1883

    def __init__(self, raw, devices):
        self.interval = raw.get("interval", self.interval)
        self.logging_level = raw.get("logging_level", self.logging_level)
        self.mqtt_host = raw.get("mqtt_host")
        self.mqtt_port = raw.get("mqtt_port", self.mqtt_port)
        self.mqtt_client_name = raw.get("mqtt_client_name")
        self.mqtt_username = raw.get("mqtt_username")
        self.mqtt_password = raw.get("mqtt_password")

        logging.basicConfig(level=self.logging_level, format="%(asctime)-15s %(levelname)-8s %(message)s")

        for entry in raw.get("devices", []):
            devices.append(Device(entry))


class Pattern:
    def __init__(self, device, raw):
        self.device = device
        self.file_pattern = raw.get("file_pattern")
        self.regexp = re.compile(self.file_pattern)
        self.actions = []
        for raw_action in raw.get("actions"):
            action = raw_action.get("action")
            cls = actions.get(action)
            if cls:
                self.actions.append(cls(self, raw_action))
            else:
                logging.warning("Ignoring unknown action %s", action)

    def process(self, filename):
        if self.regexp.match(filename):
            for action in self.actions:
                action.process(filename)


class Action:
    def __init__(self, pattern, raw):
        self.pattern = pattern
        self.action = raw.get("action")

    def process(self, filename):
        return


class DownloadAction(Action):
    download_filename = "{filename}"

    def __init__(self, pattern, raw):
        super().__init__(pattern, raw)
        self.download_path = raw.get("download_path")
        self.download_filename = raw.get("download_filename", self.download_filename)

    def process(self, filename):
        logging.info("Download action for device '%s' file '%s'", self.pattern.device.name, filename)
        with open(os.path.join(self.download_path.format(filename=filename), self.download_filename.format(filename=filename)), 'wb') as handle:
            self.pattern.device.ftp.retrbinary(f"RETR {filename}", handle.write)


class MqttAction(Action):
    payload = "{filename}"

    def __init__(self, pattern, raw):
        super().__init__(pattern, raw)
        self.topic = raw.get("topic")
        self.payload = raw.get("payload", self.payload)

    def connect(self):
        context.mqtt_client = mqtt.Client(config.mqtt_client_name)
        if context.config.mqtt_username is not None:
            context.mqtt_client.username_pw_set(context.config.mqtt_username, context.config.mqtt_password)
        context.mqtt_client.connect(context.config.mqtt_host, context.config.mqtt_port)
        context.mqtt_client.loop_start()

    def process(self, filename):
        logging.info("MQTT action for device '%s' file '%s'", self.pattern.device.name, filename)
        if not context.mqtt_client:
            self.connect()
        context.mqtt_client.publish(self.topic.format(filename=filename), self.payload.format(filename=filename), retain=False)


class Device:
    hostname = "127.1"
    port = 21
    password = ""
    path = "/mnt/sdcard/RecFiles"
    file_pattern = "^Rec.*\\.avi$"

    def __init__(self, raw):
        self.patterns = []
        self.old_files = []
        self.name = raw.get("name")
        self.hostname = raw.get("hostname", self.hostname)
        self.port = raw.get("port", self.port)
        self.user = raw.get("user")
        self.password = raw.get("password", self.password)
        self.path = raw.get("path", self.path)

        for raw_pattern in raw.get("patterns"):
            self.patterns.append(Pattern(self, raw_pattern))

        self.connect()

    def connect(self):
        # FTP.__init__() doesn't like a 'port' argument
        self.ftp = FTP(host=self.hostname, user=self.user, passwd=self.password)
        self.ftp.cwd(self.path)
        logging.debug("Device '%s' connected to host '%s'", self.name, self.hostname)
        self.old_files = self.ftp.nlst()
        logging.debug("Device '%s' has %i files", self.name, len(self.old_files))

    def list_new_files(self):
        all_files = self.ftp.nlst()
        logging.debug("Device '%s' has %i files", self.name, len(all_files))
        new_files = []
        for filename in all_files:
            if filename not in self.old_files:
                new_files.append(filename)
                logging.info("New filename found: %s", filename)
        self.old_files = all_files
        return new_files

    def process(self, config):
        for filename in self.list_new_files():
            for pattern in self.patterns:
                pattern.process(filename)


def monitor():
    while True:
        for device in context.devices:
            device.process(context.config)
        sleep(context.config.interval)


actions = {
    "download": DownloadAction,
    "mqtt": MqttAction
}

context = Context()
monitor()

