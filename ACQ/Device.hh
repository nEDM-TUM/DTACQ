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

    template < typename T >
    class DevTempl {
      public:
        typedef typename std::vector< T > data_type;
        typedef typename boost::shared_ptr< data_type > ptr_type;
        typedef typename boost::function< void (ptr_type) > callback_functor;

    };

    Device(const std::string& ipAddr = "");
    Device(const Device&);

    std::string SendCommand(const std::string& cmd);

    void ResetIPAddress(const std::string& ipAddr);
    std::string IPAddress() const;

    void BeginReadout(size_t bufferSize = 1024*1024);

	// Following function will abort if the correct size (in typename) isn't
	// called.  At the moment, only int16_t and int32_t are implemented
	template<typename T>
    void BeginReadout(
            typename DevTempl<T>::callback_functor func,
            size_t bufferSize = 1024*1024);

    void StopReadout();

    bool IsRunning() const;

    size_t NumSites() const { return m_numSites; }
    size_t NumChannels(size_t site_no) const { return m_Channels[site_no]; }
    size_t ReadoutSize() const { return m_ReadoutSize; }
  protected:

    // Disable copy operator
    Device& operator=(const Device&);

    typedef boost::asio::ip::tcp::socket sock_type;
    typedef boost::recursive_mutex mutex;
    typedef std::vector<size_t> chan_number_type;

    sock_type m_ServiceSocket;
    sock_type m_DataSocket;
    mutable size_t m_DataRead;

    boost::thread m_workerThread;
    mutex m_DataSocketMutex;

    chan_number_type m_Channels;
    size_t m_numSites;
    size_t m_ReadoutSize;

    void CloseSocket(sock_type&);

};

}

#endif /* _ACQ_Device_hh_ */
