#include "Device.hh"
#include <boost/asio/connect.hpp>
#include <boost/asio/streambuf.hpp>
#include <boost/asio/write.hpp>
#include <boost/asio/read_until.hpp>
#include <boost/asio/read.hpp>
#include <boost/bind.hpp>
#include <boost/asio/placeholders.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include <iostream>

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

    io_type& Service()
    {
      return m_IOService;
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
  m_ServiceSocket(IOService::IO().Service()),
  m_DataSocket(IOService::IO().Service())
{
  ResetIPAddress(ipAddr);
}

//-----------------------------------------------------------------
Device::Device(const Device& dev) :
  m_ServiceSocket(IOService::IO().Service()),
  m_DataSocket(IOService::IO().Service())
{
  ResetIPAddress(dev.IPAddress());
}

//-----------------------------------------------------------------
void Device::ResetIPAddress(const std::string& ipAddr)
{
  // Close both services
  if (m_ServiceSocket.is_open()) m_ServiceSocket.close();
  if (m_DataSocket.is_open()) m_DataSocket.close();

  // Open up the command service
  tcp::resolver res(IOService::IO().Service()); 
  tcp::resolver::iterator endpts = res.resolve(tcp::resolver::query(ipAddr, "4220"));
  boost::asio::connect(m_ServiceSocket, endpts);
  //m_ServiceSocket.set_option( boost::asio::socket_base::keep_alive(true) );
  SendCommand("prompt on");
}

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
void Device::BeginReadout(size_t bufferSize)
{
  BeginReadout(boost::bind(&Device::DefaultReadout, this, _1), bufferSize);
}


//-----------------------------------------------------------------
void Device::BeginReadout(Device::callback_functor func, size_t bufferSize)
{

  mutex::scoped_lock sL(m_DataSocketMutex); 
  //if (!m_workerThread.try_join_for(boost::chrono::milliseconds(0))) {
  //  return;
  //}
  StopReadout();


  // Resize local buffer
  m_DataBuffer.resize(bufferSize); 

  // Opem 
  tcp::resolver res(IOService::IO().Service()); 
  tcp::resolver::iterator endpts = res.resolve(tcp::resolver::query(IPAddress(), "4210"));
  boost::asio::connect(m_DataSocket, endpts);
  m_DataRead = 0;
  m_Timer.start();
  // Start processing thread
  m_workerThread = boost::thread(boost::bind(&Device::AnalysisThread, this, func));

  DoSingleRead();
}

//-----------------------------------------------------------------
void Device::AnalysisThread(Device::callback_functor func)
{
  std::cout << "Analysis thread start" << std::endl;
  boost::function< void(data_type*) > myFunc = boost::bind(&Device::ConsumeFromQueue, this, func, _1); 
  while( m_DataSocket.is_open() ) {
    if( !m_Queue.consume_one( myFunc ) ) {
      boost::this_thread::sleep(boost::posix_time::milliseconds(100));
    }
  } 

  // If we get here the socket has been closed, consume the rest of the data
  m_Queue.consume_all( myFunc );
  std::cout << "Analysis thread done" << std::endl;
}

//-----------------------------------------------------------------
void Device::StopReadout()
{
  mutex::scoped_lock sL(m_DataSocketMutex); 
  if (m_DataSocket.is_open()) m_DataSocket.close();
  m_Timer.stop();
  m_workerThread.join();
}


//-----------------------------------------------------------------
void Device::PushOnQueue(const Device::data_type& dat, size_t len)
{
  m_Queue.push( new data_type(dat.begin(), dat.begin() + len) );
}

//-----------------------------------------------------------------
void Device::ConsumeFromQueue(Device::callback_functor func, Device::data_type* dat)
{
  func(ptr_type(dat));
}

//-----------------------------------------------------------------
void Device::DoSingleRead()
{
  m_DataSocket.async_receive(
        boost::asio::buffer(m_DataBuffer, m_DataBuffer.size()*sizeof(m_DataBuffer[0])),
        boost::bind(&Device::HandleRead, this, 
             boost::asio::placeholders::error,
             boost::asio::placeholders::bytes_transferred));
}

//-----------------------------------------------------------------
void Device::HandleRead(const boost::system::error_code&,
                std::size_t bytes_transferred)
{
  PushOnQueue(m_DataBuffer, bytes_transferred/sizeof(m_DataBuffer[0]));
  if (m_DataSocket.is_open()) DoSingleRead();
}

void Device::DefaultReadout(ptr_type dat) const
{
  m_DataRead += dat->size(); 
}

}

