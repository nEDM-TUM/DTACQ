#ifndef _ACQ_Device_hh_
#define _ACQ_Device_hh_

#include <string>
#include <boost/asio/ip/tcp.hpp>
#include <boost/thread.hpp>
#include <boost/thread/mutex.hpp>
//#include <boost/lockfree/queue.hpp>
#include <boost/function.hpp>
#include "CircularBuffer.hh"

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

    size_t NumSites() const { return m_numSites; }
    size_t NumChannels(size_t site_no) const { return m_Channels[site_no]; }
  protected:
    Device& operator=(const Device&);

    typedef boost::asio::ip::tcp::socket sock_type;
    typedef boost::recursive_mutex mutex;
    //typedef boost::lockfree::queue<data_type*, boost::lockfree::capacity<1000> > queue_type;
    typedef bounded_buffer<data_type*> queue_type;
    typedef std::vector<size_t> chan_number_type;

    sock_type m_ServiceSocket;
    sock_type m_DataSocket;
    data_type m_DataBuffer;
    mutable size_t m_DataRead;

    boost::thread m_workerThread;
    mutex m_DataSocketMutex;
    queue_type m_Queue;

    size_t m_numSites;
    chan_number_type m_Channels;

    void PushOnQueue(const data_type& dat, size_t len);
    void ConsumeFromQueue(callback_functor, data_type*);
    void AnalysisThread(callback_functor func);

    void DefaultReadout(ptr_type) const;

    void DoSingleRead();
    void HandleRead(const boost::system::error_code& err,
                    std::size_t bytes_transferred);

    void CloseSocket(sock_type&);

};

}

#endif /* _ACQ_Device_hh_ */
