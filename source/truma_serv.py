# MIT License
#
# Copyright (c) 2022  Dr. Magnus Christ (mc0110)
#
# TRUMA-inetbox-simulation
#
# Credentials and MQTT-server-adress must be filled
# If the mqtt-server needs authentification, this can also filled
#
# The communication with the CPplus uses ESP32-UART2 - connect (tx:GPIO17, rx:GPIO16)
#
#
#
# Version: 0.8.5-HK
#
# change_log:
# 0.8.2 HA_autoConfig für den status error_code, clock ergänzt
# 0.8.3 encrypted credentials, including duo_control, improve the MQTT-detection
# 0.8.4 Tested with RP pico w R2040 - only UART-definition must be changed
# 0.8.5 Added support for MPU6050 implementing a 2D-spiritlevel, added board-based autoconfig for UART,
#       added config variables for activating duoControl and spirit-level features
#
# 0.8.5-HK-1  Maintopic parametrierbar,  HA-entfernt,  in main() client.connect mit sleepTime
# 0.8.5-HK-2  import dc_control und  spiritlevel in  if activate_... verlegt, damit Import nur wenn notwendig
# 0.8.5-HK-3  activate_spiritlevel mit try/except damit fehlende MPU nicht zum Programmabbruch führt
# 0.8.5-HK-4  GSM integriert
# 0.8.5-HK-5  publish displaystatus,  rssi, spannung
#


from mqtt_async import MQTTClient, config
import uasyncio as asyncio
from crypto_keys import fn_crypto as crypt
from tools import set_led, toggle_led
from lin import Lin
import uos
import time
from machine import UART, Pin, I2C
import logging

checkMem = True  # HK: zur Überwachung der Speichernutzung
if checkMem:
    import micropython
    import gc  # https://forum.micropython.org/viewtopic.php?t=1747  https://docs.micropython.org/en/latest/develop/memorymgt.html


debug_lin = False
debug_gsm = False

logLevel = logging.INFO


log = logging.getLogger(__name__)
log.setLevel(logLevel)

# Config Features
activate_duoControl = False
activate_spiritlevel = False
activate_GSM = True

# Decrypt your encrypted credentials
c = crypt()
config.server = c.get_decrypt_key("credentials.dat", "MQTT")
config.ssid = c.get_decrypt_key("credentials.dat", "SSID")
config.wifi_pw = c.get_decrypt_key("credentials.dat", "WIFIPW")
config.user = c.get_decrypt_key("credentials.dat", "UN")
config.password = c.get_decrypt_key("credentials.dat", "UPW")
MainTopic = c.get_decrypt_key("credentials.dat", "MAINTOPIC")
TelNr = c.get_decrypt_key("credentials.dat", "TELNR")
Pin = c.get_decrypt_key("credentials.dat", "PIN")

c = None  # crypt wird nicht mehr benötigt

# Change the following configs to suit your environment
S_TOPIC_1 = MainTopic + '/set/'
#S_TOPIC_2 = 'homeassistant/status'
Pub_Prefix = MainTopic + '/control_status/'
GSM_Prefix = MainTopic + '/gsm/'
Display_Prefix = MainTopic + '/display_status/'

Pub_SL_Prefix = 'spiritlevel/status/'


config.clean = True
config.keepalive = 90  # last will after 90sek off

config.set_last_will(MainTopic, "Offline", retain=True, qos=0)  # last will is important

# hw-specific configuration
SDA_PIN = -1
SCL_PIN = -1
if ("ESP32" in uos.uname().machine):
    print("Found ESP32 Board, using UART2 for LIN on GPIO 16(rx), 17(tx)")
    # ESP32-specific hw-UART (#2)
    serial = UART(2, baudrate=9600, bits=8, parity=None, stop=1, timeout=3)  # this is the HW-UART-no
    SDA_PIN = 21
    SCL_PIN = 22
elif ("RP2040" in uos.uname().machine):
    # RP2 pico w -specific hw-UART (#2)
    print("Found Raspberry Pico Board, using UART1 on GPIO 4 and 5")
    serial = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5), timeout=3)  # this is the HW-UART1 in RP2 pico w
    SDA_PIN = 0
    SCL_PIN = 1
else:
    print("No compatible Board found!")
    raise SystemExit

# Initialize the lin-object
lin = Lin(serial, debug_lin)

if activate_duoControl:
    from duo_control import duo_ctrl  # damit import nur wenn notwendig
    # Initialize the duo-ctrl-object
    dc = duo_ctrl()
else:
    dc = None

if activate_spiritlevel:
    try:
        from spiritlevel import spirit_level  # damit import nur wenn notwendig
        # Initialize the i2c and spirit-level Object
        i2c = I2C(0, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=400000)
        time.sleep(1.5)
        sl = spirit_level(i2c)
    except Exception as e:
        log.exc(e, "")
        sl = None
        activate_spiritlevel = False
else:
    sl = None

if activate_GSM:
    from gsm import gsm
    # Initialize the gsm-object
    gsm = gsm(lin.app, TelNr, Pin, debug_gsm)
else:
    gsm = None


# # Auto-discovery-function of home-assistant (HA)
# HA_MODEL  = 'inetbox'
# HA_SWV    = 'V02'
# HA_STOPIC = 'service/truma/control_status/'
# HA_CTOPIC = 'service/truma/set/'

# HA_CONFIG = {
#     "alive":             ['homeassistant/binary_sensor/truma/alive/config', '{"name": "truma_alive", "model": "' + HA_MODEL + '", "sw_version": "' + HA_SWV + '", "device_class": "running", "state_topic": "' + HA_STOPIC + 'alive"}'],
#     "current_temp_room": ['homeassistant/sensor/current_temp_room/config', '{"name": "truma_current_temp_room", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "device_class": "temperature", "unit_of_measurement": "°C", "state_topic": "' + HA_STOPIC + 'current_temp_room"}'],
#     "current_temp_water":['homeassistant/sensor/current_temp_water/config', '{"name": "truma_current_temp_water", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "device_class": "temperature", "unit_of_measurement": "°C", "state_topic": "' + HA_STOPIC + 'current_temp_water"}'],
#     "target_temp_room":  ['homeassistant/sensor/target_temp_room/config', '{"name": "truma_target_temp_room", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "device_class": "temperature", "unit_of_measurement": "°C", "state_topic": "' + HA_STOPIC + 'target_temp_room"}'],
#     "target_temp_water": ['homeassistant/sensor/target_temp_water/config', '{"name": "truma_target_temp_water", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "device_class": "temperature", "unit_of_measurement": "°C", "state_topic": "' + HA_STOPIC + 'target_temp_water"}'],
#     "energy_mix":        ['homeassistant/sensor/energy_mix/config', '{"name": "truma_energy_mix", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "state_topic": "' + HA_STOPIC + 'energy_mix"}'],
#     "el_power_level":          ['homeassistant/sensor/el_level/config', '{"name": "truma_el_power_level", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "state_topic": "' + HA_STOPIC + 'el_power_level"}'],
#     "heating_mode":            ['homeassistant/sensor/heating_mode/config', '{"name": "truma_heating_mode", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "state_topic": "' + HA_STOPIC + 'heating_mode"}'],
#     "operating_status":        ['homeassistant/sensor/operating_status/config', '{"name": "truma_operating_status", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "state_topic": "' + HA_STOPIC + 'operating_status"}'],
#     "error_code":              ['homeassistant/sensor/error_code/config', '{"name": "truma_error_code", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "state_topic": "' + HA_STOPIC + 'error_code"}'],
#     "clock":                   ['homeassistant/sensor/clock/config', '{"name": "truma_clock", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "state_topic": "' + HA_STOPIC + 'clock"}'],
#     "set_target_temp_room":    ['homeassistant/select/target_temp_room/config', '{"name": "truma_set_roomtemp", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "command_topic": "' + HA_CTOPIC + 'target_temp_room", "options": ["0", "10", "15", "18", "20", "21", "22"] }'],
#     "set_target_temp_water":   ['homeassistant/select/target_temp_water/config', '{"name": "truma_set_warmwater", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "command_topic": "' + HA_CTOPIC + 'target_temp_water", "options": ["0", "40", "60", "200"] }'],
#     "set_heating_mode":        ['homeassistant/select/heating_mode/config', '{"name": "truma_set_heating_mode", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "command_topic": "' + HA_CTOPIC + 'heating_mode", "options": ["off", "eco", "high"] }'],
#     "set_energy_mix":          ['homeassistant/select/energy_mix/config', '{"name": "truma_set_energy_mix", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "command_topic": "' + HA_CTOPIC + 'energy_mix", "options": ["none", "gas", "electricity", "mix"] }'],
#     "set_el_power_level":      ['homeassistant/select/el_power_level/config', '{"name": "truma_set_el_power_level", "model": "' + HA_MODEL + '", "sw_version":"' + HA_SWV + '", "command_topic": "' + HA_CTOPIC + 'el_power_level", "options": ["0", "900", "1800"] }'],
# }


# Universal callback function for all subscriptions
def callback(topic, msg, retained, qos):
    topic = str(topic)
    topic = topic[2:-1]
    msg = str(msg)
    msg = msg[2:-1]
    print("Received:", topic, msg, retained, qos)
    # Command received from broker
    if topic.startswith(S_TOPIC_1):
        topic = topic[len(S_TOPIC_1):]
        if topic in lin.app.status.keys():
            print("inet-key:", topic, msg)
            try:
                lin.app.set_status(topic, msg)
            except Exception as e:
                log.exc(e, "")
                # send via mqtt
        elif not (dc == None):
            if topic in dc.status.keys():
                print("dc-key:", topic, msg)
                try:
                    dc.set_status(topic, msg)
                except Exception as e:
                    log.exc(e, "")
                    # send via mqtt
            else:
                print("key incl. dc is unkown")
        else:
            print("key w/o dc is unkown")
    # # HA-server send ONLINE message
    # if (topic == S_TOPIC_2) and (msg == 'online'):
    #     print("Received HOMEASSISTANT-online message")
    #     await set_ha_autoconfig(client)


# Initialze the subscripted topics
async def conn_callback(client):
    print("MQTT connected")
    set_led("MQTT", True)
    await client.publish(MainTopic, "Online", qos=0)
    # inetbox_set_commands
    await client.subscribe(S_TOPIC_1+"#", 1)
    # # HA_online_command
    # await client.subscribe(S_TOPIC_2, 1)


# Wifi and MQTT status
async def wifi_status(info):
    if info:
        print("Wifi connected")
    else:
        print("Wifi connection lost")
        set_led("MQTT", False)


# # HA autodiscovery - delete all entities
# async def del_ha_autoconfig(c):
#     for i in HA_CONFIG.keys():
#         try:
#             await c.publish(HA_CONFIG[i][0], "{}", qos=1)
# #            print(i,": [" + HA_CONFIG[i][0] + "payload: {}]")
#         except:
#             print("Publishing error in del_ha_autoconfig")

# # HA auto discovery: define all auto config entities
# async def set_ha_autoconfig(c):
#     print("set ha_autoconfig")
#     for i in HA_CONFIG.keys():
#         try:
#             await c.publish(HA_CONFIG[i][0], HA_CONFIG[i][1], qos=1)
# #            print(i,": [" + HA_CONFIG[i][0] + "payload: " + HA_CONFIG[i][1] + "]")
#         except:
#             print("Publishing error in set_ha_autoconfig")


async def publish_displaystatus():
    if len(lin.app.display_status) > 0:
        s = lin.app.display_status
        #print (f"display_status: {s}")
        if lin.app.display_status_updated:
            lin.app.display_status_updated = False
            for key in s.keys():
                print(f'publish {Display_Prefix[len(MainTopic)+1:]+key}:{s[key]}')
                try:
                    await client.publish(Display_Prefix+key, str(s[key]), qos=0)
                    s.pop(key)  # todo:hk noch prüfen   damit Status nur nach Änderung übertragen wird
                except:
                    print("Error in Display Status publishing")
            s.clear()  # todo:hk oder so alle auf einmal  damit Status nur nach Änderung übertragen wird


# main publisher-loop
async def main(client):
    print(f"main-loop is running  (MainTopic:{MainTopic})")
    set_led("MQTT", False)
    err_no = 1
    while err_no:
        try:
            await client.connect()
            err_no = 0
        except:
            toggle_led("MQTT")
            await asyncio.sleep_ms(50)  # um die Systemlast zu reduzieren
            err_no += 1
            if err_no > 200:  # maximal 10sec Verbindungsversuch
                err_no = 1
                set_led("MQTT", False)
                await asyncio.sleep(60)  # nächster Verbindungsversuch nach 60sec
    lin.app.status["rssi"][0] = getRssi(client)
    lin.app.status["rssi"][1] = True
    # await del_ha_autoconfig(client)
    # await set_ha_autoconfig(client)

    i = 0
    while True:
        await asyncio.sleep(10)  # Update every 10sec
        if checkMem:   # Speicher überwachen   https://docs.micropython.org/en/latest/reference/constrained.html#the-heap
            #micropython.mem_info()
            mem = gc.mem_free()
            if mem < 20000:
                gc.collect()  # Speicher aufräumen
                #print(f"mem_free:{mem} --> {gc.mem_free()}")

        s = lin.app.get_all(True)
        for key in s.keys():
            print(f'publish {key}:{s[key]}')
            try:
                await client.publish(Pub_Prefix+key, str(s[key]), qos=1)
            except:
                print("Error in LIN status publishing")

        if not (dc == None):
            s = dc.get_all(True)
            for key in s.keys():
                print(f'publish {key}:{s[key]}')
                try:
                    await client.publish(Pub_Prefix+key, str(s[key]), qos=1)
                except:
                    print("Error in duo_ctrl status publishing")

        if not (sl == None):
            s = sl.get_all()
            for key in s.keys():
                print(f'publish {key}:{s[key]}')
                try:
                    await client.publish(Pub_SL_Prefix+key, str(s[key]), qos=1)
                except:
                    print("Error in spirit_level status publishing")

        if not (gsm == None):
            s = gsm.get_all(True)
            for key in s.keys():
                print(f'publish {GSM_Prefix[len(MainTopic)+1:]+key}:{s[key]}')
                try:
                    await client.publish(GSM_Prefix+key, str(s[key]), qos=0)
                except:
                    print("Error in GSM status publishing")

        # loop-count
        i += 1
        if not (i % 6):  # jede Minute
            # await client._ping_n_wait(client._proto)  #Verbindung aufrecht erhalten
            # continue  # zum Test, um nachfolgende Meldungen zu unterdrücken

            lin.app.status["alive"][1] = True   # Verbindungsstatus Truma
            await publish_displaystatus()       # Displaystatus

        if not (i % 60):  # alle 10 Minuten
            i = 0
            #lin.app.status["spannung"][1] = True
            lin.app.status["rssi"][0] = getRssi(client)
            lin.app.status["rssi"][1] = True


# major ctrl loop for inetbox-communication
async def lin_loop():
    await asyncio.sleep(1)  # Delay at begin
    print("lin-loop is running")
    while True:
        lin.loop_serial()
        if not (lin.stop_async):
            await asyncio.sleep_ms(1)


# major ctrl loop for duo_ctrl_check
async def dc_loop():
    await asyncio.sleep(30)  # Delay at begin
    print("duo_ctrl-loop is running")
    while True:
        dc.loop()
        await asyncio.sleep(10)


async def sl_loop():
    await asyncio.sleep(5)  # Delay at begin
    print("spirit-level-loop is running")
    while True:
        sl.loop()
        #print("Angle X: " + str(sl.get_roll()) + "      Angle Y: " +str(sl.get_pitch()) )
        await asyncio.sleep_ms(100)


async def gsm_loop():
    await asyncio.sleep(10)
    await gsm.setup()
    print("GSM-loop is running")
    while True:
        await gsm.loop_serial()
        if not (gsm.stop_async):
            await asyncio.sleep_ms(5)
        else:
            print("GSM-loop stopped")


def getRssi(client):
    while True:
        try:
            rssi = client.getRSSI()
            #print(f"RSSI: {rssi}")
        except:
            rssi = -999
        return rssi


async def rssi_loop(client):  # zum Testen
    await asyncio.sleep(5)  # Delay at begin
    print("rssi-loop is running")
    while True:
        print(f"RSSI: {getRssi(client)}")
        await asyncio.sleep(2)


config.subs_cb = callback
config.connect_coro = conn_callback
config.wifi_coro = wifi_status

# if not(dc == None):
#     HA_CONFIG.update(dc.HA_DC_CONFIG)
# if not(sl == None):
#     HA_CONFIG.update(sl.HA_SL_CONFIG)


try:
    loop = asyncio.get_event_loop()
    client = MQTTClient(config)

    a = asyncio.create_task(main(client))
    b = asyncio.create_task(lin_loop())
    if not (dc == None):
        c = asyncio.create_task(dc_loop())
    if not (sl == None):
        d = asyncio.create_task(sl_loop())
    if not (gsm == None):
        e = asyncio.create_task(gsm_loop())
    # f = asyncio.create_task(rssi_loop(client))  #RSSI anzeigen um besten Antennnenort zu finden
    loop.run_forever()

except KeyboardInterrupt:
    print("Abbruch durch Ctrl-C")
except Exception as e:
    log.exc(e, "")
finally:
    set_led("MQTT", False)
    set_led("D8", False)
    set_led("GSM", False)
