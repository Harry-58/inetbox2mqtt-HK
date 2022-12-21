# MIT License
#
# Copyright (c) 2022  Harry Konz   ( https://github.com/Harry-58 )
#
#
#
# Änderungen:


import os
from crypto_keys import fn_crypto as crypt


def inputDefault(msg, default):
    if default:
        return input("%s [%s]:" % (msg, default)) or default
    else:
        return input("%s :" % (msg))


def find(name, path):
    return name in os.listdir()


CREDENTIALS = "credentials.dat"

print("Check for ", CREDENTIALS)
# hier können Defaultwerte eingetragen werden
SSID = ""
Wifi_PW = ""
MQTT = ""
UName = ""
UPW = ""
MAIN_TOPIC = "service/truma"
PIN = ""
TELNR = ""


if find(CREDENTIALS, "/"):
    print(" credentials load from Disk")
    c = crypt()
    MQTT = c.get_decrypt_key(CREDENTIALS, "MQTT")
    SSID = c.get_decrypt_key(CREDENTIALS, "SSID")
    Wifi_PW = c.get_decrypt_key(CREDENTIALS, "WIFIPW")
    UName = c.get_decrypt_key(CREDENTIALS, "UN")
    UPW = c.get_decrypt_key(CREDENTIALS, "UPW")
    MAIN_TOPIC = c.get_decrypt_key(CREDENTIALS, "MAINTOPIC")
    PIN = c.get_decrypt_key(CREDENTIALS, "PIN")
    TELNR = c.get_decrypt_key(CREDENTIALS, "TELNR")

    a = ""
    while a != "yes":
        print("Fill in your credentials:")
        SSID = inputDefault("SSID ", SSID)
        print()
        Wifi_PW = inputDefault("Wifi-password ", Wifi_PW)
        print()
        MQTT = inputDefault("MQTT-Server - IP or hostname ", MQTT)
        print()
        UName = inputDefault("Username ", UName)
        print()
        UPW = inputDefault("User-Password ", UPW)
        print()
        MAIN_TOPIC = inputDefault("MainTopic ", MAIN_TOPIC)
        print()
        PIN = inputDefault("PIN ", PIN)
        print()
        TELNR = inputDefault("erlaubte Telefonnummern (durch Komma trennen) ", TELNR)
        print()

        print("Your inputs are:")
        print()
        print(f"SSID       : {SSID}")
        print(f"Wifi-PW    : {Wifi_PW}")
        print(f"MQTT-Server: {MQTT}")
        print(f"Username   : {UName}")
        print(f"User-PW    : {UPW}")
        print(f"MainTopic  : {MAIN_TOPIC}")
        print(f"PIN        : {PIN}")
        print(f"erlaubte Telefonnummern  : {TELNR}")
        print()
        a = input("ok for you (yes/no): ")

    print("Write credentials encrypted to disk")
    os.rmdir(CREDENTIALS)
    fn = open(CREDENTIALS, "wb")
    c = crypt()
    c.fn_write_encrypt(fn, "SSID:" + SSID)
    c.fn_write_encrypt(fn, "WIFIPW:" + Wifi_PW)
    c.fn_write_encrypt(fn, "MQTT:" + MQTT)
    c.fn_write_encrypt(fn, "UN:" + UName)
    c.fn_write_encrypt(fn, "UPW:" + UPW)
    c.fn_write_encrypt(fn, "MAINTOPIC:" + MAIN_TOPIC)
    c.fn_write_encrypt(fn, "PIN:" + PIN)
    c.fn_write_encrypt(fn, "TELNR:" + TELNR)
    c.fn_write_eof_encrypt(fn)
    fn.close()
