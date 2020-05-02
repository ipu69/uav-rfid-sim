import heapq
import itertools
from enum import Enum
from functools import total_ordering
import colorama


def _get_scalar_or_dict(x):
    if isinstance(x, dict):
        return _ParamsDict(x)
    elif isinstance(x, list) or isinstance(x, tuple):
        return tuple(_get_scalar_or_dict(i) for i in x)
    else:
        return x


class _ParamsDict:
    def __init__(self, kwargs):
        self.__kwargs = {}
        if kwargs is not None:
            for key, value in kwargs.items():
                self.__kwargs[key] = _get_scalar_or_dict(value)

    def __getitem__(self, item):
        return self.__kwargs[item]

    def __getattr__(self, item):
        return self.__kwargs[item]

    def as_dict(self):
        return {**self.__kwargs}


@total_ordering
class _Event:
    def __init__(self, event_id, name, sim_time, args, kwargs):
        self.__event_id = event_id
        self.__name = name
        self.__sim_time = sim_time
        self.__args = args
        self.__kwargs = kwargs
        self.__removed = False

    @property
    def event_id(self):
        return self.__event_id

    @property
    def sim_time(self):
        return self.__sim_time

    @property
    def name(self):
        return self.__name

    @property
    def args(self):
        return self.__args

    @property
    def kwargs(self):
        return self.__kwargs

    @property
    def removed(self):
        return self.__removed

    def remove(self):
        self.__removed = True

    def __eq__(self, other):
        return (self.__sim_time == other.sim_time and
                self.__event_id == other.event_id)

    def __lt__(self, other):
        return (self.__sim_time < other.sim_time or
                self.__sim_time == other.sim_time and
                self.__event_id < other.event_id)


class Kernel:
    def __init__(self):
        self.__queue = []
        self.__sim_time = 0
        self.__event_ids = {}
        self.__next_event_id = itertools.count()
        self.__num_events = 0
        self.__queue_size = 0
        self.__stop_predicates = []

    @property
    def sim_time(self):
        return self.__sim_time

    @property
    def empty(self):
        return self.__queue_size == 0

    @property
    def num_events(self):
        return self.__num_events

    def add_event(self, name, delay, args=(), kwargs=None):
        if delay < 0:
            raise ValueError('negative delay disallowed')
        kwargs = {} if kwargs is None else kwargs
        event = _Event(
            event_id=next(self.__next_event_id),
            name=name,
            sim_time=self.sim_time + delay,
            args=args,
            kwargs=kwargs
        )
        self.__event_ids[event.event_id] = event
        heapq.heappush(self.__queue, event)
        self.__queue_size += 1
        return event.event_id

    def remove_event(self, event_id):
        event = self.__event_ids.get(event_id, None)
        if event:
            del self.__event_ids[event_id]
            if not event.removed:
                event.remove()
                self.__queue_size -= 1
                return event
        return None

    def _next_event(self):
        while self.__queue:
            event = heapq.heappop(self.__queue)
            if not event.removed:
                # Update time:
                assert event.sim_time >= self.__sim_time
                self.__sim_time = event.sim_time

                # Remove event from the EventID table and reduce queue size:
                del self.__event_ids[event.event_id]
                self.__queue_size -= 1

                return event
        raise KeyError('pop from empty queue')

    def _test_stop(self):
        return any(pred(self) for pred in self.__stop_predicates)

    def setup(self, sim_time_limit=None):
        if sim_time_limit and sim_time_limit > 0:
            self.__stop_predicates.append(
                lambda kern: sim_time_limit < kern.sim_time
            )

    def run(self, sim, init, fin):
        if hasattr(sim.data, 'initialize'):
            sim.data.initialize()
        if init:
            init(sim)

        while not self.empty:
            event = self._next_event()
            if self._test_stop():
                break

            try:
                handlers_list = DES.events_mapping.get(event.name, [])
            except KeyError:
                raise RuntimeError(f'event "{event.name}" not defined')

            sim.logger.trace(f'---- event "{event.name}" '
                             f'[running {len(handlers_list)} handlers]')
            for handler in handlers_list:
                sim.logger.trace(f'** calling {handler.__name__}()')
                handler(*event.args, **event.kwargs)
                self.__num_events += 1

        if hasattr(sim.data, 'finalize'):
            sim.data.finalize()
        if fin:
            fin(sim)


class Logger:
    class Level(Enum):
        TRACE = 0
        DEBUG = 1
        INFO = 2
        WARNING = 3
        ERROR = 4

    def __init__(self, kernel):
        self.level = Logger.Level.INFO
        self.__kernel = kernel

    @property
    def kernel(self):
        return self.__kernel

    def write(self, level, msg, src=''):
        fs_bright = colorama.Style.BRIGHT
        fs_normal = colorama.Style.NORMAL
        fs_dim = colorama.Style.DIM
        fs_reset = colorama.Style.RESET_ALL + colorama.Fore.RESET
        time_color = colorama.Fore.LIGHTCYAN_EX

        if level.value >= self.level.value:
            lc = Logger.level2font(level)
            src_str = (fs_bright + f'({src}) ' + fs_reset) if src else ''
            level_str = fs_bright + lc + f'[{level.name:7s}]'
            time_str = fs_dim + time_color + f'{self.kernel.sim_time:014.9f}'
            msg_str = fs_normal + lc + msg
            print(f'{level_str} {time_str} {src_str}{msg_str}' + fs_reset)

    def trace(self, msg, src=''):
        self.write(Logger.Level.TRACE, msg, src)

    def debug(self, msg, src=''):
        self.write(Logger.Level.DEBUG, msg, src)

    def info(self, msg, src=''):
        self.write(Logger.Level.INFO, msg, src)

    def warning(self, msg, src=''):
        self.write(Logger.Level.WARNING, msg, src)

    def error(self, msg, src=''):
        self.write(Logger.Level.ERROR, msg, src)

    @staticmethod
    def level2font(level):
        if level is Logger.Level.TRACE:
            return colorama.Fore.LIGHTBLACK_EX
        if level is Logger.Level.DEBUG:
            return colorama.Fore.WHITE
        if level is Logger.Level.INFO:
            return colorama.Fore.MAGENTA
        if level is Logger.Level.WARNING:
            return colorama.Fore.YELLOW
        if level is Logger.Level.ERROR:
            return colorama.Fore.RED


class Simulator:
    def __init__(self, kernel, model, params=None, logger_level=None):
        params = {} if params is None else params
        self.__kernel = kernel
        self.__params = _ParamsDict(params)
        self.__logger = Logger(kernel)
        if logger_level is not None:
            self.__logger.level = logger_level
        # Creating model data:
        if issubclass(model, DESModel):
            self.__data = model(self)
        else:
            # If protodata is not a class, we use it as it is.
            self.__data = model

    @property
    def sim_time(self):
        return self.__kernel.sim_time

    @property
    def num_events(self):
        return self.__kernel.num_events

    def schedule(self, event_name, delay=0, args=(), kwargs=None):
        return self.__kernel.add_event(event_name, delay, args, kwargs)

    def cancel(self, event_id):
        self.__kernel.remove_event(event_id)

    @property
    def params(self):
        return self.__params

    @property
    def data(self):
        return self.__data

    @property
    def logger(self):
        return self.__logger


class DES:
    events_mapping = {}
    initialize = None

    @classmethod
    def on(cls, event_name, handler):
        try:
            handlers_list = cls.events_mapping[event_name]
            if handler not in handlers_list:
                handlers_list.append(handler)
        except KeyError:
            cls.events_mapping[event_name] = [handler]

    @classmethod
    def delete_handler(cls, name, handler):
        try:
            cls.events_mapping[name].remove(handler)
        except KeyError:
            pass

    @classmethod
    def simulate(cls, model, initialize=None, params=None,
                 logger_level=Logger.Level.INFO, sim_time_limit=None):
        initialize = initialize or cls.initialize
        params = {} if params is None else params
        if isinstance(params, list) or isinstance(params, tuple):
            return [
                cls.simulate(model, initialize, p, logger_level) for p in params
            ]
        kernel = Kernel()
        sim = Simulator(kernel, model, params, logger_level)
        kernel.setup(sim_time_limit=sim_time_limit)
        kernel.run(sim, init=initialize, fin=None)
        return sim


class DESModel:
    def __init__(self, sim=None):
        self.__sim = sim

    @property
    def sim(self):
        return self.__sim

    @sim.setter
    def sim(self, value):
        self.__sim = value

