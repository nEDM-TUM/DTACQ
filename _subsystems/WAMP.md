---
title: WAMP
description: WAMP server interface to digitizer classes
layout: basic
---

## WAMP server

This provides a server that allows communication with DTACQ cards use
WebSockets (e.g. through a web browser).  The server itself is written in
python and requires the following packages:

* [`twisted`](https://twistedmatrix.com/trac/) - event-driven networking engine
* [`autobahn`](http://autobahn.ws/python/) - web-socket communication
* [`clint`](https://pypi.python.org/pypi/clint/) - for some nice command-line tools
* [`numpy`](http://www.numpy.org/) - arrays/data handling
* [`pynedm`]({{ site.url }}/Python-Slow-Control) - communication with database
* [`paramiko`](http://www.paramiko.org/) - SSH communication

## Getting started

For running as a `daemon` (e.g. in production), please see [here](WAMPAdministration).

This is as simple as running the code (make sure `PYTHONPATH` is set correctly
to be able to pull in `dtacq`):

{% highlight python %}
from dtacq import ShipData

if __name__ == '__main__':
   from twisted.python import log
   from twisted.internet import reactor
   import sys

   log.startLogging(sys.stdout)

   from autobahn.twisted.websocket import WebSocketServerFactory
   factory = WebSocketServerFactory()
   factory.protocol = ShipData

   reactor.listenTCP(port=9000, factory=factory)
   reactor.run()
{% endhighlight %}

## `dtacq` Modules

`dtacq` is broken into several modules:

* database - handles communications with the database (e.g. uploading of files
and measurements)
* cards - supported cards.  Here's where one would put new cards.
* decorators - some decorators to ensure that cards are running/not running.
* digitizer_utils - utilities, including communication with the digitizer cards via SSH
* readout - objects performing actual readout of the system.  These classes
also communicate with the web interface.
* settings - module handling import of settings from the environment
* trigger - handles user-written triggers
* web_interface - class to handle interaction with the browser via web-sockets.

Please see the code for more details here.
