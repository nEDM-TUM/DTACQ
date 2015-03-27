"""
  Provides a WAMP server for D-TACQ digitizers.  Also allows saving data in DB
"""

from autobahn.twisted.websocket import WebSocketServerProtocol
import pyacq
import time
import numpy
import sys
import threading
import json
import os
import ctypes
import datetime
import cloudant
from twisted.python import log
from twisted.internet import reactor, defer, threads
import time
import traceback


class ReadoutException(Exception):
    pass

_db_url = "http://localhost:5984"
_db_name = "nedm%2Fmeasurements"
_un = "digitizer_writer"
_pw="""pw"""

def _performUpload(**kw):
    doc_to_post = kw.get("doc_to_save",{}) 
    doc_to_post["type"] = "measurement"

    # Post the doc
    acct = cloudant.Account(uri=_db_url) 
    acct.login(_un, _pw)
    db = acct[_db_name]
    resp = db.design("nedm_default").post("_update/insert_with_timestamp",params=doc_to_post).json()

    if "ok" not in resp:
        return "Measurement could not be saved"

    if "filename" not in doc_to_post: 
        resp["type"] = "DocUpload"
        return resp 

    fn = doc_to_post["filename"] 
    doc = db[resp['id']]
    rev = doc.get().json()['_rev']
    with open(fn, 'rb') as f:
        resp = doc.attachment(fn + "?rev=" + rev).put(data=f,headers={'content-type' : 'application/octet-stream'}).json()

    if "ok" in resp:
        resp["url"] = "/_couchdb/{}/{}/{}".format(_db_name,resp["id"],fn)  
        resp["file_name"] = fn 
        resp["type"] = "FileUpload"
    return resp


class ReadoutObj(object):
    def __init__(self, ip_addr):
        self.ip_addr = ip_addr
        dev = pyacq.Device(str(ip_addr))
        # Tell device to transmit verification data in the stream
        dev.SendCommand("set.site 0 spad 1,2,0")
        dev.SendCommand("run0 1,2")
        # Available sites in the device
        self.available_modules = dict([(i+1, dev.NumChannels(i)) for i in range(dev.NumSites())])
        # total number of channels available
        self.total_ch =  int(dev.SendCommand("NCHAN")) 
        self.actual_ch =  sum(self.available_modules.values())
        self.check_word = self.actual_ch
        self.dev = dev

        self.alock = threading.Lock()
        self.cond = threading.Condition(self.alock)
        self.obj_buffer = None 
        self.open_file = None
        self.isRunning = False
        self.should_save = False
        self.should_upload = False
        self._cl = []

    def _add_to_list(self, al):
        self.cond.acquire()
        self.obj_buffer = al
        self.cond.notify()
        self.cond.release()
    
    def _pop_from_list(self):
        anobj = None
        self.cond.acquire()
        while self.obj_buffer is None: 
            self.cond.wait(1.0)
            if self._exc is not None:
                self.obj_buffer = None
                break
        anobj = self.obj_buffer 
        self.obj_buffer = None 
        self.cond.release()

        if anobj is None or len(anobj) > 0:
            return anobj
        return self._pop_from_list()
     
    def _ensureNotRunning(self):
        if self.isRunning:
            raise ReadoutException("Cannot call function while readout running")
    
    def _ensureRunning(self):
        if not self.isRunning:
            raise ReadoutException("Cannot call function while readout is idle")

    def getChannels(self, **kw):
	return self.total_ch

    def closeFile(self, **kw):
        if self.open_file is not None: self.open_file.close()      
        self.open_file = None

    def startReadout(self, **kw):
        self._ensureNotRunning()
        buffer_size = kw.get("buffer_size", 1*1024*1024)
        bytes_per_frame = self.total_ch*2
        buffer_size += (bytes_per_frame - (buffer_size % bytes_per_frame))
        self.last_offset = 0
        self.should_upload = False 
        self.last_counter = 0 
        self._exc = None
        if kw.get("should_upload", False):
            self.should_upload = True
            dt = str(datetime.datetime.utcnow())
            freq = int(self.dev.SendCommand("get.site 1 sysclkhz"))/int(self.dev.SendCommand("get.site 1 clkdiv"))
            header = { "channels" : self.total_ch, 
                       "log" : kw.get("log", ""), 
                       "bit_depth" : 2, 
                       "bit_mask" : 0xff, 
                       "ip" : self.ip_addr, 
                       "date" : dt, 
                       "freq_hz" : freq, 
                       "measurement_name" : "Digitizer " + self.ip_addr, 
                       "channel_list" : kw.get("channel_list", [])
                     }
            self._cl = header["channel_list"]
            for k, v in kw.get("logitems", {}).items():
                header[k] = v
            if kw.get("should_save", False):
                file_name = dt + ".dig" 
                if os.path.exists(file_name): 
                    raise ReadoutException("'%s' exists, not overwriting" % file_name)
                self.open_file = open(file_name, "wb")
                header["filename"] = file_name 
                header_b = bytearray(json.dumps(header))
                self.open_file.write(bytearray(ctypes.c_uint32(len(header_b))) + header_b)
            self.doc_to_save = header
        self.dev.BeginReadout(function=self, buffer_size=buffer_size)
        self.isRunning = True

        def waitToFinish(s, d=None): 
            if not d:
                d = defer.Deferred()
            if s.dev.IsRunning():
                reactor.callLater(1, waitToFinish, s, d)
            else:
                if not s._exc:
                    d.callback(dict(type="JobFinished", msg="Readout job completed"))
                else:
                    d.callback(dict(type="JobFinished", error=self._exc))
            return d
        return waitToFinish(self)

    def stopReadout(self, **kw):
        self._ensureRunning()
        self.dev.StopReadout()
        self.closeFile()
        self.isRunning = False
        if self.should_upload:
            return threads.deferToThread(_performUpload, doc_to_save=self.doc_to_save)

    def readBuffer(self, **kw):
        self._ensureRunning()
        chans = kw.get("channels", [])
        # build load into a stream
        header = [len(chans)]
        header.extend(chans)
        header = numpy.array(header, dtype=numpy.int32)
        header = header.tostring()
        al = self._pop_from_list()
        if al is None:
            raise ReadoutException("Readout unexpectedly ended!")
        return header + numpy.array([al[ch::self.total_ch] for ch in chans]).tostring()

    def _validateData(self, v):
        ch = self.total_ch
        full_pts = len(v)/ch
        last_set = v[(full_pts-1)*ch:]
        cw = self.check_word
        total_counter = numpy.fromstring(numpy.array(last_set[cw:cw+2]).tostring(), numpy.uint32)[0]
        self.last_counter += full_pts
        self.last_counter %= 0xFFFFFFFF
        if self.last_counter != (total_counter % 0xFFFFFFFF):
            raise ReadoutException("ReadoutBuffer corrupted")
        
    def _writeToFile(self, v, afile, ch_list):
        ch = self.total_ch
        t = [v[c::ch] for c in ch_list]
        numpy.array(t).T.tofile(afile)

    def __call__(self, x):
        try:
           v = x.vec()
           if self.last_offset != 0: 
               raise ReadoutException("Buffer not aligned")
           self._validateData(v)
           if self.open_file:
               self._writeToFile(v, self.open_file, self.doc_to_save["channel_list"])
           ch = self.total_ch
           start_pt = (ch - self.last_offset) % ch
           end_pt = (len(v)-start_pt) % ch
           t = v[start_pt:]
           self.last_offset += end_pt 
           self._add_to_list(t)
        except Exception as e:
           self._exc = traceback.format_exc()
           print self._exc 
           raise

    def safeShutdown(self):
        if self.isRunning: self.stopReadout()
        
available_urls = [
		"digitizer.1.nedm1"
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
       except Exception as e:
         retDic["error"]=traceback.format_exc()
         print retDic["error"]
         pass

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
      self.__class__._connectedClients.add(self)
      self.req = request
      print("Client connecting: {}".format(request.peer))

   def onOpen(self):
      print("WebSocket connection open.")

   def onClose(self, wasClean, code, reason):
      self.releaseDigitizerControl()
      self.__class__._connectedClients.remove(self)
      print("WebSocket connection closed: {}".format(reason))

   def initializeWebPage(self):
      return dict(urls=available_urls)
        

if __name__ == '__main__':
   import sys
 
   log.startLogging(sys.stdout)
 
   from autobahn.twisted.websocket import WebSocketServerFactory
   factory = WebSocketServerFactory()
   factory.protocol = ShipData

   reactor.listenTCP(9000, factory)
   reactor.run()
