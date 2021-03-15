#!/usr/bin/python3

"""
Script for receiving data from the Internet traffic
of the Huawei E5186 router (and etc.) and sending MQTT data
for the Domoticz Smart Home system.
The script should be called every 5 minutes.
You have to use cron or daemonize it yourself.

No guarantees. Use at Your own risk. Even that it will work as intended.
Happiness for everybody, free, and no one will go away unsatisfied!
    (Arkady Strugatsky, Roadside Picnic)
MIT License 
https://github.com/pertsevpy
"""

import sys
import time
import datetime
import requests
from json import loads, dumps

# https://github.com/Salamek/huawei-lte-api
from huawei_lte_api.Client import Client
from huawei_lte_api.AuthorizedConnection import AuthorizedConnection
from huawei_lte_api.Connection import Connection

# https://pypi.org/project/paho-mqtt/
import paho.mqtt.publish as publish

# Wrapper for keyring library
import credentials_data

# Variable definitions
# These IDX values must match your Domoticz settings.
# ###################################################
# idx Domoticz device (custom) for LTE signal
# Don't change the key names idx_signal, they are used in huawei_lte_api
idx_signal = {
    'rsrq':    20,
    'rsrp':    21,
    'rssi':    22,
    'sinr':    23,
    'cell_id': 24
}

# idx Domoticz device for traffic statistics
idx_traffic = {
    'TotalDownload': 26,
    'TotalUpload':   27,
    'monthDL':       28,
    'monthUL':       29,
    'awgDL':         177,
    'awgUL':         178
}

# idx Domoticz variable for traffic statistics
idx_traffic_variable = {
    'TotalDownload': 7,
    'TotalUpload':   8
}

# date for resetting traffic statistics (int type)
reset_date = 5


class MQTT_client():
    """paho.mqtt wrapper for Domoticz MQTT"""
    def __init__(self, hostname="localhost", port=1883, username=None,
                 password=None, topic="domoticz/in"):
        self.__hostname = hostname
        self.__port = port
        self.__username = username
        self.__password = password
        self.__auth = {'username': self.__username,
                       'password': self.__password}
        self.__topic = topic

    def __pub(self, msg, retained=False):
        # print("Connecting {}".format(configMQTT.mqtt_cred["hostname"]))
        publish.single(self.__topic, payload=msg, retain=retained,
                       hostname=self.__hostname, port=self.__port,
                       keepalive=10, will=None, auth=self.__auth)

    def pub_MQTT(self, idx, val):
        send_data1 = {
            'idx': idx,
            'RSSI': 0,
            'nvalue': 0,
            'svalue': val}
        self.__pub(dumps(send_data1))  # dumps for JSON format: '' to ""
        time.sleep(0.1)

    def command_MQTT(self, command, idx, value):
        send_data1 = {
            'command': command,
            'idx': idx,
            'value': value}
        self.__pub(dumps(send_data1))
        time.sleep(0.1)
# ########### class MQTT_client ##############################################


class domoticz_client():
    def __init__(self, hostname="localhost", port=8080,
                 username=None, password=None):
        self.__domoticzserver = "http://" + hostname + ":" + str(port)
        self.__domoticzusername = username
        self.__domoticzpassword = password

    def domoticz_requests(self, path):
        r = requests.get(self.__domoticzserver + path,
                         auth=(self.__domoticzusername,
                               self.__domoticzpassword),
                         verify=True)
        if r.status_code == 200:
            j = loads(r.text)
        else:
            print('HTTP Error: ' + str(r.status_code))
            sys.exit(2)
        return j

    def parsingData(self, data):
        """Parsing JSON of Domoticz response to find the value
        of the requested parameter and
        the date of the last sensor update (not used now)."""
        dictdata = (data['result'])[0]
        if ('Data' in dictdata):
            sensor_data = dictdata['Data']
        elif ('Value' in dictdata):
            sensor_data = dictdata['Value']
        else:
            sensor_data = None
            # Space - Divider Values and Naming Units
        i2 = sensor_data.find(' ')
        if i2 > 0:
            sensor_data = sensor_data[0: i2]
        strLastDataUpdate = dictdata['LastUpdate']
        d = {'Data': sensor_data, 'LastUpdate': strLastDataUpdate}
        return d

    def getUserVariables(self, idx):
        """Get the Domoticz User Variables value for idx"""
        j = self.domoticz_requests(
            '/json.htm?type=command&param=getuservariable&idx='+str(idx))
        return self.parsingData(j)['Data']

    def getDevice(self, idx):
        """Get the Domoticz sensor value for idx"""
        j = self.domoticz_requests('/json.htm?type=devices&rid='+str(idx))
        return self.parsingData(j)['Data']
# ########### class domoticz_client ##########################################


class router_client():
    def __init__(self, hostname="192.168.8.1", username="admin",
                 password="admin"):
        self.__hostname = hostname
        self.__username = username
        self.__password = password

        connection = AuthorizedConnection('http://' +
                                          self.__username + ':' +
                                          self.__password + '@' +
                                          self.__hostname + '/')
        self.client = Client(connection)

        # print(client.device.information())  # Needs valid authorization,
        # will throw exception if invalid credentials are passed in URL

    def get_signal(self):
        data = self.client.device.signal()
        # Validation RSSI: str(Int) only!
        if data['rssi'] == ">=-51dBm":
            data['rssi'] = "-51"
        return data

    def get_stat(self):
        return self.client.monitoring.traffic_statistics()

    def reset_traf(self):
        # clear the traffic history on the router
        self.client.monitoring.set_clear_traffic()
# ########### class router_client ############################################


if __name__ == "__main__":
    # MAIN function
    # Initialization MQTT client
    mqtt_client = MQTT_client(
        credentials_data.get_cred("mqtt")["hostname"],
        credentials_data.get_cred("mqtt")["port"],
        credentials_data.get_cred("mqtt")["username"],
        credentials_data.get_cred("mqtt")["password"])

    # Initialization Domoticz client
    dz = domoticz_client(
        credentials_data.get_cred("domoticz")["hostname"],
        credentials_data.get_cred("domoticz")["port"],
        credentials_data.get_cred("domoticz")["username"],
        credentials_data.get_cred("domoticz")["password"])

    # Initialization Router client
    router = router_client(
        credentials_data.get_cred("router")["hostname"],
        credentials_data.get_cred("router")["username"],
        credentials_data.get_cred("router")["password"])

    # get LTE signal data from router
    signal_data = router.get_signal()

    # MQTT pub signal variable
    for key in idx_signal:
        mqtt_client.pub_MQTT(idx_signal[key], signal_data.get(key))
    del signal_data # We got everything we wanted from you

    # get traffic statistics
    traf_data = router.get_stat()

    # translate to Gigabytes
    traf_data['TotalDownload'] = str(
        round(float(traf_data['TotalDownload'])/1024/1024/1024, 3))
    traf_data['TotalUpload'] = str(
        round(float(traf_data['TotalUpload'])/1024/1024/1024, 3))

    mqtt_client.pub_MQTT(idx_traffic['TotalDownload'],
                         traf_data.get('TotalDownload'))
    mqtt_client.pub_MQTT(idx_traffic['TotalUpload'],
                         traf_data.get('TotalUpload'))

    # Huawei E5186 does not display the current speed.
    # We will consider averaged in 5 minutes
    # prevDL prevUL in UserVariables used as a temporary value.
    prevDL = float(dz.getUserVariables(idx_traffic_variable['TotalDownload']))
    prevUL = float(dz.getUserVariables(idx_traffic_variable['TotalUpload']))

    diffDL = float(traf_data['TotalDownload']) - float(prevDL)
    diffUL = float(traf_data['TotalUpload']) - float(prevUL)

    awgDL = round(diffDL * 1024 * 1024 / (60 * 5), 2)
    awgUL = round(diffUL * 1024 * 1024 / (60 * 5), 2)

    mqtt_client.pub_MQTT(idx_traffic['awgDL'], str(awgDL))
    mqtt_client.pub_MQTT(idx_traffic['awgUL'], str(awgUL))

    # In the monthly one will need to plus the difference
    monthDL = float(dz.getDevice(idx_traffic['monthDL'])) + diffDL
    monthUL = float(dz.getDevice(idx_traffic['monthUL'])) + diffUL

    mqtt_client.pub_MQTT(idx_traffic['monthDL'], str(monthDL))
    mqtt_client.pub_MQTT(idx_traffic['monthUL'], str(monthUL))

    mqtt_client.command_MQTT('setuservariable',
                             idx_traffic_variable['TotalDownload'],
                             traf_data['TotalDownload'])
    mqtt_client.command_MQTT('setuservariable',
                             idx_traffic_variable['TotalUpload'],
                             traf_data['TotalUpload'])

    # Reset traf on day or month
    today = datetime.datetime.today()
    timeHM = today.strftime("%H%M")
    timeD = today.strftime("%d")
    # Time Ot 00:00:00 to 00:04:59
    if float(timeHM) >= 0 and float(timeHM) < 5:
        # reset the day counters in Domoticz at the beginning of the new day
        mqtt_client.command_MQTT('setuservariable',
                                 idx_traffic_variable['TotalDownload'], '0')
        mqtt_client.command_MQTT('setuservariable',
                                 idx_traffic_variable['TotalUpload'], '0')
        mqtt_client.pub_MQTT(idx_traffic['TotalDownload'], '0')
        mqtt_client.pub_MQTT(idx_traffic['TotalUpload'], '0')
        # reset the monthly counters in Domoticz
        if float(timeD) == reset_date:
            mqtt_client.pub_MQTT(idx_traffic['TotalDownload'], '0')
            mqtt_client.pub_MQTT(idx_traffic['TotalUpload'], '0')
            mqtt_client.pub_MQTT(idx_traffic['monthDL'], '0')
            mqtt_client.pub_MQTT(idx_traffic['monthUL'], '0')
        # reset Traffic on the Router
        router.reset_traf()

    sys.exit()
