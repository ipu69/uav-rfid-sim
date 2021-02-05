//
// Created by Andrey Larionov on 09.06.2020.
//

#ifndef CSURM_SCHEDULER_H
#define CSURM_SCHEDULER_H

#include <queue>
#include <map>
#include <unordered_set>
#include <functional>
#include <Python.h>

namespace csurm {

class Event {
public:
  Event(int id, int code, float time, int index, PyObject *att = nullptr);
  Event(const Event& other);
  ~Event();

  inline int getID() const { return _id; }
  inline int getCode() const { return _code; }
  inline float getTime() const { return _time; }
  inline int getIndex() const { return _index; }
  inline PyObject *getAtt() const { return _att; }

  bool operator<(const Event& rside) const;

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



typedef void (*CyCallback)(void*, PyObject*, int, PyObject*);


class Scheduler {
public:
  Scheduler();
  ~Scheduler();

  void set_cy_callback(CyCallback fn);

  void attach_handler(int code, void *handler);

  inline void set_context_owner(PyObject* owner) { _context_owner = owner; }

  int schedule(float time, int code, int index = 0, PyObject *att = nullptr);
  void cancel(int event_id);

  inline float get_time() const { return _time; }

  void run();

private:
  CyCallback _callback;
  std::priority_queue<Event*, std::vector<Event*>, EventPtrComparator> _queue;
  std::unordered_set<int> _cancelled_event_ids;
  int _next_event_id;
  std::map<int, std::vector<void*> > _handlers;
  float _time;
  PyObject *_context_owner;
};

}

#endif //CSURM_SCHEDULER_H
