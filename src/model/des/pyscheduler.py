import heapq
from collections import namedtuple
from enum import Enum


class SpecType(Enum):
    EMPTY = 0
    INDEX = 1
    OBJECT = 2
    INDEX_OBJECT = 3


class Event:
    def __init__(self, event_id, code, time, index, att):
        self.event_id = event_id
        self.code = code
        self.time = time
        self.index = index
        self.att = att

    def as_tuple(self):
        return self.event_id, self.code, self.time, self.index, self.att

    def __eq__(self, other):
        return (self.time == other.time and
                self.event_id == other.event_id)

    def __lt__(self, other):
        return (self.time < other.time or
                self.time == other.time and
                self.event_id < other.event_id)


class EventQueue:
    def __init__(self):
        self._queue = []
        self._cancelled_events = set()
        self._next_event_id = 1

    def push(self, code, time, index, att):
        event_id = self._next_event_id
        self._next_event_id += 1
        ev = Event(event_id, code, time, index, att)
        heapq.heappush(self._queue, ev)
        return event_id

    def pop(self):
        while len(self._queue) > 0:
            event = heapq.heappop(self._queue)
            event_id = event.event_id
            if event_id not in self._cancelled_events:
                return event.as_tuple()
            self._cancelled_events.remove(event_id)
        return None

    def remove(self, event_id):
        if event_id not in self._cancelled_events:
            self._cancelled_events.add(event_id)

    def empty(self):
        return len(self._queue) == 0

    def size(self):
        return len(self._queue)


Context = namedtuple('Context', ('sim', 'state', 'params'))
HandlerDescriptor = namedtuple('HandlerDescriptor', ('handler', 'spec_type'))


class PyScheduler:
    def __init__(self):
        self._queue = EventQueue()
        self._handlers = {}
        self._time = 0
        self._context = Context(self, None, None)
        self._init_handlers = []
        self._stopped = False

    def bind(self, code, handler, spec_type=SpecType.EMPTY):
        if code not in self._handlers:
            self._handlers[code] = [HandlerDescriptor(handler, spec_type)]
        else:
            self._handlers[code].append(HandlerDescriptor(handler, spec_type))

    def bind_init(self, handler):
        self._init_handlers.append(handler)

    @property
    def context(self):
        return self._context

    def get_context(self):
        return self._context

    def setup_context(self, state, params):
        self._context = Context(self, state, params)

    @property
    def time(self):
        return self._time

    def get_time(self):
        return self._time

    def schedule(self, time, code, index=-1, att=None):
        return self._queue.push(code, time, index, att)

    def cancel(self, event_id):
        self._queue.remove(event_id)

    def run(self):
        self._time = 0.0
        for handler in self._init_handlers:
            handler(self.context)

        while not self._queue.empty() and not self._stopped:
            event_tuple = self._queue.pop()
            if event_tuple is None:
                break
            _, code, time, index, att = event_tuple
            self._time = time
            for descriptor in self._handlers.get(code, []):
                self._call_handler(descriptor, index, att)
        print('after loop: num_events=', self._queue.size())

    def stop(self):
        self._stopped = True

    def _call_handler(self, descriptor, index, att):
        handler, spec_type = descriptor.handler, descriptor.spec_type
        if spec_type == SpecType.INDEX_OBJECT:
            handler(self.context, index, att)
        elif spec_type == SpecType.INDEX:
            handler(self.context, index)
        elif spec_type == SpecType.OBJECT:
            handler(self.context, att)
        else:
            handler(self.context)
