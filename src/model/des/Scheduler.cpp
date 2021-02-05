#include "Scheduler.h"
#include <iostream>
#include <sstream>

namespace model {
namespace des {

/******** EVEMT *******************/
Event::Event(int id, int code, float time, int index, PyObject *att)
: _id(id), _code(code), _time(time), _index(index), _att(att) {
    if (_att) {
        Py_INCREF(_att);
    }
}

Event::Event(const Event& other)
: _id(other._id), _code(other._code), _time(other._time),
  _index(other._index), _att(other._att) {
    if (_att) {
        Py_INCREF(_att);
    }
}

Event::~Event() {
    if (_att) {
        Py_DECREF(_att);
    }
}

bool Event::operator<(const Event& rside) const {
    return this->_time < rside.getTime() || (
        this->_time == rside.getTime() && this->_id < rside.getID()
    );
}

std::string Event::str() const {
    std::stringstream ss;
    ss << "Event[ID:" << _id << ", code:" << _code << ", time:" << _time
        << ", index:" << _index << ", att:" << (long)_att << "]";
    return ss.str();
}


/******* COMPARATOR **************/
bool EventPtrComparator::operator()(Event* lside, Event* rside) {
    return *rside < *lside;
}


/******* SCHEDULER **************/
Scheduler::Scheduler()
: _callback_e(nullptr), _callback_i(nullptr), _callback_p(nullptr),
  _callback_ip(nullptr), _next_event_id(1), _time(0.0),
  _context_owner(nullptr), _stopped(false) {
    ; // nop
}

Scheduler::~Scheduler() {
    while (!_queue.empty()) {
        Event *top = _queue.top();
        delete top;
        _queue.pop();
    }
}


void Scheduler::attach_handler_ip(int code, void *handler) {
    struct HandlerDescriptor hd = {handler, SPECTYPE_INT_PYOBJ};
    _handlers[code].push_back(hd);
}

void Scheduler::attach_handler_i(int code, void *handler) {
    struct HandlerDescriptor hd = {handler, SPECTYPE_INT};
    _handlers[code].push_back(hd);
}

void Scheduler::attach_handler_p(int code, void *handler) {
    struct HandlerDescriptor hd = {handler, SPECTYPE_PYOBJ};
    _handlers[code].push_back(hd);
}

void Scheduler::attach_handler_e(int code, void *handler) {
    struct HandlerDescriptor hd = {handler, SPECTYPE_EMPTY};
    _handlers[code].push_back(hd);
}

void Scheduler::attach_init_handler(void *handler) {
    _init_handlers.push_back(handler);
}


int Scheduler::schedule(float time, int code, int index, PyObject *att) {
    return _schedule(new Event(_next_event_id, code, time, index, att));
}

int Scheduler::_schedule(Event *event) {
    _next_event_id++;
    _queue.push(event);
    return event->getID();
}

void Scheduler::stop() {
    _stopped = true;
}

void Scheduler::cancel(int event_id) {
    _cancelled_event_ids.insert(event_id);
}

void Scheduler::run()
{
    _time = 0.0;

    // Initialization:
    for (auto& fn: _init_handlers) {
        _callback_e(fn, _context_owner);
    }

    // Main loop:
    while (!_queue.empty() && !_stopped)
    {
        Event *event = _queue.top();
        _queue.pop();

        auto cit = _cancelled_event_ids.find(event->getID());
        if (cit != _cancelled_event_ids.end()) {
            _cancelled_event_ids.erase(cit);
        } else {
            _time = event->getTime();
            const auto& hs = _handlers[event->getCode()];

            for (auto it = hs.begin(); it != hs.end(); it++) {
                switch (it->spec_type) {
                case SPECTYPE_EMPTY:
                    _callback_e(it->handler, _context_owner);
                    break;
                case SPECTYPE_INT:
                    _callback_i(it->handler, _context_owner, event->getIndex());
                    break;
                case SPECTYPE_PYOBJ:
                    _callback_p(it->handler, _context_owner, event->getAtt());
                    break;
                default:
                    _callback_ip(it->handler, _context_owner,
                                 event->getIndex(), event->getAtt());
                    break;
                }
            }
        }

        delete event;
    }
}

}}
