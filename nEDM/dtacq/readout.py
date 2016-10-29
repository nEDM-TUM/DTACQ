import pyacq
import numpy
import threading
import datetime
import traceback
from twisted.internet import defer, reactor
from .digitizer_utils import (execute_cmd,
                              ReadoutException,
                              ReleaseDigitizerNow,
                              OpenNewReadoutFile,
                              EndReadoutNow)
import logging
from .database import UploadClass
from .decorators import (notRunning, isRunning)
from .trigger import get_trigger
from . import cards
import os


class ReadoutObj(object):
    def __init__(self, ip_addr):
        self.ip_addr = ip_addr
        dev = pyacq.Device(str(ip_addr))
        # Available sites in the device
        model = dev.SendCommand("get.site 1 MODEL").split(" ")[0]
        # Tell device to transmit verification data in the stream

        try:
          # Check for LIA version of firmware
          if dev.SendCommand("fpga_version").split(" ")[0].split("_")[-1] == "LIA":
              model += "LIA"
        except: pass

        if hasattr(cards, model):
            self.card = getattr(cards, model)(dev)
        else:
            raise ReadoutException("Unknown MODEL {}".format(model))
        # total number of channels available
        self.useExternalClock()

        self.alock = threading.Lock()
        self.cond = threading.Condition(self.alock)
        self.obj_buffer = None
        self.upload_class = None
        self.counter = -1

    def __getattr__(self, name):
        """
        Forward attribute access to card
        """
        try:
            return getattr(self.card, name)
        except:
            raise AttributeError

    def _add_to_list(self, al):
        self.cond.acquire()
        self.counter += 1
        if self.counter >= 0xffffffff:
            self.counter = 0
        self.obj_buffer = numpy.copy(al)
        self.cond.release()

    def _pop_from_list(self):
        anobj = None
        self.cond.acquire()
        anobj = self.obj_buffer
        self.obj_buffer = None
        ctr = self.counter
        self.cond.release()

        if anobj is not None and self.bit_right_shift != 0:
            anobj = numpy.right_shift(anobj, self.bit_right_shift)
        return anobj, ctr

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

    def checkTrigger(self, **kw):
        get_trigger(kw.get("trigger", ""))
        return True

    def rebootCard(self):
        execute_cmd(self.ip_addr, "reboot")
        raise ReleaseDigitizerNow()

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
        except:
            # Getting here means we can't continue, reboot
            self.rebootCard()

    @notRunning
    def startReadout(self, **kw):

        self.counter = -1
        ml = kw.get("mod_list", [])
        mods = ','.join(map(str,ml))
        if len(ml) == 0:
            raise ReadoutException("Must select modules to readout")
        self.dev.SendCommand("run0 " + mods)

        self.card.reset(sum([self.available_modules[m] for m in ml]),
                        int(self.dev.SendCommand("NCHAN")))

        buffer_size = kw.get("buffer_size", 1*1024*1024)
        pts_per_frame = self.total_ch
        buffer_size += (pts_per_frame - (buffer_size % pts_per_frame))
        pts_per_buffer = buffer_size/pts_per_frame

        self.trigger = get_trigger(kw.get("trigger", ""))

        self.last_offset = 0
        self.upload_class = None
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
            for k, v in kw.get("logitems", {}).items():
                header[k] = v
            if kw.get("should_save", False):
                file_name = dt.replace(':', '-') + ".dig"
                if os.path.exists(file_name):
                    raise ReadoutException("'%s' exists, not overwriting" % file_name)
                header["filename"] = file_name
            self.doc_to_save = header
            self.upload_class = UploadClass(self.doc_to_save)

        self.dev.BeginReadout(function=self, buffer_size=buffer_size)
        self.isRunning = True

        def waitToFinish(s, d=None, uc=None):
            if not d:
                d = defer.Deferred()
            if not uc:
                uc = s.upload_class
            if hasattr(s, "dev") and s.dev.IsRunning():
                reactor.callLater(1, waitToFinish, s, d, uc)
            else:
                s.isRunning = False
                def send_result(res):
                    res = [ res ]
                    if not s._exc:
                        res.append(dict(type="JobFinished", msg="Readout job completed"))
                    else:
                        res.append(dict(type="JobFinished", error=s._exc))
                    d.callback(res)
                if uc:
                    uc.closeAndUploadFile().addCallback( send_result )
                else:
                    send_result("")
            return d
        return waitToFinish(self)

    @isRunning
    def stopReadout(self, **kw):
        self.dev.StopReadout()

    def readBuffer(self, **kw):
        chans = kw.get("channels", [])
        include_counter = kw.get("include_counter", False)

        # build load into a stream
        header = [len(chans)]
        header.extend(chans)
        al, ctr = self._pop_from_list()

        # If we include the counter, then we set a bit flag in the header and
        # append one value to the length
        if include_counter:
            header.append(ctr)
            header[0] += 0xff00

        header = numpy.array(header, dtype=numpy.uint32)
        header = header.tostring()
        if al is None:
            if not self.isRunning:
                if self._exc is not None:
                    raise ReadoutException("Readout unexpectedly ended!")
                return numpy.array([0xdeadbeef], dtype=numpy.int32).tostring()
        if al is not None:
            return header + numpy.array([al[ch::self.total_ch] for ch in chans]).tostring()
        return header


    def _writeToFile(self, v, afile, ch_list, data_range=None):
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
            towrite = t.T
            if data_range is not None:
                towrite = towrite[data_range[0]:data_range[1]]
            towrite.tofile(afile)
        except:
            traceback.print_exc()
            raise

    def __call__(self, x):
        try:
           if len(x) == 0: return
           v = x.vec()
           if self.last_offset != 0:
               # This should generally not happen, but we check anyways
               raise ReadoutException("Buffer not aligned")
           self.validateData(v)
           # This should generally be 0, though it's possible that the *last*
           # buffer is not aligned.
           self.last_offset += len(v) % self.total_ch

           if self.upload_class:
               if self.upload_class.isWriting():
                   retVal = self.trigger.call_trigger(v, range(self.total_ch), self.total_ch)
                   if retVal == False:
                       return
                   if retVal == True:
                       retVal = [None]
                   # We were given a set of commands to write the file, loop through them
                   for y in retVal:
                       if y == OpenNewReadoutFile:
                           self.upload_class.writeNewFile()
                       else:
                           self.upload_class.writeToFile(lambda x: self._writeToFile(v, x, self.doc_to_save["channel_list"], data_range=y))
           self._add_to_list(v)
        except EndReadoutNow:
           logging.info("Readout end requested")
           raise
        except:
           self._exc = traceback.format_exc()
           logging.exception("Exception during readout")
           raise

    def safeShutdown(self):
        if self.isRunning: self.stopReadout()
        del self.card.dev

