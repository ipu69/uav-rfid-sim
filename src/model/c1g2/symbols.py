from enum import Enum
import numpy as np
import binascii
import collections


class DR(Enum):
    DR_8 = 0
    DR_643 = 1

    @staticmethod
    def encode(dr):
        return str(dr.value)

    @property
    def ratio(self):
        return 8.0 if self == DR.DR_8 else 64.0 / 3

    @staticmethod
    def deserialize(s):
        if s == '8':
            return DR.DR_8
        elif s == '64/3':
            return DR.DR_643
        raise ValueError(f'unrecognized DR "{s}"')

    @staticmethod
    def str(value):
        if value == DR.DR_8:
            return '8'
        if value == DR.DR_643:
            return '64/3'
        raise ValueError(f'unrecognized DR "{value}"')


class TagEncoding(Enum):
    FM0 = 1
    M2 = 2
    M4 = 4
    M8 = 8

    @staticmethod
    def encode(m):
        return format(int(np.log2(m.value)), '02b')

    @staticmethod
    def deserialize(s):
        s = str(s).upper()
        if s in {'1', 'FM0'}:
            return TagEncoding.FM0
        elif s in {'2', 'M2'}:
            return TagEncoding.M2
        elif s in {'4', 'M4'}:
            return TagEncoding.M4
        elif s in {'8', 'M8'}:
            return TagEncoding.M8
        raise ValueError(f'unrecognized TagEncoding = "{s}"')


class Bank(Enum):
    RESERVED = 0
    EPC = 1
    TID = 2
    USER = 3

    @staticmethod
    def encode(bank):
        return format(bank.value, '02b')

    @staticmethod
    def deserialize(s):
        s = s.upper()
        if s == 'RESERVED':
            return Bank.RESERVED
        elif s == 'EPC':
            return Bank.EPC
        elif s == 'TID':
            return Bank.TID
        elif s == 'USER':
            return Bank.USER
        raise ValueError(f'unrecognized Bank = "{s}"')


class InventoryFlag(Enum):
    A = 0
    B = 1

    @staticmethod
    def encode(flag):
        return str(flag.value)

    def invert(self):
        return InventoryFlag.A if self == InventoryFlag.B else InventoryFlag.B

    @staticmethod
    def deserialize(s):
        s = s.upper()
        if s == 'A':
            return InventoryFlag.A
        elif s == 'B':
            return InventoryFlag.B
        raise ValueError(f'unrecognized InventoryFlag = "{s}"')


class Sel(Enum):
    SL_ALL = 0
    SL_NO = 2
    SL_YES = 3

    @staticmethod
    def encode(field):
        return format(field.value, '02b')

    @staticmethod
    def deserialize(s):
        s = s.upper()
        if s == 'ALL':
            return Sel.SL_ALL
        elif s == 'YES' or s == 'SEL':
            return Sel.SL_YES
        elif s == 'NO' or s == '~SEL':
            return Sel.SL_NO
        raise ValueError(f'unrecognized Sel = "{s}"')


class Session(Enum):
    S0 = 0
    S1 = 1
    S2 = 2
    S3 = 3

    @staticmethod
    def encode(session):
        return format(session.value, '02b')

    @staticmethod
    def deserialize(s):
        s = str(s).upper()
        if s == '0' or s == 'S0':
            return Session.S0
        elif s == '1' or s == 'S1':
            return Session.S1
        elif s == '2' or s == 'S2':
            return Session.S2
        elif s == '3' or s == 'S3':
            return Session.S3
        raise ValueError(f'unrecognized Session = "{s}"')


def encode_ebv(value, first_block=True):
    prefix = '0' if first_block else '1'
    if value < 128:
        return prefix + format(value, '07b')
    else:
        return encode_ebv(value >> 7, first_block=False) + \
               encode_ebv(value % 128, first_block=first_block)


class CommandCode(Enum):
    QUERY = 16
    QUERY_REP = 0
    ACK = 1
    REQ_RN = 193
    READ = 194

    @staticmethod
    def encode(code):
        if code == CommandCode.QUERY:
            return '1000'
        if code == CommandCode.QUERY_REP:
            return '00'
        if code == CommandCode.ACK:
            return '01'
        if code == CommandCode.REQ_RN:
            return '11000001'
        if code == CommandCode.READ:
            return '11000010'
        raise ValueError(f'unsupported command code "{code}"')

    @staticmethod
    def get_name_for(code):
        if code == CommandCode.QUERY:
            return 'Query'
        if code == CommandCode.QUERY_REP:
            return 'QueryRep'
        if code == CommandCode.ACK:
            return 'ACK'
        if code == CommandCode.REQ_RN:
            return 'ReqRn'
        if code == CommandCode.READ:
            return 'Read'
        raise ValueError(f'unsupported command code "{code}"')


def encode(value, width=0, use_ebv=False):
    tv = type(value)
    if tv in {DR, TagEncoding, Bank, InventoryFlag, Sel, Session, CommandCode}:
        return tv.encode(value)

    if tv == bool:
        return '1' if value else '0'

    elif tv == int:
        if use_ebv:
            return encode_ebv(value)
        elif width > 0:
            return format(value, "0{width}b".format(width=width))
        return format(value, "b")

    elif tv == str:
        return encode(list(binascii.unhexlify(value.strip())))

    elif tv == bytes:
        return encode(list(value))

    elif isinstance(value, collections.Iterable):
        return "".join(format(x, "08b") for x in value)

    raise ValueError(f'unsupported field type "{tv}"')


def min_t1(rtcal, blf, frt=0.1):
    return max(rtcal, 10.0 / blf) * (1. - frt) - 2e-6


def nominal_t1(rtcal, blf):
    return max(rtcal, 10 / blf)


def max_t1(rtcal, blf, frt=0.1):
    return max(rtcal, 10.0 / blf) * (1. + frt) + 2e-6


def min_t2(blf):
    return 3. / blf


def max_t2(blf):
    return 20. / blf


def t3():
    return 0.


def t4(rtcal):
    return 2. * rtcal


def get_blf(dr, trcal):
    return dr.ratio / trcal
