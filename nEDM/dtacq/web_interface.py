from autobahn.twisted.websocket import WebSocketServerProtocol
from twisted.internet import defer
import json
import traceback
import logging
import numpy
from .digitizer_utils import ReadoutException, ReleaseDigitizerNow
from .readout import ReadoutObj
available_urls = [
                "digitizer.1.nedm1",
                "digitizer.2.nedm1"
]
class ShipData(WebSocketServerProtocol):
   _readoutObjects = {}
   _connectedClients = set()
   def onMessage(self, payload, isBinary):
       retDic = {}
       retVal = None
       try:
         mess = json.loads(payload)
         retDic["cmd"] = mess["cmd"]
         obj = self
         if "ip" in mess:
           # Means we are referencing a digitizer
           ro = self.__class__._readoutObjects
           if self not in ro:
               raise ReadoutException("Digitizer control must first be requested")
           obj = ro[self]

         args = mess.get("args", {})
         retVal = getattr(obj, mess["cmd"])(**args)
         retDic["ok"] = True
       except ReleaseDigitizerNow:
         self.announce("Digitizer release requested by program")
         self.onMessage(json.dumps({ "cmd" : "releaseDigitizerControl"}), False)
         return
       except:
         retDic["error"]=traceback.format_exc(limit=1)
         logging.exception("onMessage")

       if isinstance(retVal, defer.Deferred):
           # handle deferred results especially
           retVal.addCallback(self.announce)
           retVal = None

       if "embed" in mess and retVal is not None:
         retDic["result"] = retVal
       retDic = self._buildHeader(retDic)
       if "embed" not in mess and retVal is not None:
         retDic += retVal
       self.sendMessage(retDic, isBinary = True)

   def requestDigitizerControl(self, **kw):
       ip = kw.get("ip_addr")
       ro = self.__class__._readoutObjects
       if self in ro:
           if ro[self].ip_addr == ip: return
           raise ReadoutException("Only one digitizer allowed at a time, release your current control")

       inv_map = dict([(v.ip_addr,k) for k,v in ro.items()])
       if ip in inv_map:
           raise ReadoutException("Digitizer already controlled elsewhere ({})".format(inv_map[ip].req.peer))

       if ip not in available_urls:
         raise ReadoutException("'%s' not available" % ip)
       # OK, we can give control
       ro[self] = ReadoutObj(ip)


   def releaseDigitizerControl(self, **kw):
       ro = self.__class__._readoutObjects
       if self in ro:
           ro[self].safeShutdown()
           ip = ro[self].ip_addr
           del ro[self]
           for s in self.__class__._connectedClients:
               if s == self: continue
               s.announce("'{}' digitizer released by '{}'".format(ip,self.req.peer))

   def announce(self, msg):
       self.sendMessage(self._buildHeader(dict(cmd="announce",msg=msg,ok=True)), isBinary = True)

   def _buildHeader(self, hdr):
       hdr = json.dumps(hdr)
       while len(hdr) % 4 != 0:
         hdr += " "
       return numpy.array([len(hdr)], dtype=numpy.int32).tostring() + hdr

   def onConnect(self, request):
      pr = request.peer
      #if pr.split(':')[1] != "192.168.1.113": raise HttpException("Currently under work")
      self.__class__._connectedClients.add(self)
      self.req = request
      logging.info("Client connecting: {}".format(pr))

   def onOpen(self):
      logging.info("WebSocket connection open.")

   def onClose(self, wasClean, code, reason):
      self.releaseDigitizerControl()
      try:
        self.__class__._connectedClients.remove(self)
      except: pass

   def initializeWebPage(self):
      return dict(urls=available_urls)

