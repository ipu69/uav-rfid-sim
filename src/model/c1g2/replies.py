from collections import Iterable

from .symbols import encode, TagEncoding

DEFAULT_EPC = 'A5' * 12


class Reply(object):
    def __init__(self, name: str):
        self.__name = name
        self.__encoded = self._encode()
        self.__bitlen = len(self.__encoded)
        self.__str = f'{name}[{self._str_body()}]'

    @property
    def encoded(self) -> str:
        return self.__encoded

    @property
    def bitlen(self) -> int:
        return self.__bitlen

    @property
    def name(self) -> str:
        return self.__name

    def _encode(self) -> str:
        raise NotImplementedError()

    def _str_body(self) -> str:
        raise NotImplementedError()

    def __str__(self):
        return self.__str


class RN16(Reply):
    def __init__(self, rn: int = 0xAAAA):
        self.__rn = rn
        super().__init__('RN16')

    @property
    def rn(self) -> int:
        return self.__rn

    def _encode(self) -> str:
        return encode(self.rn, width=16)

    def _str_body(self) -> str:
        return f"RN:{self.rn:04X}"


class EPC(Reply):
    def __init__(
            self,
            epc: str = DEFAULT_EPC,
            pc: int = 0x0000,
            crc16: int = 0x0000
    ):
        self.__epc = epc
        self.__pc = pc
        self.__crc16 = crc16
        super().__init__('EPCID')

    @property
    def epc(self) -> str:
        return self.__epc

    @property
    def pc(self) -> int:
        return self.__pc

    @property
    def crc16(self) -> int:
        return self.__crc16

    def _encode(self) -> str:
        return encode(self.pc, width=16) + encode(self.epc) + \
               encode(self.crc16, width=16)

    def _str_body(self) -> str:
        if isinstance(self.epc, Iterable) \
                and not isinstance(self.epc, str):
            epc = "".join([format(x, '02X') for x in self.epc])
        else:
            epc = self.epc
        return f"PC:{self.pc:04X} PEC:{epc} CRC:{self.crc16:04X}}}"


class Handle(Reply):
    def __init__(self, rn: int = 0xAAAA, crc16: int = 0x0000):
        self.__rn = rn
        self.__crc16 = crc16
        super().__init__('HANDLE')

    @property
    def rn(self) -> int:
        return self.__rn

    @property
    def crc16(self) -> int:
        return self.__crc16

    def _encode(self) -> str:
        return encode(self.rn, width=16) + encode(self.crc16, width=16)

    def _str_body(self) -> str:
        return f"RN:{self.rn:04X} CRC:{self.crc16:04X}}}"


class Data(Reply):
    def __init__(
            self,
            words: str = 'ABCD' * 4,
            rn: int = 0,
            crc16: int = 0,
            header: int = 0
    ):
        self.__header = header
        self.__words = words
        self.__rn = rn
        self.__crc16 = crc16
        super().__init__('DATA')

    @property
    def words(self) -> str:
        return self.__words

    @property
    def header(self) -> int:
        return self.__header

    @property
    def rn(self) -> int:
        return self.__rn

    @property
    def crc16(self) -> int:
        return self.__crc16

    def _encode(self) -> str:
        return encode(self.header, width=1) + encode(self.words) + \
               encode(self.rn, width=16) + \
               encode(self.crc16, width=16)

    def _str_body(self) -> str:
        if isinstance(self.words, str):
            words = self.words
        else:
            words = "".join([format(x, '02X') for x in self.words])
        return f"H:{self.header:01X} Words:{self.words} " \
               f"RN:{self.rn:04X} CRC:{self.crc16}"


class TagPreamble:
    def __init__(self, m: TagEncoding, trext: bool, blf: float):
        self.__m = m
        self.__trext = trext
        self.__blf = blf
        # Derived:
        if m == TagEncoding.FM0:
            bits = '1010v1' if not trext else '0000000000001010v1'
        elif trext:
            bits = '0000000000000000010111'
        else:
            bits = '0000010111'
        bitlen = len(bits)
        self.__bits = bits
        self.__bitlen = bitlen
        self.__duration = bitlen * (m.value / blf)

    @property
    def m(self):
        return self.__m

    @property
    def trext(self):
        return self.__trext

    @property
    def blf(self):
        return self.__blf

    @property
    def encoded(self) -> str:
        return self.__bits

    @property
    def bitlen(self) -> int:
        return self.__bitlen

    @property
    def duration(self) -> float:
        return self.__duration

    def __str__(self) -> str:
        return self.__bits


class TagFrame(object):
    def __init__(
            self,
            preamble: TagPreamble,
            reply: Reply
    ):
        self.__preamble = preamble
        # Derived values:
        self.__reply = reply
        self.__encoded = f'{self.__preamble.encoded}{reply.encoded}e'
        self.__bitlen = len(self.__encoded)
        self.__duration = self.__bitlen * (preamble.m.value / preamble.blf)
        self.__str = f"TagFrame{{P:{self.__preamble}; R:{self.__reply}}}"

    @property
    def preamble(self) -> TagPreamble:
        return self.__preamble

    @property
    def reply(self) -> Reply:
        return self.__reply

    @property
    def encoded(self) -> str:
        return self.__encoded

    @property
    def bitlen(self) -> int:
        return self.__bitlen

    @property
    def duration(self) -> float:
        return self.__duration

    def __str__(self) -> str:
        return self.__str
