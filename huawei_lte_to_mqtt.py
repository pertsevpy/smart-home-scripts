#!/usr/bin/python3

"""
Script for receiving data from the Internet traffic
of the Huawei E5186 router (and etc.) and sending MQTT data
for the Domoticz Smart Home system
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

# Wrapper for Python keyring library 
import credentials_data


class MQTT_client():
    def __init__(self, hostname="localhost", port=1883, username=None,
                 password=None, topic="domoticz/in"):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.auth = {'username': self.username, 'password': self.password}
        self.topic = topic

    def pub(self, msg, retained=False):
        # print("Connecting {}".format(configMQTT.mqtt_cred["hostname"]))
        publish.single(self.topic, payload=msg, retain=retained,
                       hostname=self.hostname, port=self.port,
                       keepalive=10, will=None, auth=self.auth)

    def pub_MQTT(self, idx, val):
        send_data1 = {
            'idx': idx,
            'RSSI': 0,
            'nvalue': 0,
            'svalue': val}
        self.pub(dumps(send_data1))  # dumps for JSON format: '' to ""
        time.sleep(0.1)

    def command_MQTT(self, command, idx, value):
        send_data1 = {
            'command': command,
            'idx': idx,
            'value': value}
        self.pub(dumps(send_data1))
        time.sleep(0.1)
# ########### class MQTT_client ##############################################


class domoticz_client():
    def __init__(self, hostname="localhost", username=None, password=None):
        self.domoticzserver = hostname
        self.domoticzusername = username
        self.domoticzpassword = password

    def domoticz_requests(self, path):
        r = requests.get(self.domoticzserver + path,
                         auth=(self.domoticzusername, self.domoticzpassword),
                         verify=True)
        if r.status_code == 200:
            j = loads(r.text)
        else:
            print('HTTP Error: ' + str(r.status_code))
            sys.exit(2)
        return j

    def parsingData(self, data):
        dictdata = (data['result'])[0]
        if ('Data' in dictdata):
            sensor_data = dictdata['Data']
        elif ('Value' in dictdata):
            sensor_data = dictdata['Value']
        else:
            sensor_data = None
            # пробел - разделитель значения и именования единиц
        i2 = sensor_data.find(' ')
        if i2 > 0:
            sensor_data = sensor_data[0: i2]
        strLastDataUpdate = dictdata['LastUpdate']
        d = {'Data': sensor_data, 'LastUpdate': strLastDataUpdate}
        return d

    def getUserVariables(self, idx):
        j = self.domoticz_requests(
            '/json.htm?type=command&param=getuservariable&idx='+str(idx))
        return self.parsingData(j)

    def getDevice(self, idx):
        j = self.domoticz_requests('/json.htm?type=devices&rid='+str(idx))
        return self.parsingData(j)
# ########### class domoticz_client ##########################################

class router_client():
    def __init__(self, hostname="192.168.8.1", username="admin",
                                               password="admin"):
        self.hostname = hostname
        self.username = username
        self.password = password

        connection = AuthorizedConnection('http://' +
                        username + ':' + password + '@' + hostname + '/')
        self.client = Client(connection)

        # print(client.device.information())  # Needs valid authorization,
        # will throw exception if invalid credentials are passed in URL

    def get_signal(self):
        return self.client.device.signal()
        
    def get_stat(self):
        return self.client.monitoring.traffic_statistics()

# ########### class router_client ##########################################

# Initialization MQTT client
# нужно сделать красиво
mqtt_client = MQTT_client(
                credentials_data.get_cred("mqtt")["hostname"],
                credentials_data.get_cred("mqtt")["port"],
                credentials_data.get_cred("mqtt")["username"],
                credentials_data.get_cred("mqtt")["password"])

# Initialization Domoticz client
dz = domoticz_client(
                "http://" +
                credentials_data.get_cred("domoticz")["hostname"] + ":" + 
            str(credentials_data.get_cred("domoticz")["port"]),
                credentials_data.get_cred("domoticz")["username"],
                credentials_data.get_cred("domoticz")["password"])

  # Initialization Router client              
router = router_client(
                credentials_data.get_cred("router")["hostname"],
                credentials_data.get_cred("router")["username"],
                credentials_data.get_cred("router")["password"])

data = router.get_signal()

# Публикуем уровень сигнала
if data['rssi'] == ">=-51dBm":
    data['rssi'] = "-51"

mqtt_client.pub_MQTT(20, data.get('rsrq'))
mqtt_client.pub_MQTT(21, data.get('rsrp'))
mqtt_client.pub_MQTT(22, data.get('rssi'))
mqtt_client.pub_MQTT(23, data.get('sinr'))
mqtt_client.pub_MQTT(24, data.get('cell_id'))

# получаем статистику трафика
data = router.get_stat()

# переводим в гигабайты
data['TotalDownload'] = str(
    round(float(data['TotalDownload'])/1024/1024/1024, 3))
data['TotalUpload'] = str(round(float(data['TotalUpload'])/1024/1024/1024, 3))


mqtt_client.pub_MQTT(26, data.get('TotalDownload'))
mqtt_client.pub_MQTT(27, data.get('TotalUpload'))

prevDL = float(dz.getUserVariables(7)['Data'])  # Download_prev
prevUL = float(dz.getUserVariables(8)['Data'])

diffDL = float(data['TotalDownload']) - float(prevDL)
diffUL = float(data['TotalUpload']) - float(prevUL)

awgDL = round(diffDL * 1024 * 1024 / (60 * 5), 2)
awgUL = round(diffUL * 1024 * 1024 / (60 * 5), 2)

mqtt_client.pub_MQTT(177, str(awgDL))
mqtt_client.pub_MQTT(178, str(awgUL))


# в месячную нужно будет плюсовать разницу
monthDL = float(dz.getDevice(28)['Data']) + diffDL
monthUL = float(dz.getDevice(29)['Data']) + diffUL

mqtt_client.pub_MQTT(28, str(monthDL))
mqtt_client.pub_MQTT(29, str(monthUL))

mqtt_client.command_MQTT('setuservariable', 7, data['TotalDownload'])
mqtt_client.command_MQTT('setuservariable', 8, data['TotalUpload'])


today = datetime.datetime.today()
timeHM = today.strftime("%H%M")
timeD = today.strftime("%d")
# время от 00:00:00 до 00:04:59
if float(timeHM) >= 0 and float(timeHM) < 5:
    # обнуляем дневные счетчики в начале нового дня
    mqtt_client.command_MQTT('setuservariable', 7, '0')
    mqtt_client.command_MQTT('setuservariable', 8, '0')
    mqtt_client.pub_MQTT(26, '0')
    mqtt_client.pub_MQTT(27, '0')

    # 5 числа обнуляем месячные счетчики
    if float(timeD) == 5:
        mqtt_client.pub_MQTT(26, '0')
        mqtt_client.pub_MQTT(27, '0')
        mqtt_client.pub_MQTT(28, '0')
        mqtt_client.pub_MQTT(29, '0')

    # clear the traffic history on the router
    client.monitoring.set_clear_traffic()

sys.exit()
