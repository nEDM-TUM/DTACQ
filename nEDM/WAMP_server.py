"""
  Provides a WAMP server for D-TACQ digitizers.  Also allows saving data in DB
"""

from autobahn.twisted.websocket import WebSocketServerProtocol
from autobahn.websocket import http
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
from types import MethodType
from pynedm import ProcessObject
from clint.textui.progress import Bar as ProgressBar
#from card_communicate import execute_cmd

_db_url = os.environ["DB_URL"]
_db_name = os.environ["DB_NAME"]
_un = os.environ["DB_USER_NAME"]
_pw= os.environ["DB_PASSWORD"]

class ReadoutException(Exception):
    pass

class ReleaseDigitizerNow(Exception):
    pass

class UploadClass(object):
   def __init__(self, doc_to_save):
     self.doc_to_post = doc_to_save
     self.doc_to_post["type"] = "measurement"
     self.deferred = None

   def __acct(self):
     acct = cloudant.Account(uri=_db_url)
     acct.login(_un, _pw)
     db = acct[_db_name]
     return acct, db

   def __performUploadInThread(self):
     acct, db = self.__acct()
     resp = db.design("nedm_default").post("_update/insert_with_timestamp",params=self.doc_to_post).json()

     if "ok" not in resp:
         return "Measurement settings could not be saved in DB"
     resp["type"] = "DocUpload"
     return resp

   def performUpload(self):
     self.deferred = threads.deferToThread(self.__performUploadInThread)
     return self.deferred

   def shouldUploadFile(self):
     return "filename" in self.doc_to_post and self.deferred is not None


   def __performUploadFileInThread(self, resp):
     if "ok" not in resp:
         return "Document not saved!"
     acct, db = self.__acct()
     fn = self.doc_to_post["filename"]

     po = ProcessObject(acct=acct)

     class CallBack:
         def __init__(self):
             self.bar = None
         def __call__(self, size_rd, total):
             if self.bar is None:
                 self.bar = ProgressBar(expected_size=total, filled_char='=')
             self.bar.show(size_rd)

     print("Sending file: {}".format(fn))
     resp = po.upload_file(fn, resp['id'], db=_db_name, callback=CallBack())
     print("response: {}".format(resp))

     if "ok" in resp:
         resp["url"] = "/_attachments/{db}/{id}/{fn}".format(db=_db_name,fn=fn,**resp)
         resp["file_name"] = fn
         resp["type"] = "FileUpload"
         os.remove(fn)
     return resp

   def uploadFile(self):
     if not self.shouldUploadFile():
       return "File will not be saved"
     self.deferred.addCallback(lambda x: threads.deferToThread(self.__performUploadFileInThread, x))
     return self.deferred

class ReadoutObj(object):
    def __init__(self, ip_addr):
        self.ip_addr = ip_addr
        dev = pyacq.Device(str(ip_addr))
        # Tell device to transmit verification data in the stream
        # Available sites in the device
        model = dev.SendCommand("get.site 1 MODEL").split(" ")[0]
        self.available_modules = dict([(i+1, dev.NumChannels(i)) for i in range(dev.NumSites())])
        self.readout_size = dev.ReadoutSize()
        dev.SendCommand("set.site 0 spad 1,2,0")
        self.min_frequency = 5000
        if model == "ACQ425ELF":
            self._validateData = self._validateData425
            self.minClkDiv = 50
            self.maxClkDiv = 50
            self.clk_divider = 1
            self.bit_right_shift = 0
            self.max_buffer = 2*1024*1024
            self.gain_settings = { 0 : "x1", 1 : "x2", 2 : "x4", 3 : "x8" }
        elif model == "ACQ437ELF":
            self._validateData = self._validateData435
            self.minClkDiv = 4
            if int(dev.SendCommand("get.site 1 hi_res_mode")) == 0:
              self.clk_divider = 256
            else:
              self.clk_divider = 512
            self.bit_right_shift = 8
            self.max_buffer = 1*1024*1024
            self.gain_settings = { 0 : "x1", 1 : "x2", 2 : "x5", 3 : "x10" }
        else:
            raise ReadoutException("Unknown MODEL {}".format(model))
        # total number of channels available
        self.min_buffer = 1*1024*1024/self.readout_size
        self.dev = dev
        self.useExternalClock()

        self.alock = threading.Lock()
        self.cond = threading.Condition(self.alock)
        self.obj_buffer = None
        self.open_file = None
        self.isRunning = False
        self.should_save = False
        self.upload_class = None
        self._cl = []

    def _add_to_list(self, al):
        self.cond.acquire()
        self.obj_buffer = numpy.copy(al)
        self.cond.release()

    def _pop_from_list(self):
        anobj = None
        self.cond.acquire()
        anobj = self.obj_buffer
        self.obj_buffer = None
        self.cond.release()

        if anobj is not None and self.bit_right_shift != 0:
            anobj = numpy.right_shift(anobj, self.bit_right_shift)
        return anobj

    def _ensureNotRunning(self):
        if self.isRunning:
            raise ReadoutException("Cannot call function while readout running")

    def useExternalClock(self, freq_in_hz=None):
        if freq_in_hz is None:
            self.ext_frequency = 0
            self.performCmd(cmd = [
                "set.site 0 fpmux=xclk",
                "set.site 1 clk=0,0,0",
            ])
        else:
            self.ext_frequency = freq_in_hz
            self.performCmd(cmd = [
                "set.site 0 fpmux=fpclk",
                "set.site 1 clk=1,0,1",
            ])
        return self.ext_frequency

    def resetReadout(self):
		"""
        Sometimes the card buffer becomes inconsistent and the run needs to
		be restarted.  We have found that, e.g., the following commands work to
        restart everything:

        run0 1
        run0 1,2
        run0 1

        so we run these here to try to "jump start" the card.
		"""

        for i in range(2):
            cmd = "run0 "
            for x in self.available_modules:
                cmd += str(x)
                self.performCmd(cmd)
                time.sleep(0.3)
                cmd += ","

    def rebootCard(self):
        execute_cmd(self.ip_addr, "reboot")
        raise ReleaseDigitizerNow()

    def readCurrentGains(self):
        g = lambda x: dict([(i, int(x[i])) for i in range(len(x))])
        return dict([(m,g(self.dev.SendCommand("get.site {} gains".format(m))))
                       for m in self.available_modules])

    def _ensureRunning(self):
        if not self.isRunning:
            raise ReadoutException("Cannot call function while readout is idle")

    def getChannels(self, **kw):
        try:
            return dict(mods=self.available_modules,
                      divide=self.clk_divider,
             current_clk_div=int(self.dev.SendCommand("get.site 1 clkdiv")),
                readout_size=self.readout_size,
                  max_buffer=self.max_buffer,
                  min_buffer=self.min_buffer,
               gain_settings=self.gain_settings,
               ext_frequency=self.ext_frequency,
               current_gains=self.readCurrentGains(),
                      sysclk=int(self.dev.SendCommand("get.site 1 sysclkhz")))
        except Exception as e:
            # Getting here means we can't continue, reboot
            self.rebootCard()

    def closeFile(self, **kw):
        if self.open_file is not None: self.open_file.close()
        self.open_file = None

    def setClkDiv(self, **kw):
        self._ensureNotRunning()
        clkdiv = int(kw.get("clkdiv", 1000))
        if clkdiv < self.minClkDiv:
            raise ReadoutException("Clkdiv must not be below the min ({})".format(self.minClkDiv))
        self.dev.SendCommand("set.site 1 clkdiv " + str(clkdiv))
        return self.dev.SendCommand("get.site 1 clkdiv")


    def performCmd(self, **kw):
        cmd = kw.get("cmd", [])
        if isinstance(cmd, list):
            return dict([(c, self.dev.SendCommand(str(c))) for c in cmd])
        else:
            return self.dev.SendCommand(cmd)

    def _checkCounter(self, full_pts, total_counter):
        self.last_counter += full_pts
        while self.last_counter > 0xFFFFFFFF:
            self.last_counter -= 0x100000000
        if self.last_counter != (total_counter % 0xFFFFFFFF):
            raise ReadoutException("ReadoutBuffer corrupted: expected({}) seen({})".format(self.last_counter, total_counter))

    def _validateData425(self, v):
        ch = self.total_ch
        full_pts = len(v)/ch
        last_set = v[(full_pts-1)*ch:]
        cw = self.check_word
        total_counter = numpy.fromstring(numpy.array(last_set[cw:cw+2]).tostring(), numpy.uint32)[0]
        self._checkCounter(full_pts, total_counter)

    def _validateData435(self, v):
        ch = self.total_ch
        full_pts = len(v)/ch
        last_set = v[(full_pts-1)*ch:]
        cw = self.check_word
        total_counter = last_set[cw]
        self._checkCounter(full_pts, total_counter)

    def startReadout(self, **kw):
        self._ensureNotRunning()

        ml = kw.get("mod_list", [])
        mods = ','.join(map(str,ml))
        if len(ml) == 0:
            raise ReadoutException("Must select modules to readout")
        self.dev.SendCommand("run0 " + mods)
        self.total_ch =  int(self.dev.SendCommand("NCHAN"))
        self.actual_ch =  sum([self.available_modules[m] for m in ml])
        self.check_word = self.actual_ch

        buffer_size = kw.get("buffer_size", 1*1024*1024)
        pts_per_frame = self.total_ch
        buffer_size += (pts_per_frame - (buffer_size % pts_per_frame))
        pts_per_buffer = buffer_size/pts_per_frame
        self.last_offset = 0
        self.upload_class = None
        self.last_counter = 0
        self._exc = None
        freq = self.ext_frequency
        if freq == 0:
            freq = int(self.dev.SendCommand("get.site 1 sysclkhz"))
        freq /= (int(self.dev.SendCommand("get.site 1 clkdiv"))*float(self.clk_divider))
        if freq < self.min_frequency:
            raise ReadoutException("Frequency ({}) below minimum ({})".format(freq, self.min_frequency))

        if kw.get("should_upload", False):
            dt = str(datetime.datetime.utcnow())
            downsample = kw.get("downsample", 1)
            if downsample < 1:
                raise ReadoutException("downsample must be >= 1")
            buffer_size -= (pts_per_buffer % downsample)*pts_per_frame

            bit_shift = self.bit_right_shift
            byte_depth = self.readout_size
            is_float = False
            if downsample != 1:
                bit_shift = 0
                byte_depth = 8
                is_float = True
            self.ds = downsample


            header = { "channels" : self.total_ch,
                       "log" : kw.get("log", ""),
                       "byte_depth" : byte_depth,
                       "bit_shift" : bit_shift,
                       "is_float" : is_float,
                       "ip" : self.ip_addr,
                       "downsample" : downsample,
                       "date" : dt,
                       "freq_hz" : freq,
                       "measurement_name" : kw.get("measurement_name", "Digitizer " + self.ip_addr),
                       "channel_list" : kw.get("channel_list", []),
                       "current_gains" : self.readCurrentGains(),
                       "gain_conversion" : self.gain_settings
                     }
            self._cl = header["channel_list"]
            for k, v in kw.get("logitems", {}).items():
                header[k] = v
            if kw.get("should_save", False):
                file_name = dt.replace(':', '-') + ".dig"
                if os.path.exists(file_name):
                    raise ReadoutException("'%s' exists, not overwriting" % file_name)
                self.open_file = open(file_name, "wb")
                header["filename"] = file_name
                header_b = bytearray(json.dumps(header))
                self.open_file.write(bytearray(ctypes.c_uint32(len(header_b))) + header_b)
            self.doc_to_save = header
            self.upload_class = UploadClass(self.doc_to_save)
            self.upload_class.performUpload()

        self.dev.BeginReadout(function=self, buffer_size=buffer_size)
        self.isRunning = True

        def waitToFinish(s, d=None):
            if not d:
                d = defer.Deferred()
            if hasattr(s, "dev") and s.dev.IsRunning():
                reactor.callLater(1, waitToFinish, s, d)
            else:
                self.isRunning = False
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
        if self.upload_class and self.upload_class.shouldUploadFile():
            return self.upload_class.uploadFile()

    def readBuffer(self, **kw):
        self._ensureRunning()
        chans = kw.get("channels", [])
        # build load into a stream
        header = [len(chans)]
        header.extend(chans)
        header = numpy.array(header, dtype=numpy.int32)
        header = header.tostring()
        al = self._pop_from_list()
        if al is None and self._exc is not None:
            raise ReadoutException("Readout unexpectedly ended!")
        if al is not None:
            return header + numpy.array([al[ch::self.total_ch] for ch in chans]).tostring()
        return header


    def _writeToFile(self, v, afile, ch_list):
        try:
            ch = self.total_ch
            # if we get stopped, it's possible we don't have all the data
            # make sure we're aligned
            at_end = len(v) % ch
            if at_end != 0:
                # truncating end
                v = v[:-at_end]
            t = None
            if self.ds == 1:
                t = numpy.array([v[c::ch] for c in ch_list])
            else:
                ds_end = len(v) % (self.ds*ch)
                if ds_end != 0:
                    v = v[:-ds_end]
                t = numpy.array([v[c::ch].reshape(-1, self.ds).mean(axis=1) for c in ch_list])
            t.T.tofile(afile)
        except:
            traceback.print_exc()
            raise

    def __call__(self, x):
        try:
           if len(x) == 0: return
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
        del self.dev

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
       except Exception as e:
         retDic["error"]=traceback.format_exc(limit=1)
         print traceback.format_exc()
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
      pr = request.peer
      #if pr.split(':')[1] != "192.168.1.113": raise HttpException("Currently under work")
      self.__class__._connectedClients.add(self)
      self.req = request
      print("Client connecting: {}".format(pr))

   def onOpen(self):
      print("WebSocket connection open.")

   def onClose(self, wasClean, code, reason):
      self.releaseDigitizerControl()
      try:
        self.__class__._connectedClients.remove(self)
      except: pass

   def initializeWebPage(self):
      return dict(urls=available_urls)


if __name__ == '__main__':
   import sys

   log.startLogging(sys.stdout)

   from autobahn.twisted.websocket import WebSocketServerFactory
   factory = WebSocketServerFactory()
   factory.protocol = ShipData

   reactor.listenTCP(port=9000, factory=factory)
   reactor.run()
