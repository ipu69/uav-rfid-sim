import sys
from collections import namedtuple

from model.des.Scheduler cimport Scheduler
from cpython.ref cimport PyObject

from model.des.pyscheduler import SpecType


cdef void cy_callback_e(void *handler, PyObject *scheduler):
    ctx = (<object>scheduler).get_context()
    (<object>handler)(ctx)


cdef void cy_callback_i(void *handler, PyObject *scheduler, int index):
    ctx = (<object>scheduler).get_context()
    (<object>handler)(ctx, index)


cdef void cy_callback_p(void *handler, PyObject *scheduler, PyObject *att):
    ctx = (<object>scheduler).get_context()
    (<object>handler)(ctx, <object>att)


cdef void cy_callback_ip(void *handler, PyObject *scheduler, int index,
                         PyObject *att):
    ctx = (<object>scheduler).get_context()
    (<object>handler)(ctx, index, <object>att)


Context = namedtuple('Context', ('sim', 'state', 'params'))


cdef class CyScheduler:
    cdef Scheduler *c_scheduler
    cdef object c_context

    def __cinit__(self):
        self.c_scheduler = new Scheduler()
        self.c_scheduler.set_cy_callback_e(cy_callback_e)
        self.c_scheduler.set_cy_callback_i(cy_callback_i)
        self.c_scheduler.set_cy_callback_p(cy_callback_p)
        self.c_scheduler.set_cy_callback_ip(cy_callback_ip)
        self.c_scheduler.set_context_owner(<PyObject*>self)
        self.c_context = Context(self, None, None)

    def __dealloc__(self):
        del self.c_scheduler

    @property
    def context(self):
        return self.c_context

    def get_context(self):
        return self.c_context

    @property
    def time(self):
        return self.get_time()

    def bind_init(self, object handler):
        self.c_scheduler.attach_init_handler(<void*>handler)

    def bind(self, int code, object handler, spec_type=SpecType.EMPTY):
        cdef void* handler_ptr = <void*>handler
        if spec_type is SpecType.EMPTY:
            self.c_scheduler.attach_handler_e(code, handler_ptr)
        elif spec_type is SpecType.INDEX:
            self.c_scheduler.attach_handler_i(code, handler_ptr)
        elif spec_type is SpecType.OBJECT:
            self.c_scheduler.attach_handler_p(code, handler_ptr)
        elif spec_type is SpecType.INDEX_OBJECT:
            self.c_scheduler.attach_handler_ip(code, handler_ptr)

    def setup_context(self, state, params):
        # noinspection PyAttributeOutsideInit
        self.c_context = Context(self, state, params)

    cpdef float get_time(self):
        return self.c_scheduler.get_time()

    cpdef int schedule(self, float time, int code, int index = -1,
                       object att = None):
        cdef PyObject *c_att = NULL

        if att is not None:
            c_att = <PyObject*>att

        return self.c_scheduler.schedule(time, code, index, c_att)

    cpdef void cancel(self, int event_id):
        self.c_scheduler.cancel(event_id)

    cpdef void stop(self):
        self.c_scheduler.stop()

    cpdef void run(self):
        self.c_scheduler.run()
