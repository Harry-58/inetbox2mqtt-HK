#  Erweiterung inetbox2mqtt
  ### Truma-Heizung mit SMS steuern  (SIM800L)

   Durch senden einer SMS kann die Truma-Heizung gesteuert werden.

      mögliche SMS: T.nn      Raumtemperatur wird auf den Wert nn, und der heating_mode auf eco gesetzt
                               Erlaubte Werte für nn:  0-4=aus, 5-30
                    B.nn      Boiler (Warmwasser)  wird auf den Wert nn gesetzt.
                               Erlaubte Werte für nn:  0=aus, 40=eco, 60=high, 200=boost

                    S.        SMS Speicherbelegung auflisten
                    L.a/u/r   SMS auflisten  a=alle  u=ungelesene  r=gelesene
                    Del.r     alle gelesenen SMS löschen
                    Del.a     alle SMS löschen
                    Status    Status InetBox abfragen.
                                Antwort-SMS: ttr:x; ctr:x  ttw:x; ctw:x  hm:x; os:x  U:x; err:x  rW:xx; rG:xx  lin:x; mqtt:x
                                   ttr=target_temp_room   ctr=current_temp_room
                                   ttw=target_temp_water  ctw=current_temp_water
                                   hm=heating_mode        os= operating_status
                                   U=spannung             err=error_code
                                   rW=rssi-Wifi           rG=rssi-GSM
                                   lin=alive              mqtt=On-/Offline

                    Eine SMS wird nur von den in "erlaubteAbsender" eingetragenen Nummern angenommen.

        Es erfolgt keine automatische Rückmeldung über SMS.
        Man sieht nur anhand der MQTT-Meldungen bzw. Print-Ausgaben ob erfolgreich.
        Der Status der InetBox kann mit der Status-SMS angefordert werden.


Die Hauptfunktionen zur SMS-Steuerung sind in den Programmen
  - sim800l.py
  - gsm.py

enthalten.

Zusätzlich wurden zur Integration der Funktion auch die Programme
  - truma_serv.py
  - inetboxapp.py
  - set_credentials_encrypt.py  (erlaubteAbsender, PIN, MainTopic)
  - tools.py
  - conversions.py

angepasst.

Eine gute Einführung in die Anwendung des SIM800L-Moduls wird auf dieser Seite gefunden:
 [SIM800L Modul • Wolles Elektronikkiste](https://wolles-elektronikkiste.de/sim800l-modul)

Für mich *"unnötiges"* wurde aus dem ursprünglichen Code entfernt. (z.B.: Home Assistant )

Mit dem Programm *update_credentials_encrypt.py* kann eine schon vorhandene *credentials.dat* aktualisiert werden,
ohne alle schon vorhandenen Werte neu eingeben zu müssen.
Der schon vorhandene Wert wird angezeigt und kann durch *ENTER* unverändert übernommen werden.



# Kurzanleitung ESP32 TRUMA-LIN

Original siehe [INETBOX_ESP](https://github.com/mc0110/inetbox2mqtt)

## Rahmenbedingung und Einschränkungen

### Anerkennung
Die Software ist eine Ableitung aus dem GITHUB-Projekt [INETBOX](https://github.com/danielfett/inetbox.py) von Daniel Fett.
Ihm und seinem Projekt wie auch den Vorarbeiten von [WoMoLIN](https://github.com/muccc/WomoLIN) ist es geschuldet,
dass diese coolen Projekte möglich geworden sind.

### Elektrik
Dementsprechend sei zu der Verkabelung - Verbindung des LIN-Bus über den TJA1020 zum UART auf die oben genannten Projekte verwiesen.
 Auf dem ESP32 verwende ich den UART2 (tx - GPIO17, rx - GPIO16).

  ![1](https://user-images.githubusercontent.com/65889763/200187420-7c787a62-4b06-4b8d-a50c-1ccb71626118.png)
 Diese sind daher mit dem TJA1020 zu verbinden.
 Es bedarf (dank des internen Aufbaus des TJA1020) keines Level-shifts. Es funktioniert auch auf 3.3V-Pegeln,
 auch wenn der TJA1020 mit 5V betrieben wird.


### Haftungsausschluss
Meine Lösung für den ESP32 wurde bislang nur mit meiner eigenen TRUMA / CPplus Version getestet.
Das LIN-Modul für den ESP32 funktioniert logisch etwas anders als bei Daniels Software,
weil ich bei einer 1-1-Portierung auf dem ESP32 Performanceprobleme hatte.
Dafür hat sich das Modul in der aktuellen Version als sehr stabil und CPplus-verträglich gezeigt.
**Trotzdem sei hier erwähnt, dass ich natürlich keine Gewähr für einen Einsatz übernehme.**

### microPython
Ich war nach den ersten Tests erstaunt, wie gut und mächtig die microPython-Plattform ist.
 Trotzdem oder vielleicht auch deshalb ist es alles sehr schnelllebig.
 So lief (zu meinem Erstaunen) die Software nicht mit einem Kernel aus dem Juli (da war u.a. das bytearray.hex noch nicht mit drin).
Die micropython-MQTT-Packete sind momentan noch experimentell.
Daher kann die aktuelle Software keine MQTT-TLS-Verbindungen aufbauen.

### Topics - fast gleich, aber nicht exakt gleich
Die MQTT-Befehle (set-topics) sind identisch mit den Befehlen bei Daniel.
Mit ihm bin ich so verblieben, dass wir versuchen, die Versionen nicht auseinander laufen zu lassen.
 Allerdings sehen die veröffentlichten Topics etwas anders aus, denn ich habe mir die Freiheit genommen,
 die Logik ein wenig zu ändern. Der ESP32 sendet nur ausgewählte Topics, ich erspare dem MQTT-Server die ganzen Timer,
 checksum, command_counter, etc. Diese sind alle selbsterklärend. Sollte es hierzu Anpassungsbedarf geben, so stehe ich zur Verfügung.
 Das  Timing der Topic-Sends ist auch etwas modifiziert. Der ESP32 sendet die Topics nur,
 wenn sich da etwas geändert hat und das für jedes einzelne Topic. Das ist bei Daniel anders,
 er schreibt immer das ganze Status-Register. Es gibt ein alive-Topic, welches den Status der

### Ändern von Einstellungen

Im Allgemeinen veröffentlichen Sie eine Nachricht an `truma/set/<setting>` (wobei `<setting>` eine der in `truma/control_status/#` veröffentlichten Einstellungen ist)
 mit dem Wert, den Sie setzen wollen. Nach dem Neustart des Dienstes warten Sie etwa eine Minute, bis der erste Satz von Werten veröffentlicht wurde, bevor Sie die Einstellungen ändern.

Zum Beispiel:

```bash
mosquitto_pub -t 'truma/set/target_temp_water' -m '40'
```
oder

```bash
mosquitto_pub -t 'truma/set/target_temp_room' -m '10'; mosquitto_pub -t 'truma/set/heating_mode' -m 'eco'
```


Für bestimmte Einstellungen gibt es einige Besonderheiten:
#### ***`target_temp_room` und `heating_mode` müssen beide aktiviert sein, damit die Heizung funktioniert. Es ist am besten, beide zusammen einzustellen, wie im obigen Beispiel ***
 * `target_temp_room` kann auf 0 gesetzt werden, um die Heizung auszuschalten, und sonst auf 5-30 Grad.
 * `heating_mode` kann auf `off`, `eco` und `high` eingestellt werden und definiert die Lüfterintensität für die Raumheizung.
 * `target_temp_water` muss auf einen der Werte `0` (aus), `40` (entspricht der Auswahl von 'eco' auf dem Display), `60` ('high') oder `200` (boost) eingestellt werden.
 * `energy_mix` und `el_power_level` sollten zusammen eingestellt werden.
 * `energy_mix` kann eines von `none`/`gas`/`electricity`/`mix` sein.
 * `el_power_level` kann auf `0`/`900`/`1800` gesetzt werden, wenn elektrische Heizung oder Mix aktiviert ist




### ESP32-LEDs
Es gibt noch ein weiteres zusätzliches Feature. Da der ESP32 ja so viele GPIOs hat, habe ich zwei LED programmiert.
Die LEDs sind in negativer Logik, also  GPIO ---- Widerstand ----- LED ----- +3.3V anzuschliessen.
GPIO12 zeigt an, wenn die MQTT-Verbindung steht. GPIO14 zeigt an, wenn die Verbindung zur CPplus steht.

### Alive-Topic
Kurzer Exkurs: Die CPplus sendet 0x18-Anfragen (0xD8 mit Parity) nur, wenn eine INETBOX registriert ist.
 Dies erkennt man u.a. an dem dritten Eintrag im Index. Der ESP32 beantwortet diese Anfragen.
 Nur wenn er 0x18-Meldungen empfängt, steht die Verbindung zur CPplus und hat die Registrierung funktioniert.
 Damit lässt es sich leicht herausfinden, ob man ggf. ein elektrisches Problem hat.
 Leuchtet die LED, ist die Kommunikation mit der CPplus gegeben.
 Der ESP32 gibt dies auch als spezielles "alive"-Topic über die MQTT-Verbindung aus.
 Dies erfolgt ca. alle 60sek. Verbindung okay, payload: ON, Verbindung nicht okay, payload: OFF

## Installationsanleitung
### Quick-Start
Das Bin-File enthält sowohl das Python als auch die py-Dateien!
Damit lässt sich das ganze Projekt in einem Zug auf den ESP32 flashen.
 Dafür muss esptool natürlich installiert sein. Bei mir findet das Tool auch schon den seriellen Port des ESPs automatisch.
 Ansonsten kann der Port natürlich mit vorgegeben werden. Der ESP muss sich im Programmiermodus (GPIO0 auf Masse beim Starten) befinden.
 Kommando ist: *esptool  write_flash 0 flash_dump_esp32_lin_v08_4M.bin*

Nach dem Flashen bitte den Chip rebooten und mit einem seriellen Terminal (miniterm, putty, serialport) verbinden (Baudrate: 115700).

Der Chip meldet sich dann und es werden die Credentials abgefragt. Diese werden dann in eine Datei geschrieben
 und der Vorgang muss nicht wiederholt werden.
 Also nur Wifi-SSID und Passwort sowie IP des MQTT-Servers und Username, PW eingeben.
Die Eingaben werden dann nochmals angezeigt und die Abfrage wiederholt, bis man diese mit ***yes*** bestätigt hat.



Für diese ersten Schritte braucht der ESP32 nicht an die CPplus angeschlossen zu sein.
 Wenn alles geklappt hat, sollte sich danach der ESP32 mit dem MQTT-Server verbinden -> Bestätigungsmeldung: connected

Danach stellt man die Verbindung zum LIN-Bus her. Diese Verbindung ist unkritisch,
kann jederzeit getrennt und danach wieder hergestellt werden. Es sollte dazu auch keine erneute Initialisierung der CPplus notwendig sein.

### IDE und Weiterentwicklung der .py
Alternativ können natürlich die *.py-Sources* verwendet werden. Hierzu kann ich die [Thonny IDE](https://thonny.org/) empfehlen.
 Wenn es auch zu PyCharm eine microPython-Erweiterung gibt, so ist das Ergebnis meilenweit weniger alltagstauglich, als das derThonny-IDE.
 Zumindest bei mir hat sich Thonny bewährt.
 Die IDE ist auf allen Plattformen (Win, Mac, Linux) verfügbar und kann auch verschiedene Ports (ESP8266, ESP32, RP2) bedienen.

#### Vorbereitung - Installation microPython
Als erstes muss Python auf dem Chip installiert werden. Auch dabei hilft Thonny.
 Man kann eine entsprechende microPython-Version direkt aus der IDE (Menüpunkt RUN, Configure Interpreter) heraus auf den Chip flashen.

#### PY-Dateien auf den Chip flashen
Als nächsten Schritt packt man die PY-Dateien auf den ESP32.
 In Thonny muss man dazu im Computer-Verzeichnis das richtige Verzeichnis selektieren.
 Mit dem "rechte Maustaste" Menü kann man dann die selektierten Dateien ***UPLOADEN***

#### Ausführen der Dateien
Ein Programmabbruch funktioniert mit Ctrl-C. Da die Dateien so aufgesetzt sind, dass nach dem Booten das Programm direkt startet,
 muss zunächst das Programm unterbrochen werden. Das erfolgt mit ctrl-C. Danach hat man mit Thonny die volle Kontrolle und kann die Dateien ändern, speichern und ausführen

-------------------------
https://www.micropython.org/
https://awesome-micropython.com/
