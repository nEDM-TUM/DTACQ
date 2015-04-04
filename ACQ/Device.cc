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

using boost::asio::ip::tcp;

typedef boost::asio::io_service io_type;
typedef boost::asio::io_service::work work_type;

class IOService {
  public:
    static IOService& IO()
    {
      static IOService gServiceSingleton;
      return gServiceSingleton;
    }

    static io_type& Service()
    {
      return IO().m_IOService;
    }

  private:
    IOService() : m_IOWork(m_IOService),
      m_Thread(boost::bind(&io_type::run, &m_IOService))
    {
    }
    ~IOService() { m_IOService.stop(); m_Thread.join(); }
    IOService(const IOService&);
    IOService& operator=(const IOService&);
    io_type     m_IOService;
    work_type   m_IOWork;
    boost::thread m_Thread;

};

//-----------------------------------------------------------------
Device::Device(const std::string& ipAddr) :
  m_ServiceSocket(IOService::Service()),
  m_DataSocket(IOService::Service())
{
  ResetIPAddress(ipAddr);
}

//-----------------------------------------------------------------
Device::Device(const Device& dev) :
  m_ServiceSocket(IOService::Service()),
  m_DataSocket(IOService::Service())
{
  ResetIPAddress(dev.IPAddress());
}

//-----------------------------------------------------------------
void Device::ResetIPAddress(const std::string& ipAddr)
{
  // Close both services
  if (m_ServiceSocket.is_open()) CloseSocket(m_ServiceSocket);
  if (m_DataSocket.is_open()) CloseSocket(m_DataSocket);

  // Open up the command service
  tcp::resolver res(IOService::Service());
  tcp::resolver::iterator endpts = res.resolve(tcp::resolver::query(ipAddr, "4220"));
  boost::asio::connect(m_ServiceSocket, endpts);
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
  return m_ServiceSocket.remote_endpoint().address().to_string();
}

//-----------------------------------------------------------------
std::string Device::SendCommand(const std::string& cmd)
{
  std::string loc_cmd = cmd + "\n";
  boost::system::error_code error;
  boost::asio::streambuf buffer;
  boost::asio::write(m_ServiceSocket, boost::asio::buffer(loc_cmd, loc_cmd.size()));
  size_t n = boost::asio::read_until(m_ServiceSocket, buffer, ">", error);
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

  DoSingleRead = [&]()
  {
    auto HandleRead = [&](const boost::system::error_code& error,
                  std::size_t bytes_transferred) {
      m_Queue.push( new dt(m_DataBuffer.begin(),
        m_DataBuffer.begin() + bytes_transferred/sizeof(m_DataBuffer[0])) );
      if (error == 0) {
        DoSingleRead();
      }
    };

    boost::asio::async_read(
          m_DataSocket,
          boost::asio::buffer(m_DataBuffer,
            m_DataBuffer.size()*sizeof(m_DataBuffer[0])),
            HandleRead);
  };


  assert(ReadoutSize() == sizeof(m_DataBuffer[0]));

  mutex::scoped_lock sL(m_DataSocketMutex);
  StopReadout();

  // Resize local buffer
  m_DataBuffer.resize(bufferSize);

  /////////////////////////////////////////////////////////////////
  // DoSingleRead lambda
  // Analysis thread
  auto AnalysisThread = [&,this,func]()
  {
    auto ConsumeFromQueue = [func] (dt* dat) {
      func(pt(dat));
    };
    try {
      while( m_DataSocket.is_open() ) {
        if( !m_Queue.consume_one( ConsumeFromQueue ) ) {
          boost::this_thread::sleep(boost::posix_time::milliseconds(1));
        }
      }

      // If we get here the socket has been closed, consume the rest of the data
      m_Queue.consume_all_no_lock( ConsumeFromQueue );
    } catch(...) {
      std::cerr << "Exception caught in readout, stopping socket" << std::endl;
      CloseSocket(m_DataSocket);
    }
  };
  /////////////////////////////////////////////////////////////////


  // Open socket to read
  tcp::resolver res(IOService::Service());
  tcp::resolver::iterator endpts = res.resolve(
    tcp::resolver::query(IPAddress(), "4210"));

  boost::asio::connect(m_DataSocket, endpts);
  m_DataRead = 0;

  // Start processing thread
  m_workerThread = boost::thread(AnalysisThread);

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
  if (m_DataSocket.is_open()) {
    CloseSocket(m_DataSocket);
  }
  m_workerThread.join();
}


void Device::CloseSocket(Device::sock_type& sock)
{
  IOService::Service().post( boost::bind( &sock_type::close, &sock ) );
}

bool Device::IsRunning() const
{
  // return true if running, false if not
  return m_DataSocket.is_open();
}

#define INSTANTIATE_TEMPLATE(atype) \
template void Device::BeginReadout<atype>(Device::DevTempl<atype>::callback_functor, size_t);

INSTANTIATE_TEMPLATE(int16_t)
INSTANTIATE_TEMPLATE(int32_t)

}



