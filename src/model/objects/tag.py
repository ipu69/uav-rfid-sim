from collections import namedtuple
from dataclasses import dataclass, field
from typing import Optional, NamedTuple, Tuple

import numpy as np

from model.c1g2.commands import ReaderFrame
from model.c1g2.replies import TagPreamble, TagFrame, RN16, EPC, Handle, Data
from model.c1g2.symbols import TagEncoding, DR, get_blf, nominal_t1
from model.objects.reader import ReaderSpec

RepliesVector = namedtuple('RepliesVector', ('rn16', 'epcid', 'handle', 'data'))


class TagSpec(NamedTuple):
    position: Tuple[float, float, float] = (0, 0, 0)
    sensitivity: float = -18.0
    epcid_wordcnt: int = 6
    modulation_loss: int = -10.0  # dBm


def rand_hex_str(n):
    return ''.join(f"{x:X}" for x in np.random.randint(0, 0x10, n))


@dataclass
class Tag:
    OFF = 0
    READY = 1
    ARBITRATE = 2
    REPLY = 3
    ACKNOWLEDGED = 4
    # OPEN = 5
    # SECURED = 6
    # KILLED = 7

    # Initialized from parameters:
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    sensitivity: float = -18.0
    data_wordcnt: int = 4
    epcid_wordcnt: int = 6
    m: TagEncoding = TagEncoding.FM0
    trext: bool = False
    rtcal: float = 15.00e-6
    trcal: float = 20.0e-6
    dr: DR = DR.DR_8
    q: int = 4
    modulation_loss: float = -10.0  # dBm

    # Variables:
    state: int = field(default=0, init=False)
    counter: int = field(default=0xFFFF, init=False)
    tx_frame: Optional[TagFrame] = field(init=False, default=None)
    rx_frame: Optional[ReaderFrame] = field(init=False, default=None)
    tx_ends_at: float = field(init=False, default=0.0)
    rx_ends_at: float = field(init=False, default=0.0)

    # Event IDs:
    tx_start_event_id: int = field(init=False, default=-1)
    tx_end_event_id: int = field(init=False, default=-1)
    rx_end_event_id: int = field(init=False, default=-1)

    # Statistics and counters:
    num_epcid_sent: int = field(init=False, default=0)
    num_epcid_received: int = field(init=False, default=0)
    num_data_sent: int = field(init=False, default=0)
    num_data_received: int = field(init=False, default=0)

    # Derived:
    epc: str = field(init=False)
    data: str = field(init=False)
    t1: float = field(init=False)
    num_slots: int = field(init=False)
    replies: RepliesVector = field(init=False)

    def __post_init__(self):
        self.epc = rand_hex_str(self.epcid_wordcnt * 4)
        self.data = rand_hex_str(self.data_wordcnt * 4)

        blf = get_blf(self.dr, self.trcal)
        self.t1 = nominal_t1(self.rtcal, blf)

        self.num_slots = 2 ** self.q

        preamble = TagPreamble(self.m, self.trext, blf)
        self.replies = RepliesVector(
            rn16=TagFrame(preamble, RN16()),
            epcid=TagFrame(preamble, EPC(self.epc)),
            handle=TagFrame(preamble, Handle()),
            data=TagFrame(preamble, Data(self.data))
        )

    @staticmethod
    def str_state(state):
        if state == Tag.OFF:
            return "OFF"
        if state == Tag.READY:
            return "READY"
        if state == Tag.ARBITRATE:
            return "ARBITRATE"
        if state == Tag.REPLY:
            return "REPLY"
        if state == Tag.ACKNOWLEDGED:
            return "ACKNOWLEDGED"
        raise ValueError(f'unrecognized tag state {state}')

    @property
    def powered(self):
        return self.state != Tag.OFF


def create_tag(tag_spec: TagSpec, reader_spec: ReaderSpec):
    if isinstance(tag_spec, TagSpec):
        return Tag(
            position=np.asarray(tag_spec.position),
            sensitivity=tag_spec.sensitivity,
            epcid_wordcnt=tag_spec.epcid_wordcnt,
            modulation_loss=tag_spec.modulation_loss,

            data_wordcnt=reader_spec.wordcnt,
            m=TagEncoding.deserialize(reader_spec.M),
            trext=reader_spec.trext,
            rtcal=reader_spec.rtcal,
            trcal=reader_spec.trcal,
            dr=DR.deserialize(reader_spec.dr),
            q=reader_spec.Q,
        )
    raise TypeError(f"unsupported tag spec. type {type(tag_spec)}")
