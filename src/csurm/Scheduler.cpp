//
// Created by Andrey Larionov on 09.06.2020.
//

#include "Scheduler.h"

namespace csurm {

/******** EVEMT *******************/
Event::Event(int id, int code, float time, int index, PyObject *att)
    : _id(id), _code(code), _time(time), _index(index), _att(att) {
  if (_att) {
    Py_INCREF(_att);
  }
}

Event::Event(const Event &other)
    : _id(other._id), _code(other._code), _time(other._time), _index(other._index),
      _att(other._att) {
  if (_att) {
    Py_INCREF(_att);
  }
}

Event::~Event() {
  if (_att) {
    Py_DECREF(_att);
  }
}

bool Event::operator<(const Event &rside) const {
  return this->_time < rside.getTime() || (
      this->_time == rside.getTime() && this->_id < rside.getID()
  );
}


/******* COMPARATOR **************/
bool EventPtrComparator::operator()(Event *lside, Event *rside) {
  return *rside < *lside;
}


/******* SCHEDULER **************/
Scheduler::Scheduler() : _callback(nullptr), _next_event_id(1), _time(0.0), _context_owner(nullptr) {
  ; // nop
}

Scheduler::~Scheduler() {
  while (!_queue.empty()) {
    Event *top = _queue.top();
    delete top;
    _queue.pop();
  }
}

void Scheduler::set_cy_callback(CyCallback fn) {
  _callback = fn;
}

void Scheduler::attach_handler(int code, void *handler) {
  _handlers[code].push_back(handler);
}

int Scheduler::schedule(float time, int code, int index, PyObject *att) {
  int event_id = _next_event_id;
  auto *event = new Event(event_id, code, time, index, att);
  _next_event_id++;
  _queue.push(event);
  return event_id;
}

void Scheduler::cancel(int event_id) {
  _cancelled_event_ids.insert(event_id);
}

void Scheduler::run() {
  _time = 0.0;
  while (!_queue.empty()) {
    Event *event = _queue.top();
    _queue.pop();

    auto cit = _cancelled_event_ids.find(event->getID());
    if (cit != _cancelled_event_ids.end()) {
      _cancelled_event_ids.erase(cit);
    } else {
      _time = event->getTime();
      const std::vector<void *> &hs = _handlers[event->getCode()];
      for (auto it = hs.begin(); it != hs.end(); it++) {
        _callback(*it, _context_owner, event->getIndex(), event->getAtt());
      }
    }

    delete event;
  }
}
}
