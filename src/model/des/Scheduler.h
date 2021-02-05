#ifndef SCHEDULER_H
#define SCHEDULER_H

#include <queue>
#include <map>
#include <unordered_set>
#include <functional>
#include <string>
#include <Python.h>

namespace model {
namespace des {


#define SPECTYPE_INT_PYOBJ 0
#define SPECTYPE_INT 1
#define SPECTYPE_PYOBJ 2
#define SPECTYPE_EMPTY 3


class Event
{
  public:
    Event(int id, int code, float time, int index, PyObject *att);
    Event(const Event& other);
    ~Event();

    inline int getID() const { return _id; }
    inline int getCode() const { return _code; }
    inline float getTime() const { return _time; }
    inline int getIndex() const { return _index; }
    inline PyObject *getAtt() const { return _att; }

    bool operator<(const Event& rside) const;

    std::string str() const;

  private:
    int _id;
    int _code;
    float _time;
    int _index;
    PyObject *_att;
};



struct EventPtrComparator {
    bool operator()(Event * lside, Event * rside);
};


struct HandlerDescriptor {
    void *handler;
    int spec_type;
};


typedef void (*CyCallbackIP)(void*, PyObject*, int, PyObject*);
typedef void (*CyCallbackI)(void*, PyObject*, int);
typedef void (*CyCallbackP)(void*, PyObject*, PyObject*);
typedef void (*CyCallbackE)(void*, PyObject*);


class Scheduler
{
  public:
    Scheduler();
    ~Scheduler();

    inline void set_cy_callback_ip(CyCallbackIP fn) { _callback_ip = fn; }
    inline void set_cy_callback_i(CyCallbackI fn) { _callback_i = fn; }
    inline void set_cy_callback_p(CyCallbackP fn) { _callback_p = fn; }
    inline void set_cy_callback_e(CyCallbackE fn) { _callback_e = fn; }

    void attach_handler_ip(int code, void *handler);
    void attach_handler_i(int code, void *handler);
    void attach_handler_p(int code, void *handler);
    void attach_handler_e(int code, void *handler);
    void attach_init_handler(void *handler);

    inline void set_context_owner(PyObject* owner) { _context_owner = owner; }

    int schedule(float time, int code, int index = -1, PyObject *att = nullptr);
    void stop();

    void cancel(int event_id);

    inline float get_time() const { return _time; }

    void run();

  private:
    CyCallbackE _callback_e;
    CyCallbackI _callback_i;
    CyCallbackP _callback_p;
    CyCallbackIP _callback_ip;

    std::priority_queue<Event*, std::vector<Event*>, EventPtrComparator> _queue;
    std::unordered_set<int> _cancelled_event_ids;
    int _next_event_id;
    std::map<int, std::vector<HandlerDescriptor> > _handlers;
    std::vector<void*> _init_handlers;
    float _time;
    PyObject *_context_owner;
    bool _stopped;

    int _schedule(Event *event);
};


}}


#endif