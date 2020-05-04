from enum import Enum
from math import pi, cos, sin
from random import randint, random

from numpy import asarray

from pysim import events
from pysim.des import DESModel
from pysim.protocol import Query, TagEncoding, DR, Session, InventoryFlag, Sel, \
    ReaderFrame, QueryRep, Ack, QueryReply, get_blf, min_t1, t3, AckReply, \
    TagFrame
from pysim.utils import count_distance


SPEED_OF_LIGHT = 299792458


class TagState(Enum):
    OFF = 0
    READY = 1
    ARBITRATE = 2
    REPLY = 3
    ACKNOWLEDGED = 4
    OPEN = 5
    SECURED = 6
    KILLED = 7


class ReaderState(Enum):
    OFF = 0
    IDLE = 1
    RX = 2
    TX = 3


class Trajectory(DESModel):
    def __init__(self, sim):
        super().__init__(sim)
        self.center = sim.params.reader.trajectory.center
        self.radius = sim.params.reader.trajectory.radius
        self.velocity = sim.params.reader.trajectory.velocity
        self.altitude = sim.params.reader.trajectory.altitude

    @property
    def angular_velocity(self):
        return self.velocity / self.radius

    def get_position(self, t):
        angle = (self.angular_velocity * t) % (2 * pi)
        x = cos(angle) * self.radius + self.center[0]
        y = sin(angle) * self.radius + self.center[1]
        z = self.altitude
        return asarray((x, y, z))

    def __str__(self):
        return f'Trajectory[C={self.center}, R={self.radius}, ' \
               f'V={self.velocity}, H={self.altitude}]'


class Network(DESModel):
    def __init__(self, sim):
        super().__init__(sim)
        self.num_tags = len(sim.params.tags)
        self.reader = Reader(sim, network=self)
        self.tags = [Tag(sim, index=i, network=self)
                     for i in range(self.num_tags)]

        # States
        self._tag_rx_start_event_id = {tag.id: None for tag in self.tags}

        self._handle_tag_rx_start = \
            lambda tag_id, frame: self.get_tag(tag_id).start_rx(frame)
        self._handle_tag_tx_end = \
            lambda tag_id: self.get_tag(tag_id).finish_tx()
        self._handle_tag_rx_end = \
            lambda tag_id: self.get_tag(tag_id).finish_rx()

    def initialize(self):
        # TODO: move DES.on and DES.delete_handler to kernel
        # Subscribe to events:
        self.sim.bind(events.TAG_RX_START, self._handle_tag_rx_start)
        self.sim.bind(events.TAG_TX_END, self._handle_tag_tx_end)
        self.sim.bind(events.TAG_RX_END, self._handle_tag_rx_end)
        self.sim.bind(events.TAG_TURNED_OFF, self.reader.tag_turned_off)
        self.sim.bind(events.READER_RX_START, self.reader.start_rx)
        self.sim.bind(events.READER_RX_END, self.reader.finish_rx)
        self.sim.bind(events.READER_TX_END, self.reader.finish_tx)
        self.sim.bind(events.READER_SEND_COMMAND, self.reader.send_command)
        self.sim.bind(events.READER_NO_REPLY, self.reader.no_reply)
        self.sim.bind(events.UPDATE_POSITIONS, self.update_positions)
        self.sim.bind(events.START_ROUND, self.reader.start_round)

    def finalize(self):
        # Subscribe to events:
        self.sim.unbind(events.TAG_RX_START, self._handle_tag_rx_start)
        self.sim.unbind(events.TAG_TX_END, self._handle_tag_tx_end)
        self.sim.unbind(events.TAG_RX_END, self._handle_tag_rx_end)
        self.sim.unbind(events.TAG_TURNED_OFF, self.reader.tag_turned_off)
        self.sim.unbind(events.READER_RX_START, self.reader.start_rx)
        self.sim.unbind(events.READER_RX_END, self.reader.finish_rx)
        self.sim.unbind(events.READER_TX_END, self.reader.finish_tx)
        self.sim.unbind(events.READER_SEND_COMMAND, self.reader.send_command)
        self.sim.unbind(events.READER_NO_REPLY, self.reader.no_reply)
        self.sim.unbind(events.UPDATE_POSITIONS, self.update_positions)
        self.sim.unbind(events.START_ROUND, self.reader.start_round)

    def get_tag(self, tag_id):
        return [tag for tag in self.tags if tag.id == tag_id][0]

    def send_tag_frame(self, tag_id, frame):
        tag = [tag for tag in self.tags if tag.id == tag_id][0]
        distance = count_distance(self.reader.position, tag.position)
        dt = distance / SPEED_OF_LIGHT
        self.sim.schedule(events.READER_RX_START, dt, args=(tag_id, frame))

    def send_reader_frame(self, frame):
        for tag in [tag for tag in self.tags if tag.state != TagState.OFF]:
            distance = count_distance(self.reader.position, tag.position)
            dt = distance / SPEED_OF_LIGHT
            self.sim.schedule(events.TAG_RX_START, dt, args=(tag.id, frame))

    def update_positions(self):
        self.reader.update_position()

        # Refresh tags power:
        for tag in self.tags:
            d = count_distance(tag.position, self.reader.position)
            propagation_distance = self.sim.params.propagation.distance
            if d <= propagation_distance and tag.state == TagState.OFF:
                tag.turn_on()
            elif d > propagation_distance and tag.state != TagState.OFF:
                tag.turn_off()

        # Schedule next positions update:
        dt = self.sim.params.mobility.update_timeout
        self.sim.schedule(events.UPDATE_POSITIONS, dt)


class RxOp:
    def __init__(self, frame=None, t_start=0, t_end=0, tag_id=-1, broken=False):
        self.frame = frame
        self.t_start = t_start
        self.t_end = t_end
        self.tag_id = tag_id
        self.broken = broken


# noinspection PyUnresolvedReferences
class DeviceMixin:
    @property
    def position(self):
        return self._position

    def update_position(self):
        pass  # do nothing by default


class Reader(DeviceMixin, DESModel):
    def __init__(self, sim, network):
        super().__init__(sim)
        self.network = network
        self.trajectory = Trajectory(sim)
        self._position = self.trajectory.get_position(0)
        self.tari = sim.params.reader.tari
        self.rtcal = sim.params.reader.rtcal
        self.trcal = sim.params.reader.trcal
        self.Q = sim.params.reader.Q
        self.M = TagEncoding.deserialize(sim.params.reader.M)
        self.dr = DR.deserialize(sim.params.reader.DR)
        self.session = Session.deserialize(sim.params.reader.session)
        self.target = InventoryFlag.deserialize(sim.params.reader.target)
        self.trext = sim.params.reader.trext
        self.sel = Sel.deserialize(sim.params.reader.sel)

        # Derived values:
        self._blf = get_blf(self.dr, self.trcal)
        self._inter_command_interval = min_t1(self.rtcal, self._blf) + t3()
        self._num_slots = 2 ** self.Q

        # State:
        self._state = ReaderState.OFF
        self._command = None
        self._tx_frame = None
        self._rxops = []
        self._slot = 0
        self._end_of_tx_time = 0
        self._end_of_tx_event_id = None
        self._end_of_rx_event_id = None
        self._no_reply_event_id = None

        # Statistics:
        self.num_reads = {tag.id: 0 for tag in sim.params.tags}
        self.rounds = []  # {index, t_start, t_finish, duration, tags_on, tags_read}
        self._round_index = 0
        self.read_timestamps = []
        self.num_collisions = 0

    def update_position(self):
        self._position = self.trajectory.get_position(self.sim.sim_time)

    def start_round(self):
        self._state = ReaderState.IDLE
        self._slot = 1
        self._send_query()
        self._round_index += 1
        # Write previous rounds stats:
        if self.rounds:
            last_round = self.rounds[-1]
            last_round['t_finish'] = self.sim.sim_time
            last_round['duration'] = self.sim.sim_time - last_round['t_start']
        # Write new round:
        self.rounds.append({
            'index': self._round_index,
            'duration': 0,
            't_start': self.sim.sim_time,
            't_finish': self.sim.sim_time,
            'tags_on': [tag.id for tag in self.network.tags
                        if tag.state != TagState.OFF],
            'tags_turned_off': [],
            'tags_read': [],
        })

    def _next_slot(self):
        if self._slot < self._num_slots:
            self._slot += 1
            self._send_query_rep()
        else:
            self.start_round()

    def send_command(self):
        assert self._state == ReaderState.IDLE

        # 1) Create frame with current command:
        preamble = ReaderFrame.Preamble(self.tari, self.rtcal, self.trcal) \
            if isinstance(self._command, Query) else \
            ReaderFrame.Sync(self.tari, self.rtcal)

        self._tx_frame = ReaderFrame(preamble, self._command)

        self.sim.logger.trace(f'reader is sending {self._tx_frame}')

        # 2) Update reader state and schedule end of TX:
        self._state = ReaderState.TX
        duration = self._tx_frame.duration
        self.sim.schedule(events.READER_TX_END, duration)

        # 3) Send frame to tags:
        self.network.send_reader_frame(self._tx_frame)

    def finish_tx(self):
        """Handle end of reader TXOP.
        """
        assert self._state == ReaderState.TX
        self._state = ReaderState.IDLE
        self._end_of_tx_event_id = None
        self._end_of_tx_time = self.sim.sim_time
        # Schedule no reply timeout:
        self._no_reply_event_id = \
            self.sim.schedule(events.READER_NO_REPLY, self._inter_command_interval)

    def start_rx(self, tag_id, frame):
        """Start tag reply receive (RXOP) by the reader.
        """
        duration = frame.duration
        now = self.sim.sim_time
        self.sim.cancel(self._no_reply_event_id)
        if self._rxops:
            t_end = max(rxop.t_end for rxop in self._rxops)
            new_t_end = now + duration
            if new_t_end > t_end:
                assert self._end_of_rx_event_id is not None
                self.sim.cancel(self._end_of_rx_event_id)
                self._end_of_rx_event_id = \
                    self.sim.schedule(events.READER_RX_END, new_t_end - now)
        else:
            self._state = ReaderState.RX
            self._end_of_rx_event_id = \
                self.sim.schedule(events.READER_RX_END, duration)

        rxop = RxOp(frame, now, now + duration, tag_id)
        self._rxops.append(rxop)

    def tag_turned_off(self, tag_id):
        rxops = [rxop for rxop in self._rxops if rxop.tag_id == tag_id]
        if rxops:
            rxops[0].broken = True
        self.rounds[-1]['tags_turned_off'].append(tag_id)

    def finish_rx(self):
        """End of all RXOPs at reader.
        """
        self._state = ReaderState.IDLE
        num_rxops = len(self._rxops)
        assert num_rxops > 0
        if num_rxops == 1 and not self._rxops[0].broken:
            rxop = self._rxops[0]
            reply = rxop.frame.reply
            p_success = (1 - self.sim.params.channel.ber) ** reply.bitlen
            success = random() <= p_success
            # print('success: ', success, ', ber: ', self.sim.params.channel.ber,
            #       ', bit length: ', reply.bitlen)
            if success:
                self._receive(rxop.frame.reply, rxop.tag_id)
            else:
                self.no_reply()
        else:
            if num_rxops > 1:
                self.num_collisions += 1
            self.no_reply()
        self._rxops = []
        self._end_of_rx_event_id = None

    def _receive(self, reply, tag_id):
        if isinstance(reply, QueryReply):
            self._send_ack(reply.rn)

        elif isinstance(reply, AckReply):
            self.num_reads[tag_id] += 1
            self.rounds[-1]['tags_read'].append(tag_id)
            if self.sim.params.reader.stats.record_read_timestamps:
                self.read_timestamps.append(self.sim.sim_time)
            self._next_slot()

        else:
            raise RuntimeError(f'response "{reply}" not supported')

    def _send_query(self):
        self._command = Query(
            dr=self.dr, m=self.M, trext=self.trext, sel=self.sel,
            session=self.session, target=self.target, q=self.Q, crc5=0)
        self.send_command()

    def _send_query_rep(self):
        self._command = QueryRep(self.session)
        self.send_command()

    def _send_ack(self, rn16):
        self._command = Ack(rn16)
        self.send_command()

    def no_reply(self):
        self._next_slot()  # right now - without any attempt to fix


class Tag(DeviceMixin, DESModel):
    def __init__(self, sim, index, network):
        super().__init__(sim)
        self.network = network
        self.index = index
        params = sim.params.tags[index]
        self.id = params.id
        self._position = asarray(params.position)
        self.epcid = params.epcid
        self.switch_target = params.switch_target
        # State variables:
        self._sessions = [InventoryFlag.A] * 4
        self._state = TagState.OFF
        self._slot = 0xFFFF
        self._rn16 = 0
        self._reader_frame = None
        self._tx_frame = None
        self._rx_end_event_id = None
        self._tx_end_event_id = None
        # Round settings (from Query command):
        self.q = 0xF
        self.m = TagEncoding.FM0
        self.trext = False
        self.blf = 42
        self.num_slots = 2 ** self.q
        self.session = Session.S0
        self.target = InventoryFlag.A

    @property
    def state(self):
        return self._state

    def turn_on(self):
        self.sim.logger.debug(f'tag {self.id} turned on')
        self._state = TagState.READY
        self.sim.schedule(events.TAG_TURNED_ON, args=(self.id,))
        for i in range(4):
            self._sessions[i] = InventoryFlag.A

    def turn_off(self):
        self.sim.logger.debug(f'tag {self.id} turned off')
        self.sim.cancel(self._rx_end_event_id)
        self.sim.cancel(self._tx_end_event_id)
        self._rx_end_event_id = None
        self._tx_end_event_id = None
        self._reader_frame = None
        self._tx_frame = None
        self._state = TagState.OFF
        self.sim.schedule(events.TAG_TURNED_OFF, args=(self.id,))

    def start_rx(self, frame):
        assert self._reader_frame is None, "Unexpected multiple reader frames"
        assert frame is not None, "Non reader frame received"
        self._reader_frame = frame
        self._rx_end_event_id = self.sim.schedule(
            events.TAG_RX_END, frame.duration, args=(self.id,))

    def finish_rx(self):
        assert self._reader_frame is not None, "Tag finish RX of nothing"
        frame = self._reader_frame
        self._rx_end_event_id = None
        self._reader_frame = None
        self._receive(frame)

    def finish_tx(self):
        assert self._tx_frame is not None, "Tag finish TX of nothing"
        self._tx_end_event_id = None
        self._tx_frame = None
        # Right now - nothing to be done here

    def _transmit(self, reply):
        assert self._tx_frame is None, "Unexpected multiple tag TXOPs"
        self._tx_frame = TagFrame(self.m, self.trext, self.blf, reply)
        self._tx_end_event_id = self.sim.schedule(
            events.TAG_TX_END, self._tx_frame.duration, args=(self.id,))
        self.network.send_tag_frame(tag_id=self.id, frame=self._tx_frame)

    def _receive(self, frame):
        assert isinstance(frame, ReaderFrame)
        command = frame.cmd

        if isinstance(command, Query):
            # Check whether tag should respond to query:
            if command.target == self._sessions[command.session.value]:
                # Extract round parameters:
                self.q = command.q
                self.trext = command.trext
                self.m = command.m
                self.blf = get_blf(command.dr, frame.preamble.trcal)
                self.num_slots = 2 ** self.q
                self.session = command.session
                self.target = command.target
                # Select random slot and send RN16 if it is zero:
                self._slot = randint(0, self.num_slots - 1)

                if self._slot == 0:
                    self._state = TagState.REPLY
                    self._send_rn16()
                else:
                    self._state = TagState.ARBITRATE
            else:
                self._state = TagState.READY

        elif isinstance(command, QueryRep):
            # Decrement slot counter and check whether we need to send
            if self._state != TagState.READY:
                self._slot = (self._slot - 1) % 0x10000
                if self._slot == 0:
                    self._state = TagState.REPLY
                    self._send_rn16()

        elif isinstance(command, Ack):
            if self._state not in {TagState.READY, TagState.ARBITRATE}:
                if command.rn == self._rn16:
                    self._state = TagState.ACKNOWLEDGED
                    self._send_epcid()

        else:
            raise ValueError(f'unsupported command {command}')

    def _send_rn16(self):
        self._rn16 = randint(0, 0xFFFF)
        self._transmit(QueryReply(self._rn16))

    def _send_epcid(self):
        self._transmit(AckReply(self.epcid))
        if self.switch_target:
            session = self.session.value
            assert isinstance(session, int)
            curr_flag = self._sessions[session]
            self._sessions[session] = curr_flag.invert()
