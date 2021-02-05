from typing import Tuple

from .symbols import DR, TagEncoding, Bank, InventoryFlag, Sel, Session, encode, \
    CommandCode


# noinspection PyUnresolvedReferences
class ReaderSync:
    def __init__(self, tari: float, rtcal: float, delim: float = 12.5e-6):
        self.__tari = tari
        self.__rtcal = rtcal
        self.__delim = delim
        # Derived values:
        self.__data1 = rtcal - tari
        self.__str = self._get_str()
        self.__duration = self._get_duration()

    @property
    def delim(self) -> float:
        return self.__delim

    @property
    def rtcal(self) -> float:
        return self.__rtcal

    @property
    def tari(self) -> float:
        return self.__tari

    @property
    def data0(self) -> float:
        return self.__tari

    @property
    def data1(self) -> float:
        return self.__data1

    @property
    def duration(self) -> float:
        return self.__duration

    def _get_duration(self) -> float:
        return self.delim + self.tari + self.rtcal

    def _get_str(self) -> str:
        return f"SYNC{{delim={self.delim * 1e6:.2f}us " \
               f"tari={self.tari*1e6:.2f}us rtcal={self.rtcal*1e6:.2f}us}}"

    def __str__(self) -> str:
        return self.__str


class ReaderPreamble(ReaderSync):
    def __init__(
            self,
            tari: float,
            rtcal: float,
            trcal: float,
            delim: float = 12.5e-6
    ):
        self.__trcal = trcal
        super().__init__(tari, rtcal, delim)

    @property
    def trcal(self):
        return self.__trcal

    def _get_duration(self) -> float:
        return self.delim + self.tari + self.rtcal + self.trcal

    def _get_str(self) -> str:
        return f"PREAMBLE{{delim={self.delim * 1e6:.2f}us " \
               f"tari={self.tari*1e6:.2f}us rtcal={self.rtcal*1e6:.2f}us" \
               f"trcal={self.trcal*1e6:.2f}us}}"


class Command:
    def __init__(self, code: CommandCode):
        self.__code = code
        self.__name = CommandCode.get_name_for(code)
        self.__encoded = CommandCode.encode(code) + self._encode_body()
        self.__bitlen = len(self.__encoded)
        self.__str = f'{self.__name}[{self._str_body()} | {self.__encoded}]'
        self.__bits_count = tuple(
            len([x for x in self.__encoded if x == b]) for b in '01'
        )

    @property
    def code(self) -> CommandCode:
        raise self.__code

    @property
    def name(self) -> str:
        return self.__name

    @property
    def encoded(self) -> str:
        return self.__encoded

    @property
    def bitlen(self) -> int:
        return self.__bitlen

    @property
    def bits_count(self) -> Tuple[int]:
        return self.__bits_count

    def _encode_body(self) -> str:
        raise NotImplementedError()

    def _str_body(self) -> str:
        raise NotImplementedError()

    def __str__(self) -> str:
        return self.__str


class Query(Command):
    def __init__(
            self,
            q: int,
            m: TagEncoding,
            dr: DR = DR.DR_8,
            trext: bool = False,
            sel: Sel = Sel.SL_ALL,
            session: Session = Session.S0,
            target: InventoryFlag = InventoryFlag.A,
            crc5: int = 0x00
    ):
        self.__dr = dr
        self.__m = m
        self.__trext = trext
        self.__sel = sel
        self.__session = session
        self.__target = target
        self.__q = q
        self.__crc5 = crc5
        super().__init__(CommandCode.QUERY)

    @property
    def q(self) -> int:
        return self.__q

    @property
    def m(self) -> TagEncoding:
        return self.__m

    @property
    def dr(self) -> DR:
        return self.__dr

    @property
    def trext(self) -> bool:
        return self.__trext

    @property
    def sel(self) -> Sel:
        return self.__sel

    @property
    def session(self) -> Session:
        return self.__session

    @property
    def target(self) -> InventoryFlag:
        return self.__target

    @property
    def crc5(self) -> int:
        return self.__crc5

    def _encode_body(self) -> str:
        return encode(self.dr) + encode(self.m) + encode(self.trext) + \
               encode(self.sel) + encode(self.session) + \
               encode(self.target) + encode(self.q, width=4) + \
               encode(self.crc5, width=5)

    def _str_body(self) -> str:
        return (
            f"Q:{self.q} M:{self.m.name} DR:{DR.str(self.dr)} "
            f"TRext:{1 if self.trext else 0} Session:{self.session.name} "
            f"Sel:{self.sel.name} Target:{self.target.name} CRC5:{self.crc5}"
        )


class QueryRep(Command):
    def __init__(self, session: Session):
        self.__session = session
        super().__init__(CommandCode.QUERY_REP)

    @property
    def session(self) -> Session:
        return self.__session

    def _encode_body(self) -> str:
        return encode(self.session)

    def _str_body(self) -> str:
        return f"Session:{self.__session.name}"


class Ack(Command):
    def __init__(self, rn: int = 0xAAAA):
        self.__rn = rn
        super().__init__(CommandCode.ACK)

    @property
    def rn(self) -> int:
        return self.__rn

    def _encode_body(self) -> str:
        return encode(self.rn, width=16)

    def _str_body(self) -> str:
        return f"RN:{self.rn:04X}"


class ReqRn(Command):
    def __init__(self, rn: int = 0xAAAA, crc16: int = 0xAAAA):
        self.__rn = rn
        self.__crc16 = crc16
        super().__init__(CommandCode.REQ_RN)

    @property
    def rn(self) -> int:
        return self.__rn

    @property
    def crc16(self) -> int:
        return self.__crc16

    def _encode_body(self) -> str:
        return encode(self.rn, width=16) + encode(self.crc16, width=16)

    def _str_body(self) -> str:
        return f"RN:{self.rn:04X} CRC:{self.crc16:04X}"


class Read(Command):
    def __init__(
            self,
            bank: Bank = Bank.USER,
            wordptr: int = 0,
            wordcnt: int = 4,
            rn: int = 0xAAAA,
            crc16: int = 0xAAAA
    ):
        self.__bank = bank
        self.__wordptr = wordptr
        self.__wordcnt = wordcnt
        self.__rn = rn
        self.__crc16 = crc16
        super().__init__(CommandCode.READ)

    @property
    def bank(self) -> Bank:
        return self.__bank

    @property
    def wordptr(self) -> int:
        return self.__wordptr

    @property
    def wordcnt(self) -> int:
        return self.__wordcnt

    @property
    def rn(self) -> int:
        return self.__rn

    @property
    def crc16(self) -> int:
        return self.__crc16

    def _encode_body(self) -> str:
        return (encode(self.bank) + encode(self.wordptr, use_ebv=True) +
                encode(self.wordcnt, width=8) + encode(self.rn, width=16) +
                encode(self.crc16, width=16))

    def _str_body(self) -> str:
        return f"Bank:{self.bank.name} WordPtr:{self.wordptr:X} " \
               f"WordCnt:{self.wordcnt} RN:{self.rn:04X} CRC:{self.crc16:04X}"


class ReaderFrame:
    def __init__(self, preamble: ReaderSync, command: Command):
        self.__command = command
        self.__preamble = preamble
        # Derived values:
        bits_cnt = command.bits_count
        self.__duration = (
                    preamble.duration +
                    preamble.data0 * bits_cnt[0] +
                    preamble.data1 * bits_cnt[1]
        )
        self.__str = f"Frame{{P:{preamble}; C:{command}}}"

    @property
    def command(self):
        return self.__command

    @property
    def preamble(self):
        return self.__preamble

    @property
    def duration(self):
        return self.__duration

    def __str__(self):
        return self.__str
