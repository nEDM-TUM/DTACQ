"""
  Provides a WAMP server for D-TACQ digitizers.  Also allows saving data in DB
"""

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
