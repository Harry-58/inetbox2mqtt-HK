# MIT License
#
# Copyright (c) 2022  Harry Konz   ( https://github.com/Harry-58 )
#
# unter Verwendung von  https://github.com/olablt/micropython-sim800

import uasyncio as asyncio
import utime as time
from machine import UART
from machine import Pin
import logging

import gc

logLevel = logging.INFO

log = logging.getLogger(__name__)


class sim800l:

    def __init__(self, serial, _rst, _debug=False):
        self.uart = serial
        self.loop = asyncio.get_event_loop()
        self.pinReset = _rst
        self.deadline = None
        self.result = ""
        self.debug = _debug
        log.setLevel(logLevel)

# https://de.wikipedia.org/wiki/GSM_03.38
    def convert_to_string(self, buf):  # info: mit der originalen Funktion werden alle Umlaute durch # ersetzt
        try:
            #print (f"c2s>{buf}")
            tt = buf.decode("utf-8").strip()
            return tt
        except UnicodeError:
            tmp = bytearray(buf)
            gc.collect() # Speicher aufräumen
            for i in range(len(buf)):

                if buf[i] > 127:
                    if tmp[i] == 228:  # ä
                        tmp[i] = ord("a")
                    elif tmp[i] == 246:  # ö
                        tmp[i] = ord("o")
                    elif tmp[i] == 252:  # ü
                        tmp[i] = ord("u")
                    elif tmp[i] == 196:
                        tmp[i] = ord("A")
                    elif tmp[i] == 214:
                        tmp[i] = ord("O")
                    elif tmp[i] == 220:
                        tmp[i] = ord("U")
                    elif tmp[i] == 223:
                        tmp[i] = ord("s")
                    else:
                        tmp[i] = ord("#")
            return bytes(tmp).decode("utf-8").strip()

    # def convert_to_string(self, buf):  # info: mit der originalen Funktion werden alle Umlaute durch # ersetzt
    #     try:                           # durch die dynamische Stringerweiterung gibt es Speicherplatzprobleme
    #         #print (f"c2s>{buf}")      #  deshalb obige Funktion ohne Umlaute
    #         tt = buf.decode("utf-8").strip()
    #         return tt
    #     except UnicodeError:
    #         buf = bytearray(buf)
    #         tmp = ""
    #         for i in range(len(buf)):
    #             gc.collect()
    #             if buf[i] > 127:
    #                 if buf[i] == 228:
    #                     tmp += "ä"
    #                 elif buf[i] == 246:
    #                     tmp += "ö"
    #                 elif buf[i] == 252:
    #                     tmp += "ü"
    #                 elif buf[i] == 196:
    #                     tmp += "Ä"
    #                 elif buf[i] == 214:
    #                     tmp += "Ö"
    #                 elif buf[i] == 220:
    #                     tmp += "Ü"
    #                 elif buf[i] == 223:
    #                     tmp += "ß"
    #                 else:
    #                     tmp += "#"
    #             else:
    #                 tmp += chr(buf[i])
    #         return tmp.strip()

    # def Xconvert_to_string(self, buf):
    #     try:
    #         tt = buf.decode("utf-8").strip()
    #         return tt
    #     except UnicodeError:
    #         tmp = bytearray(buf)
    #         for i in range(len(tmp)):
    #             if tmp[i] > 127:
    #                 tmp[i] = ord("#")
    #         return bytes(tmp).decode("utf-8").strip()

    async def writeline(self, command):
        self.uart.write("{}\r\n".format(command))
        log.debug("<" + command)

    async def write(self, command):
        self.uart.write("{}".format(command))
        log.debug("<" + command)

    def stop(self, in_advance=False):
        if not in_advance:
            pass
            # print("no time left - deadline")
        else:
            pass
            # print("stopped in advance - found expected string")
        self.deadline = None

    def running(self):
        return self.deadline is not None

    def postpone(self, duration=1000):
        self.deadline = time.ticks_add(time.ticks_ms(), duration)

    def read(self, expect=None, duration=1000):
        self.result = ""
        self.postpone(duration)
        self.loop.create_task(self.read_killer(expect, duration))

    async def read_killer(self, expect=None, duration=1000):
        try:
            time_left = time.ticks_diff(self.deadline, time.ticks_ms())
            while time_left > 0:
                line = self.uart.readline()
                if line:
                    line = self.convert_to_string(line)
                    if len(line) > 0:
                        log.debug(">" + line)
                    self.result += line
                    if expect and line.find(expect) == 0:
                        # if expect and expect in line:
                        self.stop(True)
                        return True
                    self.postpone(duration)
                time_left = time.ticks_diff(self.deadline, time.ticks_ms())
        except Exception as e:
            log.exc(e, "")
            self.stop()
        self.stop()

    async def command(self, command, expect=None, duration=1000):
        try:
            while self.uart.any():  # Empfangs-Buffer leeren
                self.uart.read(1)
            await self.writeline(command)

            self.read(expect, duration)
            while self.running():
                await asyncio.sleep(0.2)  # Pause 0.2s

            await asyncio.sleep_ms(25)  # Wartezeit vor Überprüfung auf weitere Zeichen
            while self.uart.any():  # falls noch weitere Zeichen im Empfangspuffer
                self.uart.read(1)   # dann leeren
            result = self.result
            return result
        except Exception as e:
            log.exc(e, "")
            return ""

    ###########################################
    # meine Erweiterungen

    async def getBattery(self):
        try:
            result = await self.command("AT+CBC", "+CBC:")  # 100
            if result:  # +CBC: x,y
                params = result.split(":")
                if params[0] == "+CBC":
                    params = params[1].split(",")
                    return round(float(params[1]) / 1000.0, 2)
        except Exception as e:
            log.exc(e, "")
        return 0

    async def getRSSI(self):
        try:
            result = await self.command("AT+CSQ", "+CSQ:", 5000)
            if result:  # +CSQ:x,y
                params = result.split(":")
                if params[0] == "+CSQ":
                    params = params[1].split(",")
                    x = int(params[0])
                    if not x == 99:
                        return - (113 - (x * 2))
        except Exception as e:
            log.exc(e, "")
        return -999

    async def setPhoneFunc(self, level):
        result = await self.command(f"AT+CFUN={level}", "+CFUN:", 200)  # 100

    async def setBaudrate(self, baudrate):
        result = await self.command(f"AT+IPR={baudrate}", "OK:", 200)  # 100

    async def getNetworkName(self):
        result = await self.command("AT+COPS?", "+COPS:", 180000)
        if result:  # +COPS: 0,0,"E-Plus"
            params = result.split(":")
            if params[0] == "+COPS":
                names = params[1].split('"')
                if len(names) > 1:
                    return names[1]
        return ""

    async def getSmsSpeicher(self):
        try:
            result = await self.command('AT+CPMS?', '+CPMS:', 5000)
            if result:
                # 0123456789
                # +CPMS: "ME",1,50,"ME",1,50,"ME",1,50
                if result.strip().startswith("+CPMS:"):
                    return result[7:].replace('"', '')
        except Exception as e:
            log.exc(e, "")
        return ""

    async def isRegistered(self):
        try:
            result = await self.command('AT+CREG?', '+CREG:', 5000)
            if result:  # +CREG: 0,x
                params = result.split(":")
                if params[0] == "+CREG":
                    params = params[1].split(",")
                    x = int(params[1])
                    if x == 1 or x == 5:  # x=1 oder 5 dann Registered
                        return True
        except Exception as e:
            log.exc(e, "")
        return False

    async def isSimInserted(self):
        try:
            result = await self.command('AT+CSMINS?', '+CSMINS:', 200)
            if result:  # +CSMINS: 0,x
                params = result.split(":")
                if params[0] == "+CSMINS":
                    params = params[1].split(",")
                    if int(params[1]) == 1:  # x=1 dann sim vorhanden
                        return True
        except Exception as e:
            log.exc(e, "")
        return False

    async def pinStatus(self):
        try:
            result = await self.command('AT+CPIN?', '+CPIN:', 5000)
            if result:  # +CPIN: READY   +CPIN: SIM PIN  +CPIN: SIM PUK
                params = result.split(":")
                if params[0] == "+CPIN":
                    if params[1].find("READY") > -1:  # PIN ok
                        return 0
                    elif params[1].find("SIM") > -1:  # PIN notwendig
                        return 1
                    elif params[1].find("PUK") > -1:  # PUK notwendig
                        return 2
        except Exception as e:
            log.exc(e, "")
        return 99

    async def setPin(self, pin):
        try:
            result = await self.command(f'AT+CPIN="{pin}"', "OK:", 5000)
            if result:  # OK / ERROR
                if result.find("OK") > -1:
                    return True
        except Exception as e:
            log.exc(e, "")
        return False

    async def changePin(self, pinOld, pinNew):  # todo: noch nicht getestet
        try:
            result = await self.command(f'AT+CPWD="SC","{pinOld}","{pinNew}"', "OK:", 15000)
            if result:  # OK / ERROR
                if result.find("OK") > -1:
                    return True
        except Exception as e:
            log.exc(e, "")
        return False

    def formatSms(self, sms):
        try:
            params = sms.split('"', 8)
            number = params[3]
            date_time = params[7][:-3]  # Zeitzone (+04) entfernen
            date_time = date_time.replace("/", "-")
            if params[8][:-2] == 'OK':
                msg = params[8][:-2]  # OK enfernen
            else:
                msg = params[8]
            return [number, date_time, msg]
        except Exception as e:
            log.exc(e, "")
            return ["", "", ""]

    async def readSms(self, id, mode=0):  # mode=0:Status auf READ setzen  mode=1:Status nicht ändern
        result = await self.command(f"AT+CMGR={id},{mode}", "OK", 5000)
        #  0     1        2 3             4 56 7                    8
        # +CMGR: "REC READ","+491751234567","","22/11/06,16:54:25+04"Testsms-3OK
        # print (result)
        if result:
            if result.strip().startswith("+CMGR:"):
                try:
                    params = result.split('"', 8)
                    number = params[3]
                    # date_time = params[7][:-3]  # Zeitzone (+04) entfernen
                    #date_time = date_time.replace("/", "-")
                    date_time = params[7]
                    msg = params[8][:-2]  # OK enfernen
                    # return self.formatSms(result)
                    return [number, date_time, msg]
                except Exception as e:
                    log.exc(e, "readSms")
                    return None
        return None

    async def listSms(self, stat=0):  # stat: 0=ALL, 1=UNREAD, 2=READ
        if stat == 0:
            _stat = "ALL"
        if stat == 1:
            _stat = "REC UNREAD"
        if stat == 2:
            _stat = "REC READ"
        result = await self.command(f'AT+CMGL="{_stat}",1', 'OK', 30000)  # SMS auflisten
        # +CMGL: 21,"REC READ","+4917512345678","","22/11/16,11:47:57+04"
        if result:
            try:
                if result.strip().startswith("+CMGL:"):
                    if result[-2:] == 'OK':
                        result = result[:-2]  # OK enfernen
                    smsList = result.split('+CMGL:')

                    # 22,"REC UNREAD","+4917512345678","","22/11/16,15:43:02+04"T-20
                    smsList.pop(0)  # erstes element ist leer, deshalb entfernen
                    for i in range(len(smsList)):
                        smsList[i] = self.convert_to_string(bytearray(smsList[i].strip()))
                        # print(f"sms[{i}]={smsList[i]}")
                    return smsList
            except Exception as e:
                log.exc(e, "listSms")
        return []

    async def sendSms(self, destno, msgtext):
        result = await self.command(f'AT+CMGS="{destno}"\r', '>', 15000)
        if result.startswith(">"):
            result = await self.command(f'{msgtext}\x1A', '+CMGS:', 30000)
            if result.find("+CMGS:") > -1:
                return True
        return False

    async def deleteSms(self, id):
        #print(f"delele_sms: AT+CMGD={id}<")
        if id == 'READ':
            # print("read")
            id = '21,1'        # 21 ist kleinst möglicher index
        elif id == 'ALL':
            # print("all")
            id = '21,4'
        else:
            pass
            # print("id")
        return await self.command(f"AT+CMGD={id}", 'OK', 5000)

    async def date_time(self):
        try:
            result = await self.command('AT+CCLK?', 'OK', 200)  # 100
            if result:
                if result[0:5] == "+CCLK":  # +CCLK: "22/11/15,09:10:53+04"
                    dateTime = result.split('"')[1]
                    # dateTime = dateTime[:-3]  # Zeitzone (+04) entfernen
                    dateTime = dateTime.replace("/", "-")
                    return dateTime
        except Exception as e:
            log.exc(e, "")
        return ''

     # +CGREG - GPRS Network Registration Status

    async def reset(self):
        if self.pinReset > -1:
            rst = Pin(self.pinReset, Pin.OUT)
            rst.value(0)
            await asyncio.sleep_ms(200)
            rst.value(1)
            rst = Pin(self.pinReset, Pin.IN)

    async def setup(self):
        await self.command('ATE0', 'OK', 200)         # command echo off
        await self.command('ATZ', 'OK', 200)          # reset to default
        await self.command('AT+CMEE=2', 'OK', 5000)   # ausführliche error strings
        await self.command('AT+CREG=1', 'OK', 5000)    # Network Registration Report enabled
        # await self.command('AT+CRSL=99', 'OK',5000)   # ringer level
        # await self.command('AT+CMIC=0,10', 'OK',200) # microphone gain
        # await self.command('AT+CLIP=1', 'OK',180000)    # caller line identification

        # await self.command('AT+CALS=3,0', 'OK')  # set ringtone
        # await self.command('AT+CLTS=1', 'OK')    # enable get local timestamp mode
        # await self.command('AT+CSCLK=0', 'OK')   # disable automatic sleep
        # Für SMS
        await self.command('AT+CMGF=1', 'OK', 5000)      # plain text SMS
        await self.command('AT+CSMP=17,167,0,0', 'OK', 5000)
        await self.command('AT+CPMS="ME","ME","ME"', 'OK', 5000)  # SMS Speicher
        await self.command('AT+CNMI=2,1,0', 'OK', 5000)    # Mode,mt,bm  (Mode=2 --> SMS speichern;  mt=1 --> +CMTI:... , mt=2 --> +CMT:...) wie empfangene SMS behandelt werden
        await self.command('AT+CSCS="GSM"', 'OK', 400)     # (Zeichensatz "IRA","GSM","UCS2","HEX","PCCP","PCDN","8859-1")
        # await self.command('AT+CIND=1,1,1,1,1,1,1', 'OK',200)   # +CIND - Indicator Control
        # await self.command('AT+CIND=?', 'OK',200)
        # +CMER - Mobile Equipment Event Reporting
        # +CSCA - Service Center Address
        #  #E2SMSRI - SMS Ring Indicator
        #  #SMOV - SMS Overflow
