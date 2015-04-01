#ifndef GIL_STATE_H
#define GIL_STATE_H
#include <boost/python.hpp>

struct release_gil_policy
{
  release_gil_policy() : 
    _currentState(PyEval_SaveThread())
  {
  }

  ~release_gil_policy() 
  {
    PyEval_RestoreThread(_currentState);
  }
  PyThreadState* _currentState;
};

struct ensure_gil_state
{
  ensure_gil_state() :
    _state(PyGILState_Ensure())
  {
  }

  ~ensure_gil_state()
  {
    PyGILState_Release(_state);
  }
  PyGILState_STATE _state;
};



#endif
