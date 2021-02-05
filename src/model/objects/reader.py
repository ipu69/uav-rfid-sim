from collections import namedtuple
from dataclasses import field, dataclass
from typing import Optional, List, NamedTuple, Tuple, Union

import numpy as np

from model.c1g2.commands import ReaderPreamble, ReaderSync, ReaderFrame, Query, \
    QueryRep, Ack, ReqRn, Read
from model.c1g2.replies import TagFrame, RN16, EPC, Handle, Data
from model.c1g2.symbols import TagEncoding, Session, InventoryFlag, get_blf, \
    t3, Bank, Sel, DR, max_t1


class ReaderSpec(NamedTuple):
    position: Tuple[float, float, float] = (0, 0, 10.0)
    speed: Tuple[float, float, float] = (1.0, 0, 0)
    Q: int = 2
    M: Union[str, int] = "M2"
    sel: str = "All"
    trext: bool = False
    dr: str = '64/3'
    tari: float = 6.25e-6
    rtcal: float = 15.0e-6
    trcal: float = 20.0e-6
    session: str = 'S0'
    target: str = 'A'
    wordcnt: int = 4
    tx_power: float = 31.5  # dBm
    circulator_noise: float = -80.0  # dBm


CommandsVector = namedtuple('CommandsVector', (
    'query', 'query_rep', 'ack', 'req_rn', 'read'
))


@dataclass
class RxOp:
    frame: TagFrame
    started_at: float
    finish_at: float
    broken: bool = False


@dataclass
class Reader:
    IDLE = 0
    RX = 1
    TX = 2

    # Initialized from parameters:
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    speed: np.ndarray = field(default_factory=lambda: np.asarray((1., 0, 0)))
    q: int = 2
    m: TagEncoding = TagEncoding.M2
    sel: Sel = Sel.SL_ALL
    trext: bool = False
    dr: DR = DR.DR_8
    tari: float = 6.25e-6
    rtcal: float = 15.0e-6
    trcal: float = 20.0e-6
    session: Session = Session.S0
    target: InventoryFlag = InventoryFlag.A
    wordcnt: int = 4  # number of words to read
    tx_power: float = 31.5
    circulator_noise: float = -80.0  # dBm

    # Logical (inventory round) variables:
    state: int = field(init=False, default=0)
    slot: int = field(init=False, default=0)
    position_updated_at: float = field(init=False, default=0.0)
    num_rounds: int = field(init=False, default=0)

    # Phy layer:
    tx_frame: Optional[object] = field(init=False, default=None)
    rxops: List[object] = field(init=False, default_factory=list)
    rx_ends_at: float = field(init=False, default=0.0)
    tx_ends_at: float = field(init=False, default=0.0)

    # Events IDs:
    end_of_tx_event_id: int = field(init=False, default=-1)
    end_of_rx_event_id: int = field(init=False, default=-1)
    no_reply_event_id: int = field(init=False, default=-1)

    # Cached values, computed after init:
    blf: float = field(init=False, default=0.0)
    inter_command_interval: float = field(init=False, default=0.0)
    num_slots: float = field(init=False, default=0)
    commands: CommandsVector = field(init=False)

    def __post_init__(self):
        self.blf = get_blf(self.dr, self.trcal)
        self.inter_command_interval = max_t1(self.rtcal, self.blf) + t3()
        self.num_slots = 2 ** self.q

        preamble = ReaderPreamble(self.tari, self.rtcal, self.trcal)
        sync = ReaderSync(self.tari, self.rtcal)

        # Initiate commands, so they are ready to use in handlers:
        self.commands = CommandsVector(
            query=ReaderFrame(
                preamble, Query(self.q, self.m, self.dr, self.trext, self.sel,
                                self.session, self.target)),
            query_rep=ReaderFrame(sync, QueryRep(self.session)),
            ack=ReaderFrame(sync, Ack()),
            req_rn=ReaderFrame(sync, ReqRn()),
            read=ReaderFrame(sync, Read(Bank.USER, 0, self.wordcnt)),
        )

    def update_position(self, time: float):
        self.position += self.speed * (time - self.position_updated_at)
        self.position_updated_at = time

    def get_next_command(self, reply) -> (bool, ReaderFrame):
        rt = type(reply)
        if rt is RN16:
            return False, self.commands.ack
        if rt is EPC:
            return False, self.commands.req_rn
        elif rt is Handle:
            return False, self.commands.read
        elif rt is Data:
            if self.slot >= self.num_slots:
                return True, None
            return False, self.commands.query_rep
        raise ValueError(f"unexpected reply {reply}")

    def start_round(self):
        assert self.state == Reader.IDLE, f'state = {Reader.str_state(self.state)}, tx_frame = {self.tx_frame}, rxops = {self.rxops}, slot = {self.slot}'
        self.slot = 1
        self.num_rounds += 1

    def start_slot(self):
        assert self.slot < self.num_slots
        self.slot += 1

    def has_next_slot(self):
        return self.slot < self.num_slots

    @staticmethod
    def str_state(state):
        if state == Reader.IDLE:
            return "IDLE"
        if state == Reader.TX:
            return "TX"
        if state == Reader.RX:
            return "RX"
        raise ValueError(f"unrecognized reader state = {state}")


def create_reader(spec):
    if isinstance(spec, ReaderSpec):
        return Reader(
            position=np.asarray(spec.position, dtype=float),
            speed=np.asarray(spec.speed),
            q=spec.Q,
            m=TagEncoding.deserialize(spec.M),
            sel=Sel.deserialize(spec.sel),
            trext=spec.trext,
            dr=DR.deserialize(spec.dr),
            tari=spec.tari,
            rtcal=spec.rtcal,
            trcal=spec.trcal,
            session=Session.deserialize(spec.session),
            target=InventoryFlag.deserialize(spec.target),
            wordcnt=spec.wordcnt,
            tx_power=spec.tx_power,
            circulator_noise=spec.circulator_noise,
        )
    raise TypeError(f"unsupported reader spec. type {type(spec)}")
