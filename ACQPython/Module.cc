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
namespace bp = boost::python;
using namespace acq;

// Wrapper for timer function parameter
typedef boost::function< void(Device::ptr_type) > func_type;
struct DataType_to_python_dat
{
    static bp::object convertObj(const Device::data_type& s)
    {
        npy_intp p[1] = { s.size() };
        PyObject* py_buffer = PyArray_SimpleNewFromData(1, p, NPY_INT16, (void*)&s[0]); 
        return boost::python::object(handle<>(py_buffer));
    }
    static PyObject* convert(const Device::data_type& s)
    {
      return convertObj(s).ptr(); 
    }
};


class dev_buffer
{
  public:
    dev_buffer(Device::ptr_type p) : _ptr(p) {}

    size_t size() { return _ptr->size(); }
    bp::object vec() { return DataType_to_python_dat::convertObj(*_ptr); }
    //Py_buffer* buf() 
    //{
    //  Py_buffer *b = (Py_buffer*) std::calloc(sizeof(*b)); 
    //  b->buf = &((*_ptr)[0]); 
    //  b->itemsize = sizeof((*_ptr)[0]);
    //  b->len = b->itemsize*_ptr->size();
    //  b->format = "H";
    //  return b;
    //}
  private:
    Device::ptr_type _ptr;
};




class PyDevice: public Device
{
  public:
    PyDevice(const std::string& ip) : Device(ip) {}
    void beginReadoutWrapper( bp::object function, uint64_t buffer_size = 1024*1024 )
    {
        _callable = function;
        BeginReadout( func_type( boost::bind(&PyDevice::PyCallback, this, _1) ), buffer_size );
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

  private:
    void PyCallback(ptr_type dat)
    {
      ensure_gil_state gS;
      _callable(boost::make_shared<dev_buffer>(dat));
    }

    bp::object _callable;
};

  

BOOST_PYTHON_MODULE(pyacq)
{
  // We need threads
  PyEval_InitThreads();
  import_array();
  bp::to_python_converter<Device::data_type, DataType_to_python_dat>();
  class_<PyDevice>("Device", init<const std::string&>())
    .def("SendCommand", &PyDevice::SendCommand) 
    .def("StopReadout", &PyDevice::StopReadout) 
    .def("NumSites", &PyDevice::NumSites)
    .def("NumChannels", &PyDevice::NumChannels)
    .def("IsRunning", &PyDevice::IsRunning)
    .def("BeginReadout", &PyDevice::beginReadoutWrapper, ( bp::arg( "function" ), bp::arg( "buffer_size" ) )); 

  //class_<Device::data_type>("DataVec")
  //  .def(bp::vector_indexing_suite<Device::data_type>());

  class_<dev_buffer, boost::shared_ptr<dev_buffer> >("Device_buffer", boost::python::no_init)
    .def("__len__", &dev_buffer::size)
    .def("vec", &dev_buffer::vec);
}
