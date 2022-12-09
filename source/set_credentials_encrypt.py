# MIT License
#
# Copyright (c) 2022  Dr. Magnus Christ (mc0110)
#
# This is part of the crypto_keys_package
#
#
# After reboot the port starts with boot.py and main.py
# If you bind this code-segment with
#
# import set_credentials
#
# then after the boot-process the port checks for an encrypted credential.dat file
# If this file isn't found, the user will be asked for input of credentials.
# After the procedure the data will be stored encrypted.
#
#
#
# Änderungen:
# Eingabe mit Defaultwerten
#   Wenn nur die Eigabetaste gedrückt wird, wird der Defaultwert als Input übernommen.
#   Das ist vor allem von Vorteil, wenn die Daten nicht mit yes übernommen werden, weil ein parameter falsch ist.
#   Im zweiten Durchlauf können die richtigen Parameter ohne Neueingabe nur durch Enter übernommen werden,
#   nur die fehlerhafte Parameter müssen neu eingegeben werden.
# Parameter für MainTopic hinzugefügt
#
#
# You can use this short snippet for decrypt your encrypted credentials


# #############
#
# from crypto_keys import fn_crypto as crypt
#
# c = crypt()
# server    = c.get_decrypt_key("credentials.dat", "MQTT")
# ssid      = c.get_decrypt_key("credentials.dat", "SSID")
# wifi_pw   = c.get_decrypt_key("credentials.dat", "WIFIPW")
# user      = c.get_decrypt_key("credentials.dat", "UN")
# password  = c.get_decrypt_key("credentials.dat", "UPW")
# MainTopic = c.get_decrypt_key("credentials.dat", "MAINTOPIC")
# TelNr     = c.get_decrypt_key("credentials.dat", "TELNR")
# PIN       = c.get_decrypt_key("credentials.dat", "PIN")
# #############
#


import os
from crypto_keys import fn_crypto as crypt


def inputDefault(msg, default):
    if default:
        return input("%s [%s]:" % (msg, default)) or default
    else:
        return input("%s :" % (msg))


def find(name, path):
    return name in os.listdir()


print("Check for credentials.dat")
if not (find("credentials.dat", "/")):
    # hier können Defaultwerte eingetragen werden
    SSID = ""
    Wifi_PW = ""
    MQTT = ""
    UName = ""
    UPW = ""
    MAIN_TOPIC = "service/truma"
    PIN = ""
    TELNR = ""

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
    fn = open("credentials.dat", "wb")
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
else:
    print("credentials.dat file exists -> pass the ask for credentials")
