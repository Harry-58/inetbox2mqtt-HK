# Crypto-Class for Strings with bonding the key with the machine.unique_id
#
#
# This modules are using the machine_unique_number for encrypt / decrypt
# So the data is only on the target-system usable
# based on ESP32 Micropython implementation of cryptographic
#
# reference:
# https://pycryptodome.readthedocs.io/en/latest/src/cipher/classic.html#cbc-mode
# https://docs.micropython.org/en/latest/library/ucryptolib.html

import os
from ucryptolib import aes
import machine


class crypto:
    __BLOCK_SIZE = 32
    __IV_SIZE = 16
    __MODE_CBC = 2

    def buildKey():
        key1 = machine.unique_id()
        key = bytearray(b'I_am_32bytes=256bits_key_padding')
        for i in range(len(key1)-1):
            key[i] = key1[i]
            key[len(key)-i-1] = key1[i]
        return key

    def encrypt(text):
        key = crypto.buildKey()
        # Generate iv with HW random generator
        iv = os.urandom(crypto.__IV_SIZE)
        cipher = aes(key, crypto.__MODE_CBC, iv)
        # Padding plain text with space
        pad = crypto.__BLOCK_SIZE - len(text) % crypto.__BLOCK_SIZE
        text = text + " "*pad
        ct_bytes = iv + cipher.encrypt(text)
        return ct_bytes

    # you need only one of this modules
    def decrypt(enc_bytes):
        key = crypto.buildKey()
        # Generate iv with HW random generator
        iv = enc_bytes[:crypto.__IV_SIZE]
        cipher = aes(key, crypto.__MODE_CBC, iv)
        return cipher.decrypt(enc_bytes)[crypto.__IV_SIZE:].strip()


class fn_crypto:
    # cryptoFile = None
    # def __init__(self, cryptoFileName):
    #    _cryptoFileName = cryptoFileName
    #    cryptoFile = open(self._cryptoFileName, "wb")
    #
    # def __del__(self):
    #    cryptoFile.close()

    def __init__(self):
        pass

    def fn_write_encrypt(self, f, x):
        cip = crypto
        x = cip.encrypt(x)
        f.write(len(x).to_bytes(2, 'little'))
        f.write(x)

    def fn_write_eof_encrypt(self, f):
        x = 0
        f.write(x.to_bytes(2, 'little'))

    def fn_read_decrypt(self, f):
        cip = crypto
        x = int.from_bytes(f.read(2), "little")
        if x > 0:
            return str(cip.decrypt(f.read(x)), 'utf-8')
        else:
            return ""

    def fn_read_str_decrypt(self, f, x):
        cip = crypto()
        return str(cip.decrypt(f.read(x)), 'utf-8')

    def get_decrypt_key(self, fn, key):
        f = open(fn, "rb")
        s = self.fn_read_decrypt(f)
        while s != "":
            if s.find(key) > -1:
                f.close()
                return str(s[s.find(":")+1:], 'utf-8')
            s = self.fn_read_decrypt(f)
        f.close()
        print('Err in crypto_keys: key not found')
        return ''
