---
title: ACQ
description: C++ classes for communicating with D-tAcq digitizer cards over sockets.
layout: basic
---

## `acq::Device`

This provides the basic interface to communicate with a digitizer
card.  Some example code:

{% highlight cpp %}

  Device dev("http://digitizer.1.nedm1"); // digitizer.1.nedm1 is an address
  cout << "IP Address: " << dev.IPAddress() << endl;
  cout << "IP Address: " << dev.IPAddress() << endl;


{% endhighlight %}
