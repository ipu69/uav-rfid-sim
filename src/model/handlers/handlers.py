import numpy as np

import model.handlers.events as ev
from model.c1g2.commands import Query, QueryRep, Ack, ReqRn, Read
from model.c1g2.replies import RN16, EPC, Handle, Data
from model.c1g2.symbols import min_t2
from model.objects.reader import Reader, RxOp
from model.objects.tag import Tag


#############################################################################
# SYSTEM HANDLERS
#############################################################################
def initialize(ctx):
    # 1) schedule next position update right now
    ctx.sim.schedule(0.0, ev.UPDATE_POSITIONS)
    # 2) schedule start of the round (also right now)
    ctx.sim.schedule(0.0, ev.START_ROUND)


def reader_left(ctx):
    # 1) record statistics
    pass  # TODO

    # 2) cancel any pending events
    if ctx.state.verbose:
        print(f'[{ctx.sim.time:.06f}] ==== READER LEFT ======')

    ctx.sim.stop()


def update_positions(ctx):
    scene, time = ctx.state, ctx.sim.time
    reader, tag, channel = scene.reader, scene.tag, scene.channel

    if scene.verbose:
        print(f'[{time:.06f}] update_positions:')

    # 1) compute next reader position using its velocity vector and time
    #    passed since the previous offset
    reader.update_position(time)

    if scene.verbose:
        print(f'\treader position: {reader.position}')

    # 2) schedule READER_LEFT, depending on the distance from the tag
    if np.linalg.norm(reader.position - tag.position) >= scene.max_distance:
        ctx.sim.schedule(time, ev.READER_LEFT)

    # 3) update channel: re-estimate power at tag and reader, schedule
    #    TAG_POWER_ON/TAG_POWER_OFF depending on value change
    else:
        channel.update_power(time, reader, tag)
        tag_rx_power = channel.tag_rx_power_map.last

        if scene.verbose:
            print(channel.str_state())

        if not tag.powered and tag_rx_power >= tag.sensitivity:
            tag_power_on(ctx)
        elif tag.powered and tag_rx_power < tag.sensitivity:
            tag_power_off(ctx)

    # 4) Schedule next power update
    ctx.sim.schedule(time + scene.position_update_interval, ev.UPDATE_POSITIONS)


#############################################################################
# READER HANDLERS
#############################################################################
def send_command(ctx, frame):
    scene, sim = ctx.state, ctx.sim
    reader, tag, channel = scene.reader, scene.tag, scene.channel
    time = sim.time

    if scene.verbose:
        print(f'[{time:.6f}] send_command: {frame} [D:{frame.duration:.06f}s]')

    reader.state = Reader.TX
    reader.tx_frame = frame
    dt = frame.duration
    sim.schedule(time + dt, ev.READER_TX_END)
    prop = channel.get_propagation_delay(reader.position, tag.position)
    sim.schedule(time + prop, ev.TAG_RX_START, att=frame)


def reader_start_round(ctx):
    scene = ctx.state
    reader = scene.reader

    if 0 < scene.max_num_rounds <= reader.num_rounds:
        ctx.sim.schedule(ctx.sim.time, ev.READER_LEFT)
    else:
        reader.start_round()

        if scene.verbose:
            print(f'[{ctx.sim.time:.6f}] ==== round #{reader.num_rounds} ====')

        frame = reader.commands.query
        send_command(ctx, frame)


def reader_rx_start(ctx, frame):
    sim, scene = ctx.sim, ctx.state
    reader = scene.reader
    time = sim.time
    rxops_list = reader.rxops

    if scene.verbose:
        print(f'[{time:.6f}] reader_rx_start: {frame} [D:{frame.duration:.06f}s]')

    # 1) if any RXOPs exist or reader state is TX, mark all RXOPs as broken:
    has_rxops = bool(rxops_list)
    broken = reader.state == Reader.TX or has_rxops

    if broken:
        for rxop in rxops_list:
            rxop.broken = True
        if scene.verbose:
            print(f'\tCOLLISION!')

    # 2) create and store a new RXOP with current time
    rxops_list.append(RxOp(frame, time, time + frame.duration, broken=broken))

    # 3) (re-)schedule RX-end event (when all RXOPs finish)
    rx_ends_at = max(rxop.finish_at for rxop in rxops_list)
    if not has_rxops or reader.rx_ends_at < rx_ends_at:
        sim.cancel(reader.end_of_rx_event_id)
        reader.end_of_rx_event_id = sim.schedule(rx_ends_at, ev.READER_RX_END)

    # 4) if the reader state was IDLE, change it to RX and cancel timeout:
    if reader.state == Reader.IDLE:
        reader.state = reader.RX
        sim.cancel(reader.no_reply_event_id)
        reader.no_reply_event_id = -1


def reader_rx_end(ctx):
    sim, scene = ctx.sim, ctx.state
    reader = scene.reader
    rxops_list, frame, broken = reader.rxops, None, True

    if scene.verbose:
        print(f'[{ctx.sim.time:.06f}] reader_rx_end')

    # 1) Set Reader to IDLE state:
    reader.state = Reader.IDLE

    # 2) Check whether RXOP was the only one and is not broken. If so,
    #    estimate minimum RX power, compute BER and decide whether frame
    #    was received successfully (not broken):
    if len(rxops_list) == 1 and not (rxop := rxops_list[0]).broken:
        channel = scene.channel
        # noinspection PyUnboundLocalVariable
        rx_power = channel.reader_rx_power_map.get_min(
            rxop.started_at, rxop.finish_at)
        frame = rxop.frame
        ber = channel.ber_map.last
        p_success = (1 - ber) ** frame.reply.bitlen
        broken = np.random.rand() > p_success

        if scene.verbose:
            print(f'\tframe: {frame}')
            print(f'\trx_power = {rx_power:.2f}dBm, ber={ber:.2f}, '
                  f'p_success={p_success:.6f}; ')

    # 3) Clear RXOP buffer and RX-related variables:
    reader.rxops = []
    reader.end_of_rx_event_id = -1

    t_send = sim.time + min_t2(reader.blf)

    if scene.verbose:
        print(f'\t{">> BROKEN" if broken else ">> RECEIVED!"}')

        # 4) If frame was broken, schedule no_reply action:
    if broken:
        reader.no_reply_event_id = sim.schedule(t_send, ev.READER_NO_REPLY)

    # 5) Otherwise, handle the response:
    else:
        reply = frame.reply

        # Write statistics:
        if isinstance(reply, EPC):
            scene.tag.num_epcid_received += 1
        elif isinstance(reply, Data):
            scene.tag.num_data_received += 1

        # Schedule either new round, or next command sending:
        new_round, next_command = reader.get_next_command(frame.reply)
        if new_round:
            sim.schedule(t_send, ev.START_ROUND)
        else:
            sim.schedule(t_send, ev.SEND_COMMAND, att=next_command)


def reader_abort_rx(ctx):
    sim, scene = ctx.sim, ctx.state
    reader = scene.reader

    if scene.verbose:
        print(f'[{ctx.sim.time:.06f}] reader_abort_rx')

    # If a RXOP is running, cancel it:
    # TODO: when adding multiple tag, find the RXOP
    # rxops = [rxop for rxop in reader.rxops if rxop.sender is tag]
    rxops_list = reader.rxops
    assert len(rxops_list) <= 1
    if rxops_list:
        rxop = rxops_list[0]
        rxop.broken = True
        sim.cancel(reader.end_of_rx_event_id)

        rxop.finish_at = sim.time
        reader.rx_ends_at = sim.time
        reader_rx_end(ctx)


def reader_tx_end(ctx):
    scene = ctx.state
    reader, sim = scene.reader, ctx.sim

    if scene.verbose:
        print(f'[{ctx.sim.time:.06f}] reader_tx_end: state := IDLE, frame = {reader.tx_frame}, slot = {reader.slot}')

    # 1) change reader state to IDLE
    reader.state = Reader.IDLE

    # 2) clear TX buffer and any corresponding events
    reader.tx_frame = None
    reader.end_of_tx_event_id = -1

    # 3) Schedule no-reply timeout
    t_no_reply = sim.time + reader.inter_command_interval
    reader.no_reply_event_id = sim.schedule(t_no_reply, ev.READER_NO_REPLY)


def no_reply(ctx):
    # Move to the next slot: increase the slot counter if round is not
    # completed, or schedule the next round start otherwise
    scene = ctx.state
    reader = scene.reader

    if scene.verbose:
        print(f'[{ctx.sim.time:.06f}] no_reply')

    if reader.has_next_slot():
        reader.start_slot()
        send_command(ctx, reader.commands.query_rep)
    else:
        reader_start_round(ctx)


#############################################################################
# TAG HANDLERS
#############################################################################
def tag_power_on(ctx):
    scene = ctx.state

    if scene.verbose:
        channel = scene.channel
        print(f'[{ctx.sim.time:.06f}] (^) tag power on')

    tag = ctx.state.tag
    tag.state = Tag.READY


def tag_power_off(ctx):
    sim, scene = ctx.sim, ctx.state
    tag, reader, channel = scene.tag, scene.reader, scene.channel

    if scene.verbose:
        channel = scene.channel
        print(f'[{ctx.sim.time:.06f}] (x) tag power OFF')

    # 1) cancel any pending RX:
    if tag.tx_start_event_id >= 0:
        sim.cancel(tag.tx_start_event_id)
        tag.tx_start_event_id = -1

    if tag.rx_end_event_id >= 0:
        assert tag.rx_frame is not None
        sim.cancel(tag.rx_end_event_id)
        tag.rx_end_event_id = -1
        tag.rx_frame = None

    # 2) force end-of-TX if tag TXOP is running
    if tag.tx_end_event_id >= 0:
        sim.cancel(tag.tx_end_event_id)
        tag.tx_end_event_id = -1

        prop = channel.get_propagation_delay(reader.position, tag.position)
        sim.schedule(sim.time + prop, ev.READER_ABORT_RX)

    # 4) set tag state (OFF)
    tag.state = Tag.OFF


def tag_rx_start(ctx, frame):
    scene = ctx.state
    tag, sim = scene.tag, ctx.sim

    # 1) if the tag is not powered, ignore; otherwise:
    if tag.state == Tag.OFF:
        return

    if scene.verbose:
        print(f'[{sim.time:.06f}] tag_rx_start: {frame} [D:{frame.duration:.06f}s]')

    # 2) if any other RXOP is running, raise an exception
    assert tag.rx_frame is None

    # 3) start RX and schedule its end:
    tag.rx_ends_at = sim.time + frame.duration
    tag.rx_frame = frame
    sim.schedule(tag.rx_ends_at, ev.TAG_RX_END)


def tag_rx_end(ctx):
    # process received frame - it is always received successfully, if
    # the tag is powered on
    scene, sim = ctx.state, ctx.sim
    tag, time = scene.tag, sim.time
    state = tag.state

    if scene.verbose:
        print(f'[{sim.time:.06f}] tag_rx_end')

    preamble, command = tag.rx_frame.preamble, tag.rx_frame.command

    tag.rx_frame = None

    if state == Tag.OFF:
        return

    tc = type(command)

    if tc is Query:
        tag.counter = np.random.randint(0, tag.num_slots)

        if tag.counter == 0:
            tag.tx_start_event_id = sim.schedule(
                time + tag.t1, ev.SEND_REPLY, att=tag.replies.rn16)
            tag.state = Tag.REPLY
        else:
            tag.state = Tag.ARBITRATE

        if scene.verbose:
            print(f'\tcounter := {tag.counter}, '
                  f'state := {Tag.str_state(tag.state)}, t1 = {tag.t1:.06f}')

    elif tc is QueryRep:
        tag.counter = (tag.counter - 1) % 0x10000
        if tag.counter == 0:
            assert tag.state == Tag.ARBITRATE
            tag.tx_start_event_id = sim.schedule(
                time + tag.t1, ev.SEND_REPLY, att=tag.replies.rn16)
            tag.state = Tag.REPLY
        elif state != Tag.ARBITRATE and state != Tag.READY:
            tag.state = Tag.ARBITRATE

        if scene.verbose:
            print(f'\tcounter := {tag.counter}, '
                  f'state := {Tag.str_state(tag.state)}')

    elif tc is Ack and state == Tag.REPLY:
        tag.tx_start_event_id = sim.schedule(
            time + tag.t1, ev.SEND_REPLY, att=tag.replies.epcid)
        tag.state = Tag.ACKNOWLEDGED

    elif state == Tag.ACKNOWLEDGED:
        if tc is ReqRn:
            tag.tx_start_event_id = sim.schedule(
                time + tag.t1, ev.SEND_REPLY, att=tag.replies.handle)
        elif tc is Read:
            tag.tx_start_event_id = sim.schedule(
                time + tag.t1, ev.SEND_REPLY, att=tag.replies.data)
        else:
            raise RuntimeError(f'unsupported command "{tag.rx_frame.command}" '
                               f'in state {Tag.str_state(state)}')

    else:
        raise RuntimeError(f'unsupported command "{tag.rx_frame.command}" '
                           f'in state {Tag.str_state(state)}')


def send_reply(ctx, frame):
    scene, sim = ctx.state, ctx.sim
    tag, channel, reader = scene.tag, scene.channel, scene.reader
    time = sim.time

    if scene.verbose:
        print(f'[{time:.06f}] send_reply: {frame} [D:{frame.duration:.06f}s]')

    tag.tx_frame = frame

    tr = type(frame.reply)
    if tr == EPC:
        tag.num_epcid_sent += 1
    elif tr == Data:
        tag.num_data_sent += 1

    dt = frame.duration
    tag.tx_end_event_id = sim.schedule(time + dt, ev.TAG_TX_END)
    prop = channel.get_propagation_delay(reader.position, tag.position)
    sim.schedule(time + prop, ev.READER_RX_START, att=frame)


def tag_tx_end(ctx):
    scene = ctx.state
    tag = scene.tag

    if scene.verbose:
        print(f'[{ctx.sim.time:.06f}] tag_tx_end')

    # clear send buffer and corresponding event ids
    tag.tx_end_event_id = -1
    tag.tx_frame = None
