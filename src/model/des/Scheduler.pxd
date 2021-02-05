from cpython.ref cimport PyObject


cdef extern from "Scheduler.cpp":
    pass


cdef extern from "Scheduler.h" namespace "model::des":
    ctypedef void (*CyCallbackE)(void*, PyObject*)
    ctypedef void (*CyCallbackI)(void*, PyObject*, int)
    ctypedef void (*CyCallbackP)(void*, PyObject*, PyObject*)
    ctypedef void (*CyCallbackIP)(void*, PyObject*, int, PyObject*)

    cdef cppclass Scheduler:
        # noinspection PyPep8Naming
        Scheduler()
        void set_cy_callback_e(CyCallbackE fn)
        void set_cy_callback_i(CyCallbackI fn)
        void set_cy_callback_p(CyCallbackP fn)
        void set_cy_callback_ip(CyCallbackIP fn)
        void set_context_owner(PyObject *owner)
        void attach_handler_e(int code, void *handler)
        void attach_handler_i(int code, void *handler)
        void attach_handler_p(int code, void *handler)
        void attach_handler_ip(int code, void *handler)
        void attach_init_handler(void *handler)
        int schedule(float time, int code, int index, PyObject *att)
        void cancel(int event_id)
        float get_time()
        void run()
        void stop();
