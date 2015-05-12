#include "Device.hh"
#include <boost/asio/connect.hpp>
#include <boost/asio/streambuf.hpp>
#include <boost/asio/write.hpp>
#include <boost/asio/read_until.hpp>
#include <boost/asio/read.hpp>
#include <boost/bind.hpp>
#include <boost/lexical_cast.hpp>
#include <boost/asio/placeholders.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include <iostream>
#include <sstream>

namespace acq {

class socket_complete : public std::exception
{};

using boost::asio::ip::tcp;

//-----------------------------------------------------------------
Device::Device(const std::string& ipAddr) :
  m_IOWork(new work_type(m_IOService)),
  m_IOThread([this] { m_IOService.run(); })
{
  ResetIPAddress(ipAddr);
}

//-----------------------------------------------------------------
Device::Device(const Device& dev) :
  m_IOWork(new work_type(m_IOService)),
  m_IOThread([this] { m_IOService.run(); })
{
  ResetIPAddress(dev.IPAddress());
}

//-----------------------------------------------------------------
void Device::ResetIPAddress(const std::string& ipAddr)
{
  // Close both services
  m_ServiceSocket.reset( new sock_type(m_IOService) ); 
  m_DataSocket.reset(); 

  // Open up the command service
  tcp::resolver res(m_IOService);
  tcp::resolver::iterator endpts = res.resolve(tcp::resolver::query(ipAddr, "4220"));
  try {
    boost::asio::connect(*m_ServiceSocket, endpts);
  } catch (...) {
    Cleanup();
    throw;  // Throw up to top level
  }
  //m_ServiceSocket.set_option( boost::asio::socket_base::keep_alive(true) );
  SendCommand("prompt on");
  m_numSites = 0;
  m_Channels.clear();
  for( size_t i=0;;i++) {
    try {
      std::ostringstream os;
      os << "get.site " << i+1 << " NCHAN";
      m_Channels.push_back(boost::lexical_cast<size_t>(SendCommand(os.str())));
    } catch (boost::bad_lexical_cast &) {
      // Just means we couldn't find anymore sites
      break;
    }
  }
  m_numSites = m_Channels.size();
  if (boost::lexical_cast<size_t>(SendCommand("data32")) == 0) {
    m_ReadoutSize = 2;
  } else {
    m_ReadoutSize = 4;
  }
}

//-----------------------------------------------------------------

//-----------------------------------------------------------------
std::string Device::IPAddress() const
{
  return m_ServiceSocket->remote_endpoint().address().to_string();
}

//-----------------------------------------------------------------
std::string Device::SendCommand(const std::string& cmd)
{
  std::string loc_cmd = cmd + "\n";
  boost::system::error_code error;
  boost::asio::streambuf buffer;
  boost::asio::write(*m_ServiceSocket, boost::asio::buffer(loc_cmd, loc_cmd.size()));
  size_t n = boost::asio::read_until(*m_ServiceSocket, buffer, ">", error);
  boost::asio::streambuf::const_buffers_type bufs = buffer.data();
  std::string retStr(
     boost::asio::buffers_begin(bufs),
     boost::asio::buffers_begin(bufs) + n);

  // Remove the prompt
  size_t last_n = retStr.find_last_of("\n");
  return retStr.substr(0, last_n);
}


//-----------------------------------------------------------------
template<typename T>
void Device::BeginReadout(typename Device::DevTempl<T>::callback_functor func, size_t bufferSize)
{
  typedef typename DevTempl<T>::data_type dt;
  typedef typename DevTempl<T>::ptr_type pt;
  typedef bounded_buffer< dt* > queue_type;

  // Static so they don't go out of scope.  *Note*, these are *class* variables
  // for a particular readout type (uint32/uint16)
  static dt m_DataBuffer;
  static queue_type m_Queue(4000);
  static std::function<void ()> DoSingleRead;

  // Empty the queue
  auto emptyQ = [] (dt*) {; }; 
  m_Queue.consume_all_no_lock(emptyQ); 

  mutex::scoped_lock sL(m_DataSocketMutex);
  m_DataSocket.reset( new sock_type( m_IOService ) );
  assert(ReadoutSize() == sizeof(m_DataBuffer[0]));

  //StopReadout();

  // Resize local buffer
  m_DataBuffer.resize(bufferSize);

  /////////////////////////////////////////////////////////////////
  // DoSingleRead lambda
  // Analysis thread
  auto AnalysisThread = [&,this,func]()
  {
    auto ConsumeFromQueue = [func] (dt* dat) {
      if (!dat || dat->size() == 0) throw socket_complete();
      func(pt(dat));
    };
    try {
      while (1) {
        if( !m_Queue.consume_one( ConsumeFromQueue ) ) {
          boost::this_thread::sleep(boost::posix_time::milliseconds(1));
        }
      }
    } catch (socket_complete&) {
      // If we get here the socket has been closed, consume the rest of the data
      std::cout << "Readout complete" << std::endl;
      
    } catch(...) {
      std::cerr << "Exception caught in readout, stopping socket" << std::endl;
      try{
        // This can also throw, e.g. if the socket is not currently open, simply catch.
        m_DataSocket->shutdown(sock_type::shutdown_both);
      } catch(boost::system::system_error& e) {
        std::cerr << "Exception in shutdown: " << e.what() << std::endl;
      }
    }
    m_isRunning = false;
  };
  /////////////////////////////////////////////////////////////////


  // Open socket to read
  tcp::resolver res(m_IOService);
  tcp::resolver::iterator endpts = res.resolve(
    tcp::resolver::query(IPAddress(), "4210"));

  boost::asio::connect(*m_DataSocket, endpts);
  m_DataRead = 0;

  // Start processing thread
  m_isRunning = true;
  m_workerThread = boost::thread(AnalysisThread);
  DoSingleRead = [&]()
  {
    auto HandleRead = [&](const boost::system::error_code& error,
                  std::size_t bytes_transferred) {
      if (bytes_transferred > 0) {
        m_Queue.push( new dt(m_DataBuffer.begin(),
          m_DataBuffer.begin() + bytes_transferred/sizeof(m_DataBuffer[0])) );
      }
      if (error == 0) {
        DoSingleRead();
      } else {
        std::cout << "Was shutdown, ec=" << error << std::endl;
        // This means we were shut down.
        // Make sure we insert a new set of data so it gets processed.
        m_Queue.push( new dt() );
      }
    };

    boost::asio::async_read(
          *m_DataSocket,
          boost::asio::buffer(m_DataBuffer,
            m_DataBuffer.size()*sizeof(m_DataBuffer[0])),
            HandleRead);
  };

  DoSingleRead();
}

//-----------------------------------------------------------------
void Device::BeginReadout(size_t bufferSize)
{
  #define BEGINREADOUTYPE(atype) \
    case sizeof(atype):          \
      BeginReadout<atype>( [this] (DevTempl<atype>::ptr_type pt) { \
        m_DataRead += pt->size();                                  \
      }, bufferSize); break;
  switch(ReadoutSize()) {
    BEGINREADOUTYPE(int16_t)
    BEGINREADOUTYPE(int32_t)
  }
}


//-----------------------------------------------------------------
void Device::StopReadout()
{
  mutex::scoped_lock sL(m_DataSocketMutex);
  if (m_isRunning) {
    try {
      m_DataSocket->shutdown(sock_type::shutdown_both);
    } catch(boost::system::system_error& ec) {
      std::cout << "Error seen by shutdown, was it already shutdown?" << std::endl;
      std::cout << ec.what() << std::endl;
    }
  }
  m_workerThread.join();
}


bool Device::IsRunning() const
{
  // return true if running, false if not
  return m_isRunning;
}

Device::~Device()
{
  std::cout << " Destructing device: " << IPAddress() << std::endl;
  Cleanup();
}

//-----------------------------------------------------------------
void Device::Cleanup()
{
  m_ServiceSocket.reset();
  m_DataSocket.reset();
  m_IOWork.reset();
  m_IOThread.join();
}

#define INSTANTIATE_TEMPLATE(atype) \
template void Device::BeginReadout<atype>(Device::DevTempl<atype>::callback_functor, size_t);

INSTANTIATE_TEMPLATE(int16_t)
INSTANTIATE_TEMPLATE(int32_t)

}



