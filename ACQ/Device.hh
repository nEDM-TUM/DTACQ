#ifndef _ACQ_Device_hh_
#define _ACQ_Device_hh_

#include <string>
#include <boost/asio/ip/tcp.hpp>
#include <boost/timer/timer.hpp>
#include <boost/thread.hpp>
#include <boost/thread/mutex.hpp>
#include <boost/lockfree/queue.hpp>
#include <boost/function.hpp>

namespace acq {

class Device {
  public:
    typedef std::vector< uint16_t > data_type;
    typedef boost::shared_ptr<data_type> ptr_type;
    typedef boost::function<void (ptr_type)> callback_functor;

    Device(const std::string& ipAddr = "");
    Device(const Device&);

    std::string SendCommand(const std::string& cmd);

    void ResetIPAddress(const std::string& ipAddr);
    std::string IPAddress() const;

    void BeginReadout(size_t bufferSize = 1024*1024);

    void BeginReadout(
            callback_functor CallBack, 
            size_t bufferSize = 1024*1024);
    void StopReadout();
  protected:
    Device& operator=(const Device&);

    typedef boost::asio::ip::tcp::socket sock_type;
    typedef boost::timer::cpu_timer timer_type;
    typedef boost::recursive_mutex mutex;
    typedef boost::lockfree::queue<data_type*, boost::lockfree::capacity<50> > queue_type;

    sock_type m_ServiceSocket;
    sock_type m_DataSocket;
    data_type m_DataBuffer;
    timer_type m_Timer;
    mutable size_t m_DataRead;

    boost::thread m_workerThread;
    mutex m_DataSocketMutex;
    queue_type m_Queue;

    void PushOnQueue(const data_type& dat, size_t len);
    void ConsumeFromQueue(callback_functor, data_type*);
    void AnalysisThread(callback_functor func);

    void DefaultReadout(ptr_type) const;

    void DoSingleRead();
    void HandleRead(const boost::system::error_code& err,
                    std::size_t bytes_transferred);

};

}

#endif /* _ACQ_Device_hh_ */
