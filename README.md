## FTPSuck

This program monitors FTP servers (devices) and take actions when a new file is detected. The currently supported actions are download and mqtt messaging.

Checkout the project, either edit ```config/default.yml``` or create a ```config/local.yml``` with the properties you need to override. Then run ```main.py```.

Please use, clone and improve.

## Installation

### clone the FTPSuck repo
```shell script
git clone https://www.github.com/dotvav/ftpsuck.git
cd ftpsuck
python3 -m venv venv
. venv/bin/activate
pip3 install -r requirements.txt
```

### Change the configuration
You can either update the ```config/default.yml``` file or create a new file named ```config/local.yml```. The keys that are present in the local config will override the ones in the default config. If a key is absent from local config, FTPSuck will fallback to the value of the default config. I recommend keeping the default config as is and make all the changes in the local config file so that you don't lose them when the default file gets updated from git.

| Property           | Usage                                                           | Note                                                                                                                            |
|--------------------|-----------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| **`devices`**      | a list of devices, aka ftp servers, to monitor                  | You **must** set this. See the model below.                                                                                     |
| `mqtt_host`        | the host name or ip address of the MQTT broker (if used)        | Only case you are defining MQTT actions. Use `localhost` or `127.0.0.1` if the MQTT broker runs on the same machine as FTPSuck. |
| `mqtt_port`        | the temperature measurement unit                                | `°C` by default.                                                                                                                |
| `mqtt_client_name` | the name that FTPSuck will us on MQTT                           | You should probably not touch this.                                                                                             |
| `mqtt_username`    | the MQTT broker username                                        | This is needed only if the MQTT broker requires an authenticated connection.                                                    |
| `mqtt_password`    | the MQTT broker password                                        | This is needed only if the MQTT broker requires an authenticated connection.                                                    |
| `interval`         | number of seconds to wait after a poll and before polling again | `10` by default                                                                                                                 |
| `logging_level`    | pyhton log level                                                | `INFO by default`                                                                                                               |

Devices are defined as follows:

| Device property | Usage                                         | Note                                        |
|-----------------|-----------------------------------------------|---------------------------------------------|
| `name`          | the name of this device (in logs or messages) | This is used in logs and MQTT messages      |
| `hostname`      | the host name or ip address of the FTP server | `127.1` by default                          |
| `port`          | the port of the FTP server                    | `21` by default                             |
| `user`          | FTP username                                  | `root` by default                           |
| `password`      | FTP password                                  | Unset by default                            |
| `path`          | the remote path on the FTP server             | Unset by default                            |
| `patterns`      | a list of patterns with actions               | You **must** set this. See the model below. |

Patterns define what filenames trigger an action, and what are the actions:

| Pattern property | Usage               | Note                                                                                        |
|------------------|---------------------|---------------------------------------------------------------------------------------------|
| `file_pattern`   | a regular exception | When a file is detected and its name matches this regexp, the actions are executed in order |
| `actions`        | a list of actions   | You **must** set this. See the model below.                                                 |

There are 3 types of actions:

| Action property     | Usage                              | Note                                                                                                                                     |
|---------------------|------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `action`            | `download`, `mqtt` or `wait`       | `download` is used to download the file from the FTP server into the local filesystem, `mqtt` is used to send a message on an MQTT topic |
| `download_path`     | where to download the file         | Used on `download` actions. `target` by default. **Variables can be used**.                                                              |
| `download_filename` | the name of the downloaded file    | Used on `download` actions. `{filename}` by default. **Variables can be used**.                                                          |
| `topic`             | which MQTT topic to send a message | Used on `mqtt` actions. **Variables can be used**.                                                                                       |
| `payload`           | what payload to put in a message   | Used on `mqtt` actions. `{filename}` by default. **Variables can be used**.                                                              |
| `duration`          | how many seconds to wait           | Used on `wait` actions. `1` by default                                                                                                   |


Where indicated, variables can be used in configuration properties. Use the `{variable_name}` syntax. The following variables are available:

| variable name | Value         |
|---------------|---------------|
| `{filename}`  | The file name |

### Start FTPSuck manually
```shell script
venv/bin/python3 main.py
```

### Start FTPSuck as a systemd service
Create the following ```/etc/systemd/system/ftpsuck.service``` file (change the paths as required):

```
[Unit]
Description=FTPSuck
Documentation=https://github.com/dotvav/ftpsuck
After=network.target

[Service]
Type=simple
User=homeassistant
WorkingDirectory=/home/homeassistant/ftpsuck
ExecStart=/home/homeassistant/ftpsuck/venv/bin/python3 /home/homeassistant/ftpsuck/main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
You may want to start this after the MQTT broker or HA has started: add the appropriate ```After=``` statement.

Run the following to enable and run the service, and see what its status is:
```shell script
sudo systemctl enable ftpsuck.service
sudo systemctl start ftpsuck.service
sudo systemctl status ftpsuck.service
```

## Pull the latest version from Github
Get the latest source
```shell script
cd ftpsuck
git pull origin master
```
Then restart the systemd service (if you created one):
```shell script
sudo systemctl status ftpsuck.service
```

## Dependencies
- paho-mqtt
- pyyaml

## Example of configuration

I have an IP camera that exposes an FTP server. It records `.avi` files in the path `/mnt/sdcard/RecFiles`. Upon motion
detection, the camera starts recording in a file named `recording_0.avi` for about a minute. When the recording is
finished, it renames the file into something like `Rec<auto_incr>_<timestamp>_A_1.avi`.

This configuration is polling the FTP server every 5 seconds is reacting to 2 file patterns:
* Any file which name matches the regexp `^recording.*\.avi$` will trigger  the publishing of `1` in an MQTT topic named 
`ftp/cam0/file`. This is telling me that motion was detected.
* Any file which name matches the regexp `^Rec.*\.avi$` (for example `Rec22_20230610153302_A_1.avi`) will triggert
  * a download of the file into the `target`
  * the publishing of the name of the file in an MQTT topic named `ftp/cam0/file`

```yaml
mqtt_host: 192.168.1.2
interval: 5
logging_level: INFO

devices:
  - name: cam0
    hostname: 192.168.1.55
    port: 21
    user: root
    password: ''
    path: /mnt/sdcard/RecFiles
    patterns:
      - file_pattern: ^Rec.*\.avi$
        actions:
          - action: download
            download_path: target
            download_filename: "{filename}"
          - action: mqtt
            topic: ftp/cam0/file
            payload: "{filename}"
      - file_pattern: ^recording.*\.avi$
        actions:
          - action: mqtt
            topic: ftp/cam0/motion
            payload: "1"
```