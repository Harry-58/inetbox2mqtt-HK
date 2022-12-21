# MIT License
#
# Copyright (c) 2022  Harry Konz   ( https://github.com/Harry-58 )
#
# version 0.9.0
#
# https://community.hiveeyes.org/t/micropython-libraries-for-the-sim800-module/1492
# https://www.az-delivery.de/en/blogs/azdelivery-blog-fur-arduino-und-raspberry-pi/gps-und-gsm-mit-micropython-auf-dem-esp32-teil-3
# https://github.com/jeffmer/micropython-upyphone
# https://wolles-elektronikkiste.de/sim800l-modul
# https://www.az-delivery.de/blogs/azdelivery-blog-fur-arduino-und-raspberry-pi/gsm-und-telefonie-mit-micropython-auf-dem-esp32-und-dem-sim808-teil-5
# https://infocenter.nordicsemi.com/index.jsp?topic=%2Fref_at_commands%2FREF%2Fat_commands%2Fsecurity%2Fcpwd_set.html
# https://docs.micropython.org/en/latest/esp32/quickref.html#uart-serial-bus
#
#  *** Truma mit SMS steuern  ***
#   durch senden einer SMS kann die Truma-Heizung gesteuert werden.
#   Eine SMS wird nur von den in "erlaubteAbsender" eingetragenen Nummern angenommen.
#
#   mögliche SMS:  T.nn [?]     Raumtemperatur wird auf den Wert nn, und der heating_mode auf eco gesetzt
#                               Erlaubte Werte für nn:  0-4=aus, 5-30
#                  B.nn [?]     Boiler (Warmwasser)  wird auf den Wert nn gesetzt.
#                               Erlaubte Werte für nn:  0=aus, 40=eco, 60=high, 200=boost
#
#                  S. [?]       SMS Speicherbelegung auflisten
#                  L.a/u/r [?]  SMS auflisten  a=alle  u=ungelesene  r=gelesene
#                  Del.r [?]    alle gelesenen SMS löschen
#                  Del.a  [?]   alle SMS löschen
#                  Status       Status InetBox abfragen.
#                                 Antwort-SMS: ttr:x; ctr:x  ttw:x; ctw:x  hm:x; os:x  U:x; err:x  rW:xx; rG:xx  lin:x; mqtt:x
#                                   ttr=target_temp_room   ctr=current_temp_room
#                                   ttw=target_temp_water  ctw=current_temp_water
#                                   hm=heating_mode        os= operating_status
#                                   U=spannung             err=error_code
#                                   rW=rssi-Wifi           rG=rssi-GSM
#                                   lin=alive              mqtt=On-/Offline
#
#   Das Ergebniss einer SMS sieht man anhand der MQTT-Meldungen bzw. Print-Ausgaben.
#   Soll das Ergebniss als SMS zurückgesendet werden, muss hinter den Befehl ein "?" geschrieben werden (z.B: T.15? ).
#   Die Anwort-SMS wird bei den T/B SMSen erst nach 1min zurückgesendet, weil die Truma verzögert reagiert.
#


import uasyncio as asyncio
from machine import UART
from tools import set_led, toggle_led, get_led
from sim800l import sim800l as sim
import json
import logging

logLevel = logging.DEBUG


# TODO: Speicher reicht dafür nicht aus
#from datetime import timedelta as timedelta
#from datetime import datetime as datetime

# *** Anschlußschema SIM800l an ESP32 ***
#
#  ESP32(3,3V)          SIM800(3,4-4,4V)
#                         IPX ◙
#                         Ant ◘
#  Vcc(4,1V) ------------ Vcc o         o Ring
#  Pin18 ------1k-------- RST o         o DTR
#  Pin33(tx)---1k --+---- RX  o         o MIC+
#                   |
#                  5,6k
#                   v
#                  GND
#  Pin34(rx)---1k ------- TX  o         o MIC-
#  GND   ---------------- GND o         o Lautsprecher+
#                                       o Lautsprecher-
#
#        RX       TX
# UART0	GPIO3	  GPIO1
# UART1	GPIO9(34) GPIO10(33) Default-Pins können nicht verwendet werden, da mit Flash verbunden --> umlegen  https://www.engineersgarage.com/micropython-esp8266-esp32-uart/
# UART2	GPIO16	  GPIO17


TX_PIN = 33
RX_PIN = 34
RST_PIN = 18   # auf -1 setzen wenn ohne Hardwarereset
BAUDRATE = 115200  # 9600, 19200, 38400, 57600, 115200

serial_sim800 = UART(1, baudrate=BAUDRATE, tx=TX_PIN, rx=RX_PIN, bits=8, parity=None, stop=1, timeout=3)

log = logging.getLogger(__name__)


class gsm:
    erlaubteAbsender = ["+49 172 xxxxxxxx", "+49yyyyyyyyyy"]  # hier Telefonnummern eintragen von denen SMSen angenommen werden (beliebig viele)
    # mit Landesvorwahl
    # wenn in __init__  Telefonnummern übergeben werden, wird die Liste überschrieben

    inetApp = None
    debug = False
    info = True
    pin = None

    debug_sim = False

    stop_async = False
    loop_cnt_Minute = 8100  # etwa 1-Minute
    loop_cnt = loop_cnt_Minute - 100

    sim = sim(serial_sim800, RST_PIN, debug_sim)

    status = {'status':    [0, True],
              'nachricht': ["-", False],
              'speicher':  ["-", False],
              'netname':   ["-", False],
              'error':     ["-", False],
              'rssi':      [0, False]}

    def __init__(self, inetApp, telNr, pin=None, debug=False):
        self.inetApp = inetApp
        self.debug = debug
        log.setLevel(logLevel)
        self.pin = pin
        if len(telNr) > 5:
            self.erlaubteAbsender = telNr.split(",")
        i = 0
        for nr in self.erlaubteAbsender:
            self.erlaubteAbsender[i] = ''.join(nr.split())  # alle Leerzeichen entfernen
            i += 1
        log.info(f"erlaubteAbsender: {self.erlaubteAbsender}")

    def set_status(self, key, value):
        if key in self.status.keys():
            #print(f"set_status: {key}:{value}")
            self.status[key] = [value, True]
        else:
            log.warning(f"set_status: {key}:{value}  nicht gefunden")

    def get_status(self, key):
        try:
            return self.status[key][0]
        except Exception as e:
            log.exc(e, f"get_status: {key}  nicht gefunden")
            return ""

    # Status-Dump - with False, it sends all status-values
    # with True it sends only a list of changed values - but reset the change-flag
    def get_all(self, only_updates):
        #print("Status:", self.status)
        if not (only_updates):
            status_updated = False
            return {key: self.get_status(key) for key in self.status.keys()}
        else:
            s = {}
            for key in self.status.keys():
                status_updated = False
                if self.status[key][1]:
                    self.status[key][1] = False
                    self.status_updated = True
                    s.update({key: self.get_status(key)})
            return s

    def XXXtimeDiff(self, tAct, tSms):  # speicherplatzprobleme
        pass
        # SMS-Time 22-11-15,09:10:50
        # 01234567890123456789
        # ACT-Time 22/11/13,17:54:30+04
       # timeAct =  datetime(int('20'+tAct[0:2]), int(tAct[3:5]), int(tAct[6:8]), int(tAct[9:11]), int(tAct[12:14]), int(tAct[15:17]))
       # print(f"timeAct:{timeAct}")
       # timeSms =  datetime(int('20'+tSms[0:2]), int(tSms[3:5]), int(tSms[6:8]), int(tSms[9:11]), int(tSms[12:14]), int(tSms[15:17]))
       # print(f"timeSms:{timeSms}")
       # delta = timeAct - timeSms
       # return delta.seconds

    def timeDiff(self, tAct, tSms):
        # SMS-Time 22-11-15,09:10:50
        # 01234567890123456789
        # ACT-Time 22-11-13,17:54:30
        # print(f"tAct:{tAct}")
        # print(f"tSms:{tSms}")
        #         tag im Monat           stunden              minuten               sekunden
        ta = (int(tAct[6:8])*86400) + (int(tAct[9:11])*3600) + (int(tAct[12:14])*60) + int(tAct[15:17])
        ts = (int(tSms[6:8])*86400) + (int(tSms[9:11])*3600) + (int(tSms[12:14])*60) + int(tSms[15:17])
        # wenn tAct in anderem Monat als tSms liegt, kommt falsches delta
        return ta-ts

    # def testDelta(self):
    #   delta = self.timeDiff("22-11-16,09:10:50", "22-11-16,09:10:33")
    #   print(f"Test-Delta:{delta}")

    async def setup(self):
        try:
            while True:
                log.info("Setup")
                self.set_status('status', 0)
                await self.sim.reset()
                await asyncio.sleep(5)
                await self.sim.command('AT', 'OK', 1000)  # autobauding
                await self.sim.command('AT', 'OK', 1000)
                await self.sim.setBaudrate(BAUDRATE)

                simVorhanden = False
                while not simVorhanden:
                    simVorhanden = await self.sim.isSimInserted()
                    if not simVorhanden:
                        self.set_status('error', "SIM fehlt")
                        await asyncio.sleep(600)

                pinStatus = await self.sim.pinStatus()  # prüfen ob Pin notwendig
                if pinStatus > 0:
                    if len(self.pin) > 0:
                        await self.sim.setPin(self.pin)
                while pinStatus != 0:        # ohne PIN/PUK geht nix
                    pinStatus = await self.sim.pinStatus()
                    if pinStatus == 0:
                        print("PIN ok")
                        break
                    elif pinStatus == 1:
                        msg = "PIN notwendig"
                    elif pinStatus == 2:
                        msg = "PUK notwendig"
                    else:
                        msg = "Fehler PIN"
                    log.error(msg)
                    self.set_status('error', msg)
                    await asyncio.sleep(600)

                await self.sim.setup()
                imNetz = await self.sim.isRegistered()
                print(f'simVorhanden:{simVorhanden}  imNetz:{imNetz}')
                if simVorhanden and imNetz and pinStatus == 0:
                    break
                else:
                    await asyncio.sleep(60)

            set_led("GSM", True)
            erg = await self.sim.getSmsSpeicher()
            log.info(f"SMS-Speicher: { erg }")  # verfügbarer SMS Speicher
            self.set_status('speicher', erg)
            self.set_status('status', 1)
            self.set_status('error', '-')
            erg = await self.sim.getNetworkName()
            self.set_status('netname', erg)
            rssi = await self.sim.getRSSI()
            self.set_status('rssi', rssi)
            # todo: gespeicherte UNREAD SMS verarbeiten
            smsList = await self.sim.listSms(1)  # SMS auflisten 0=All, 1=UNREAD, 2=READ
            for i in range(len(smsList)):
                log.debug(f"sms[{i}]={smsList[i]}")
            self.set_status('nachricht', json.dumps(smsList))  # ohne json werden Umlaute in hex konvertiert
        except Exception as e:
            log.exc(e, "")

    async def setHeat(self, temp, mode):
        topic = "target_temp_room"
        msg = str(temp)
        await self.setTruma(topic, msg)
        await asyncio.sleep_ms(100)
        topic = "heating_mode"
        msg = str(mode)
        await self.setTruma(topic, msg)
        return

    async def setWater(self, temp):
        topic = "target_temp_water"
        msg = str(temp)
        await self.setTruma(topic, msg)
        return

    async def setTruma(self, topic, msg):
        topic = str(topic)
        msg = str(msg)
        log.debug(f"setTruma:{topic}={msg}")
        if topic in self.inetApp.status.keys():
            try:
                self.inetApp.set_status(topic, msg)
            except Exception as e:
                log.exc(e, "")
        else:
            log.error(f"key {topic} ist unbekannt")

    async def loop_serial(self):
        try:
            self.loop_cnt += 1
            if not (self.loop_cnt % (self.loop_cnt_Minute*5)):  # alle 5 Minuten
                rssi = await self.sim.getRSSI()                 # rssi senden
                self.set_status('rssi', rssi)

                toggle_led("GSM")
                imNetz = await self.sim.isRegistered()          # überprüfen ob im Netz registriert
                if imNetz:
                    set_led("GSM", True)
                    self.set_status('status', 1)
                else:
                    set_led("GSM", False)
                    self.set_status('status', 0)

            if not (self.loop_cnt % (self.loop_cnt_Minute*60)):  # alle 60 Minuten
                self.loop_cnt = 0
                erg = await self.sim.getSmsSpeicher()            # SMS Speicherbelegung senden
                self.set_status('speicher', erg)

            if (self.sim.uart.any()):
                line = self.sim.uart.readline()
                line = self.sim.convert_to_string(line)
                if line == "None":  # Timeout erkennen, mit exception geht's nicht
                    pass
                    log.warning("*** sim_timeout")
                else:
                    if len(line) > 0:
                        line = line.strip()
                        set_led("GSM", True)
                        if not line.startswith('OK'):
                            log.debug(f"sim: {line}")
                        if line.find('NOT READY') >= 0 or line.find('ERROR') >= 0 or line.find('VOLTAGE') >= 0:
                            self.set_status('error', line)
                            set_led("GSM", False)
                            # E:\PlatformIO\Test\GSM_SIM800\SIM800 Series_AT Command Manual_V1.10.pdf  ab Seite 342
                        elif line.startswith('+CREG:'):  # Netzwerk geändert
                            pass
                            # erg = await self.sim.getNetworkName()
                            #self.set_status('netname', erg)
                            # rssi = await self.sim.getRSSI()
                            #self.set_status('rssi', rssi)
                        elif line.startswith('+CMTI:'):  # SMS empfangen indirekt, SMS steht im Speicher  +CMGR: "REC UNREAD","+4917512345678","","22/12/07,12:32:01+04"\rTest1
                            await self.doSMS(line)
                        elif line.startswith('+CMT:'):   # SMS empfangen direkt                            +CMT: "+4917512345678","","22/12/07,12:29:50+04"
                            await self.doSMS(line)
                        elif line.startswith('+CIEV:'):  # +CIEV: 10,"26203","netzclub+","netzclub+", 0, 0
                            pass
        except Exception as e:
            log.exc(e, "")

# https://websms.de/de-de/blog/sms-codierung-warum-eine-sms-70-oder-160-zeichen-lang-ist/
    async def doSMS(self, line):
        log.debug(f"SMS empfangen:{line}")
        try:
            if line.startswith('+CMT:'):  # +CMT: "+491751234567","","22/12/07,13:05:16+04"
                params = line.split('"', 6)
                log.debug(f"CMT-params: { params}  {len(params)}")
                if len(params) > 5:
                    absender = params[1]
                    smsTime = params[5]
                    index = -1
                    nachricht = ''
                    await asyncio.sleep_ms(200)
                    while self.sim.uart.any() > 0:
                        tmp = self.sim.convert_to_string(self.sim.uart.readline())
                        nachricht = nachricht + tmp
                        await asyncio.sleep_ms(100)
                else:
                    log.error('CMT no params')
                    return
            elif line.startswith('+CMTI:'):  # +CMTI: "ME",21
                params = line.split(',')
                log.debug(f"CMTI-params: { params}  {len(params)}")
                if len(params) > 1:
                    index = params[1].strip("'")
                    # print(f"index:{index}")
                    absender, smsTime, nachricht = await self.sim.readSms(index)
                else:
                    log.error('CMTI no params')
                    return
            else:
                log.error('no SMS')
                return

            log.info(f"SMS:von:{absender} um:{smsTime} msg:{nachricht}")
            if absender in self.erlaubteAbsender:  # Absender erlaubt
                self.set_status('nachricht', f"von:{absender} um:{smsTime} msg:{nachricht}")
                actTime = await self.sim.date_time()  # 22-11-15,09:12:30
                #print (f"actTime:{actTime}")
                delta = self.timeDiff(actTime, smsTime)
                #print (f"delta:{delta}")
                if delta < 3600:  # nur verarbeiten wenn nicht älter als 1 Stunde
                    log.debug("SMS zulässig")
                    nachricht = nachricht.strip().lower()
                    if nachricht.startswith("t.") or nachricht.startswith("b."):  # Raum- und Wassertemperatur setzen
                        await self.doTruma(absender, nachricht)
                        if index != -1:
                            await self.sim.deleteSms(index)
                    elif nachricht.startswith("s."):    #
                        if index != -1:
                            await self.sim.deleteSms(index)
                        erg = await self.sim.getSmsSpeicher()  # SMS Speicherbelegung abrufen
                        log.debug(f"SMS-Speicher: { erg }")
                        self.set_status('speicher', erg)
                        if nachricht.endswith("?"):  # Antwort-SMS wird erwartet
                            params = erg.split(",")  # "ME",1,50,"ME",1,50,"ME",1,50
                            if len(params) > 2:
                                msg = f"SMS-Speicherbelegung: {params[1]} von {params[2]}"
                            else:
                                msg = "SMS-Speicherbelegung unbekannt"
                            if not await self.sim.sendSms(absender,  erg):
                                log.error("Fehler beim senden Speicher-SMS")
                    elif nachricht.startswith("l."):      # SMS auflisten
                        if index != -1:
                            await self.sim.deleteSms(index)
                        if nachricht.startswith("l.a"):     # Alle
                            erg = await self.sim.listSms(0)
                        elif nachricht.startswith("l.u"):   # ungelesene
                            erg = await self.sim.listSms(1)
                        elif nachricht.startswith("l.r"):   # gelesene
                            erg = await self.sim.listSms(2)
                        else:                               # wenn ohne stat dann ungelesene
                            erg = await self.sim.listSms(1)
                        Anzahl_Read = 0
                        Anzahl_UnRead = 0
                        for i in range(len(erg)):
                            if erg[i].find("UNREAD") >= 0:
                                Anzahl_UnRead = +1
                            elif erg[i].find("READ") >= 0:
                                Anzahl_Read = +1
                            log.debug(f"sms[{i}]={erg[i]}")
                        self.set_status('nachricht', json.dumps(erg))  # ohne json werden Umlaute in hex konvertiert
                        if nachricht.endswith("?"):  # Antwort-SMS wird erwartet
                            msg = f"SMS-gelesen:   {Anzahl_Read}\nSMS-ungelesen: {Anzahl_UnRead}"
                            if not await self.sim.sendSms(absender, msg):
                                log.error("Fehler beim senden Speicher-SMS")
                    elif nachricht.startswith("del."):  # SMS löschen
                        if nachricht.startswith("del.r"):  # alle gelesenen SMS löschen
                            erg = await self.sim.deleteSms("READ")
                        elif nachricht.startswith("del.a"):  # alle SMS löschen
                            erg = await self.sim.deleteSms("ALL")
                        else:
                            erg = await self.sim.deleteSms("READ")
                        log.debug(f"SMS-Speicher löschen: {erg}")
                        if nachricht.endswith("?"):  # Antwort-SMS wird erwartet
                            msg = "SMS-Speicher geloescht"
                            if not await self.sim.sendSms(absender, msg):
                                log.error("Fehler beim senden Lösch-SMS")

                    elif nachricht.startswith("status"):  # Truma-Status abfragen
                        await self.doStatus(absender)
                        if index != -1:
                            await self.sim.deleteSms(index)
                    else:
                        log.warning("Befehl unbekannt")
                else:
                    log.info("SMS ist zu alt --> nicht zulässig")
                    self.set_status('error', f"SMS zu alt: {absender} um:{smsTime} msg:{nachricht}")
            else:
                log.warning(f"Absender {absender} nicht erlaubt")
                self.set_status('error', f"Absender nicht erlaubt: {absender} um:{smsTime} msg:{nachricht}")
        except Exception as e:
            log.exc(e, "")

    async def doTruma(self, absender, nachricht):
        try:
            if nachricht.startswith("t."):  # t.15  (0-30)
                temp = nachricht[2:].replace('?', '').strip()
                if not temp.isdigit():
                    temp = 0
                log.info(f"temp:{temp}")
                if int(temp) < 5:
                    temp = 0
                    mode = "off"
                else:
                    mode = "eco"
                if int(temp) > 30:
                    temp = 30  # maximal 30Grad möglich
                await self.setHeat(temp, mode)
            elif nachricht.startswith("b."):  # b.40  (0,40,60,200)
                boil = nachricht[2:].replace('?', '').strip()
                if not boil.isdigit():
                    boil = 0
                if not boil in [0, 40, 60, 200]:
                    boil = 40    # bei falschen Werten auf 40=eco setzen
                log.info(f"boil:{boil}")
                await self.setWater(boil)
            else:
                log.warning(f"truma_unbekannt: {nachricht}")
                return
            if nachricht.endswith("?"):  # Antwort-SMS wird erwartet
                asyncio.create_task(self.doStatus(absender, 30))  # Status verzögert senden, da Truma den Befehl erst verarbeiten muss
        except Exception as e:
            log.exc(e, "")

    async def doStatus(self, absender, delay=0):
        if delay > 0:
            log.debug(f"doStatus verzögert um {delay}s")
            await asyncio.sleep(delay)
        try:
            log.debug("Status als SMS senden")  # self.app.status['target_temp_room'][0]
            msg = 'ttr:' + self.inetApp.get_status('target_temp_room') + \
                '; ctr:' + self.inetApp.get_status('current_temp_room') + \
                '\nttw:' + self.inetApp.get_status('target_temp_water') + \
                '; ctw:' + self.inetApp.get_status('current_temp_water') + \
                '\nhm:' + self.inetApp.get_status('heating_mode') + \
                '; os:' + self.inetApp.get_status('operating_status') + \
                '\nU:' + str(self.inetApp.get_status('spannung')) + \
                '; err:' + self.inetApp.get_status('error_code') + \
                '\nrW:' + str(self.inetApp.get_status('rssi')) + \
                '; rG:' + str(self.get_status('rssi')) + \
                '\nlin:' + self.inetApp.get_status('alive') + \
                '; mqtt:' + ("ON" if get_led("MQTT") == 1 else "OFF")
            log.debug(msg)
            if not await self.sim.sendSms(absender,  msg):
                log.error("Fehler beim senden Status-SMS")
        except Exception as e:
            log.exc(e, "")
