#include "ACQ/Device.hh"
#include <boost/python.hpp>
#include <boost/python/make_function.hpp>
#include <boost/bind.hpp>
#include <boost/make_shared.hpp>
#include <boost/thread/thread.hpp>
#include <cstdlib>
#include <iostream>
#include <boost/python/suite/indexing/vector_indexing_suite.hpp>

// We don't want any deprecated numpy API
#define NPY_NO_DEPRECATED_API NPY_1_8_API_VERSION
#include "numpy/arrayobject.h"
#include "gil_state.h"

using namespace boost::python;
using namespace acq;

//-----------------------------------------------------------------
// Convert from Data type to python numpy array
template< typename T >
struct DataType_to_python_dat
{
    typedef typename Device::DevTempl<T>::data_type dt;
    static object convertObj(const dt& s)
    {
        npy_intp p = (npy_intp)s.size();
        PyObject* py_buffer;
        if (p > 0) {
          py_buffer = PyArray_SimpleNewFromData(
            1, // dimension
            &p,// array of dimension sizes
            (sizeof(s[0]) == 2) ? NPY_INT16 : NPY_INT32, // type
            (void*)&s[0] // address
          );
        } else {
          py_buffer = PyArray_SimpleNew(
            1, // dimension
            &p,// array of dimension sizes
            (sizeof(s[0]) == 2) ? NPY_INT16 : NPY_INT32 // type
          );
        }
        return boost::python::object(handle<>(py_buffer));
    }
    static PyObject* convert(const dt& s)
    {
      return convertObj(s).ptr();
    }
};

//-----------------------------------------------------------------
template< typename T >
class dev_buffer
{
  public:
    typedef typename Device::DevTempl<T>::ptr_type ptr_type;
    dev_buffer(ptr_type p) : _ptr(p) {}

    size_t size()
    {
      return _ptr->size();
    }

    object vec()
    {
      return DataType_to_python_dat<T>::convertObj(*_ptr);
    }

  private:
    ptr_type _ptr;
};

//-----------------------------------------------------------------
class PyDevice: public Device
{
  public:
    PyDevice(const std::string& ip) : Device(ip) {}
    void beginReadoutWrapper( object function,
      uint64_t buffer_size = 1024*1024 )
    {
        _func = function;
        #define READOUTTYPE(atype)                            \
        case sizeof(atype):                                   \
          BeginReadout<atype>( [this]                         \
              (DevTempl<atype>::ptr_type pt) {                \
            ensure_gil_state gS;                              \
            typedef dev_buffer<atype> db;                     \
            _func(boost::make_shared<db>(pt));                \
          }, buffer_size); break;

        switch( ReadoutSize() ) {
          READOUTTYPE(int16_t)
          READOUTTYPE(int32_t)
        }
    }

    std::string SendCommand(const std::string& cmd)
    {
      release_gil_policy sL;
      return Device::SendCommand(cmd);
    }

    void StopReadout()
    {
      release_gil_policy sL;
      return Device::StopReadout();
    }
  protected:
    object _func;

};


//-----------------------------------------------------------------
template <typename T>
void define_buffer(const std::string& aname)
{
  typedef dev_buffer<T> db;
  class_<db, boost::shared_ptr<db> >(aname.c_str(),
      boost::python::no_init)
    .def("__len__", &db::size)
    .def("vec", &db::vec);
}

//-----------------------------------------------------------------
BOOST_PYTHON_MODULE(pyacq)
{
  // We need threads
  PyEval_InitThreads();
  import_array();

  class_<PyDevice>("Device", init<const std::string&>())
    .def("SendCommand", &PyDevice::SendCommand)
    .def("StopReadout", &PyDevice::StopReadout)
    .def("NumSites", &PyDevice::NumSites)
    .def("NumChannels", &PyDevice::NumChannels)
    .def("IsRunning", &PyDevice::IsRunning)
    .def("ReadoutSize", &PyDevice::ReadoutSize)
    .def("BeginReadout", &PyDevice::beginReadoutWrapper,
      ( arg( "function" ), arg( "buffer_size" ) ));

  define_buffer<int16_t>("DevBuffer_16");
  define_buffer<int32_t>("DevBuffer_32");

}
