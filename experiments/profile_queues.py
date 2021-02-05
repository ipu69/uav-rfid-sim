import cProfile
import pstats
import sys
from dataclasses import dataclass

import numpy as np

from model.des.cyscheduler import CyScheduler
from model.des.pyscheduler import PyScheduler, SpecType

NUM_NODES = 5
MAX_TIME = 1e3
MAX_EVENTS = -1
MOVE_RATE = 100.0
CANCEL_RATE = 1.0

WINDOW_SIZE = 10000


class RandomValues:
    def __init__(self, fn):
        self.fn = fn
        self.intervals = []
        self.index = 0

    def get(self):
        if self.index >= len(self.intervals):
            self.intervals = self.fn(WINDOW_SIZE)
            self.index = 0
        x = self.intervals[self.index]
        self.index += 1
        return x


class State:
    def __init__(self, num_nodes, move_rate, cancel_rate):
        self.nodes = [0] * num_nodes
        self.num_incs = [0] * num_nodes
        self.num_decs = [0] * num_nodes
        self.next_move_ids = [-1] * num_nodes
        self.num_events = 0

        self.move_intervals = RandomValues(
            lambda size: np.random.exponential(1 / move_rate, size)
        )
        self.cancel_intervals = RandomValues(
            lambda size: np.random.exponential(1 / cancel_rate, size)
        )
        self.coins = RandomValues(
            lambda size: np.random.rand(size) < 0.5
        )


@dataclass
class Params:
    num_nodes: int = NUM_NODES
    move_rate: float = MOVE_RATE
    cancel_rate: float = CANCEL_RATE
    max_time: float = MAX_TIME
    max_events: int = MAX_EVENTS
    verbose: float = False


EVENT_INC = 0
EVENT_DEC = 1
EVENT_CANCEL = 2


def _schedule_next_move(ctx, index):
    time = ctx.sim.time
    max_events = ctx.params.max_events
    if time < ctx.params.max_time and (
            max_events < 0 or ctx.state.num_events < max_events):
        interval = ctx.state.move_intervals.get()
        coin = ctx.state.coins.get()
        code = EVENT_INC if coin else EVENT_DEC
        event_id = ctx.sim.schedule(time + interval, code, index)
        ctx.state.next_move_ids[index] = event_id
        ctx.state.num_events += 1
    else:
        ctx.state.next_move_ids[index] = -1


def _schedule_next_cancel(ctx):
    time = ctx.sim.time
    max_events = ctx.params.max_events
    if time < ctx.params.max_time and (
            max_events < 0 or ctx.state.num_events < max_events):
        interval = ctx.state.cancel_intervals.get()
        coins = ctx.state.coins
        nodes = [i for i in range(ctx.params.num_nodes) if coins.get()]
        ctx.state.num_events += 1
        ctx.sim.schedule(time + interval, EVENT_CANCEL, att=nodes)


def init(ctx):
    for i in range(ctx.params.num_nodes):
        _schedule_next_move(ctx, i)
    _schedule_next_cancel(ctx)


def handle_inc(ctx, index):
    ctx.state.nodes[index] += 1
    if ctx.params.verbose:
        print(f'{ctx.sim.time}: inc(index={index}): node={ctx.state.nodes[index]}')
    ctx.state.num_incs[index] += 1
    _schedule_next_move(ctx, index)


def handle_dec(ctx, index):
    ctx.state.nodes[index] -= 1
    if ctx.params.verbose:
        print(f'{ctx.sim.time}: dec(index={index}): node={ctx.state.nodes[index]}')
    ctx.state.num_decs[index] += 1
    _schedule_next_move(ctx, index)


def handle_cancel(ctx, att):
    att = [] if att is None else att
    if ctx.params.verbose:
        print(f'{ctx.sim.time}: att={att})')
    if att is None:
        return
    for i in att:
        event_id = ctx.state.next_move_ids[i]
        if event_id >= 0:
            if ctx.params.verbose:
                print(f'{ctx.sim.time}: ... cancelled event #{event_id} for node {i}')
            ctx.sim.cancel(event_id)
    _schedule_next_cancel(ctx)


def simulate(scheduler_klass, num_nodes, move_rate, cancel_rate, max_time,
             max_events, verbose=False):
    params = Params(
        num_nodes=num_nodes,
        move_rate=move_rate,
        cancel_rate=cancel_rate,
        max_time=max_time,
        max_events=max_events,
        verbose=verbose
    )
    state = State(num_nodes, move_rate, cancel_rate)
    scheduler = scheduler_klass()
    scheduler.setup_context(state, params)
    scheduler.bind_init(init)

    scheduler.bind(EVENT_INC, handle_inc, SpecType.INDEX)
    scheduler.bind(EVENT_DEC, handle_dec, SpecType.INDEX)
    scheduler.bind(EVENT_CANCEL, handle_cancel, SpecType.OBJECT)

    scheduler.run()
    return scheduler.get_time(), scheduler.get_context().state


def run_experiment(
        klass,
        num_nodes=NUM_NODES,
        move_rate=MOVE_RATE,
        cancel_rate=CANCEL_RATE,
        max_time=MAX_TIME,
        max_events=MAX_EVENTS,
        print_ret=False
):
    if print_ret:
        print('Launching experiment:')
        print('- num nodes   : ', num_nodes)
        print('- move rate   : ', move_rate)
        print('- cancel rate : ', cancel_rate)
        print('- max. time   : ', max_time)
        print('- max events  : ', max_events,
              '' if max_events >= 0 else '(not limited)')

    sim_time, state = simulate(
        klass,
        num_nodes=num_nodes,
        move_rate=move_rate,
        cancel_rate=cancel_rate,
        max_time=max_time,
        max_events=max_events,
        verbose=False)

    if print_ret:
        print('----------------------------')
        print('nodes:      ', state.nodes)
        print('num_incs:   ', state.num_incs)
        print('num_decs:   ', state.num_decs)
        print('num_events: ', state.num_events)
        print('time:       ', sim_time)
        print('----------------------------')


# def run_queue(queue, num_iters=1000):
#     num_reads, num_writes, next_id = 0, 0, 1
#     times = np.random.exponential(10.0, num_iters)
#     coins = np.random.randint(0, 2, num_iters)
#     for i in range(num_iters):
#         is_write = queue.empty() or coins[i] == 0
#         if is_write:
#             queue.push(next_id, times[i])
#             next_id += 1
#             num_writes += 1
#         else:
#             queue.pop()
#             num_reads += 1
#     return num_writes, num_reads
#
#
# def run_experiment(klass, num_iters=1000):
#     q = klass()
#     run_queue(q, num_iters)
#
#
def profile_experiment(
        klass,
        num_nodes=NUM_NODES,
        move_rate=MOVE_RATE,
        cancel_rate=CANCEL_RATE,
        max_time=MAX_TIME,
        max_events=MAX_EVENTS
):
    exec_str = f"run_experiment(" \
               f"{klass.__name__}, " \
               f"num_nodes={num_nodes}, " \
               f"move_rate={move_rate}, " \
               f"cancel_rate={cancel_rate}, " \
               f"max_time={max_time}, " \
               f"max_events={max_events}" \
               f")"
    print('* launching:', exec_str)
    cProfile.runctx(exec_str, globals(), locals(), "Profile.prof")
    s = pstats.Stats("Profile.prof")
    s.strip_dirs().sort_stats("time").print_stats()


def print_format():
    print('format: python experiments/profile_queue.py [-cy|-py] [N]')
    sys.exit(1)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Profile simulator")

    parser.add_argument('-T, --max-time', default=MAX_TIME, dest='max_time',
                        type=float, metavar='T',
                        help=f'Max simulation time (default: {MAX_TIME})')

    parser.add_argument('-N, --num-nodes', default=NUM_NODES, dest='num_nodes',
                        type=int, metavar='N',
                        help=f'Number of nodes (default: {NUM_NODES})')

    parser.add_argument('-R, --move-rate', default=MOVE_RATE, dest='move_rate',
                        type=float, metavar='R',
                        help=f'Move rate (default: {MOVE_RATE})')

    parser.add_argument('-C, --cancel-rate', default=CANCEL_RATE,
                        dest='cancel_rate', type=float, metavar='R',
                        help=f'Cancel rate (default: {CANCEL_RATE})')

    parser.add_argument('-E, --max-events', default=MAX_EVENTS,
                        dest='max_events', type=int, metavar='N',
                        help=f'Maximum number of events '
                             f'(default: {MAX_EVENTS})')

    parser.add_argument('--no-profile', default=False, dest='no_profile',
                        const=True, action='store_const',
                        help='Disable profiling, just run simulation')

    parser.add_argument('mode', type=str, nargs='?', default='cython',
                        help='Mode of execution. Possible values: python, '
                             'cython (default)')

    args = parser.parse_args()
    if args.mode == 'cython':
        klass = CyScheduler
    elif args.mode == 'python':
        klass = PyScheduler
    else:
        raise ValueError

    if not args.no_profile:
        profile_experiment(
            klass,
            max_time=args.max_time,
            num_nodes=args.num_nodes,
            move_rate=args.move_rate,
            cancel_rate=args.cancel_rate,
            max_events=args.max_events,
        )
    else:
        run_experiment(
            klass,
            max_time=args.max_time,
            num_nodes=args.num_nodes,
            move_rate=args.move_rate,
            cancel_rate=args.cancel_rate,
            max_events=args.max_events,
            print_ret=True,
        )


if __name__ == '__main__':
    main()
