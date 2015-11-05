---
title: ACQ
description: C++ classes for communicating with D-tAcq digitizer cards over sockets.
layout: basic
---

## `acq::Device`

This provides the basic interface to communicate with a digitizer
card.  Some example code:

{% highlight cpp %}
#include "ACQ/Device.hh"
#include <iostream>

using namespace std;

int main(int argc, char** argv)
{
  if (argc != 2) {
    cout << "Usage: prog ip_addr_of_digitizer" << endl;
    return 1;
  }
  acq::Device dev(argv[1]);
  cout << "IP Address: " << dev.IPAddress() << endl;
  cout << "Num sites: " << dev.NumSites() << endl;
  for (size_t i=0; i<dev.NumSites(); i++ ) {
    cout << "  Site: " << i << ", Num channels: " << dev.NumChannels(i) << endl;
  }
  cout << "size of ADC word (bytes): " << dev.ReadoutSize() << endl;

  cout << "Help output: " << endl << dev.SendCommand("help") << endl;

  return 0;
}
{% endhighlight %}

## Readout streaming

Readout is handled by pulling data from a TCP socket as fast as possible.
This data is read out in buffer-size chunks and passed on to a function defined
by the user.  This can be seen in the following code:

{% highlight cpp %}
#include "ACQ/Device.hh"
#include <iostream>
#include <chrono>
#include <thread>

using namespace std;

int main(int argc, char** argv)
{
  if (argc != 2) {
    cout << "Usage: prog ip_addr_of_digitizer" << endl;
    return 1;
  }
  acq::Device dev(argv[1]);
  cout << "IP Address: " << dev.IPAddress() << endl;
  cout << "Num sites: " << dev.NumSites() << endl;

  typedef int16_t readoutType;  // 16-bit cards
  //typedef int32_t readoutType; // 32-bit cards
  dev.BeginReadout<readoutType>( [] (acq::Device::DevTempl<readoutType>::ptr_type ptr) {
    // This function runs in a separate thread
    cout << (*ptr)[0] << endl;
  },
  1024*1024 // Buffer size (in bytes)
  );

  // Wait for 2 s then call stop
  std::this_thread::sleep_for(std::chrono::seconds(2));
  dev.StopReadout();

  return 0;
}
{% endhighlight %}

