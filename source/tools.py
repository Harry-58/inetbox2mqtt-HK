from machine import Pin

# this routine isn't nessecary - see bytes.hex(" ")
def format_bytes(bytestring):
    return " ".join("{:02x}".format(c) for c in bytestring)


def calculate_checksum(bytestring):
    # The checksum contains the inverted eight bit sum with carry over all data bytes or all data bytes and the protected identifier.
    cs = 0
    for b in bytestring:
        cs = (cs + b) % 0xFF

    cs = ~cs & 0xFF
    if cs == 0xFF:
        cs = 0
    return cs


PIN_MAP = {
    "MQTT": 5,
    "D8": 23,
    "GSM": 19
}


# D8 is misleading, because the raw-PID is 0xD8, but the correct PID is "0x18"
def set_led(s, b):
    p = Pin(PIN_MAP[s], Pin.OUT)
    if b:
        p.value(1)    #Status gedreht, da bei mir gegen Masse angeschlossen
    else:
        p.value(0)    #Status gedreht, da bei mir gegen Masse angeschlossen

def get_led(s):
    p = Pin(PIN_MAP[s], Pin.OUT)
    return p.value()

def toggle_led(s):
    p = Pin(PIN_MAP[s], Pin.OUT)
    p.value(not (p.value()))


def dtoggle_led(s):
    p = Pin(PIN_MAP[s], Pin.OUT)
    p.value(not (p.value()))  # ??? What is this function supposed to do? Two times "NOT" results in "YES", which does not change the LED status!
    p.value(not (p.value()))



def get_gpio(p, i):
    if i:
        p0 = Pin(p, Pin.IN, Pin.PULL_UP)
    else:
        p0 = Pin(p, Pin.IN, Pin.PULL_DOWN)
    v = (p0.value() != i)
#    print("check pin", p, " inv: ", i, " Val: ", v)
    return v

# pin, inverted, value ("ON", "OFF")


def set_gpio(p, i, v):
    p0 = Pin(p, Pin.OUT)
    v = (v != i)
    p0.value(v)
#    print("set pin", p, " inv: ", i, " to: ", v)
