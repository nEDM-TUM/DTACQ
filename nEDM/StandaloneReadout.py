"""
  Provides a WAMP server for D-TACQ digitizers.  Also allows saving data in DB
"""

import pyacq
import time
import numpy
import sys
import traceback


class ReadoutException(Exception):
    pass

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

        self.isRunning = False
        self.should_save = False
        self._cl = []

    def _ensureNotRunning(self):
        if self.isRunning:
            raise ReadoutException("Cannot call function while readout running")

    def readCurrentGains(self):
        g = lambda x: dict([(i, int(x[i])) for i in range(len(x))])
        return dict([(m,g(self.dev.SendCommand("get.site {} gains".format(m))))
                       for m in self.available_modules])

    def _ensureRunning(self):
        if not self.isRunning:
            raise ReadoutException("Cannot call function while readout is idle")

    def setClkDiv(self, **kw):
        self._ensureNotRunning()
        clkdiv = int(kw.get("clkdiv", 1000))
        if clkdiv < self.minClkDiv:
            raise ReadoutException("Clkdiv must not be below the min ({})".format(self.minClkDiv))
        self.dev.SendCommand("set.site 1 clkdiv " + str(clkdiv))
        return self.dev.SendCommand("get.site 1 clkdiv")


    def _validateData425(self, v):
        ch = self.total_ch
        full_pts = len(v)/ch
        last_set = v[(full_pts-1)*ch:]
        cw = self.check_word
        total_counter = numpy.fromstring(numpy.array(last_set[cw:cw+2]).tostring(), numpy.uint32)[0]
        self.last_counter += full_pts
        self.last_counter %= 0xFFFFFFFF
        if self.last_counter != (total_counter % 0xFFFFFFFF):
            raise ReadoutException("ReadoutBuffer corrupted: expected({}) seen({})".format(self.last_counter, total_counter))

    def _validateData435(self, v):
        ch = self.total_ch
        full_pts = len(v)/ch
        last_set = v[(full_pts-1)*ch:]
        cw = self.check_word
        total_counter = last_set[cw]
        self.last_counter += full_pts
        self.last_counter %= 0xFFFFFFFF
        if self.last_counter != (total_counter % 0xFFFFFFFF):
            raise ReadoutException("ReadoutBuffer corrupted: expected({}) seen({})".format(self.last_counter, total_counter))


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
        bytes_per_frame = self.total_ch*2
        buffer_size += (bytes_per_frame - (buffer_size % bytes_per_frame))
        self.last_offset = 0
        self.last_counter = 0
        self._exc = None

        self.dev.BeginReadout(function=self, buffer_size=buffer_size)
        self.isRunning = True

    def stopReadout(self, **kw):
        self._ensureRunning()
        self.dev.StopReadout()

    def _writeToFile(self, v, afile, ch_list):
        try:
            ch = self.total_ch
            # if we get stopped, it's possible we don't have all the data
            # make sure we're aligned
            at_end = len(v) % ch
            if at_end != 0:
                # truncating end
                v = v[:-at_end]
            t = numpy.array([v[c::ch] for c in ch_list])
            t.T.tofile(afile)
        except Exception as e:
            print e, len(t), t.T, afile, ch, len(v), v, ch_list
            raise

    def __call__(self, x):
        # Called during run
        try:
           if len(x) == 0: return
           v = x.vec()
           print("Read in ({})".format(v))
           if self.last_offset != 0:
               raise ReadoutException("Buffer not aligned")
           self._validateData(v)
           #self._writeToFile(v, self.open_file, self.doc_to_save["channel_list"])
           ch = self.total_ch
           start_pt = (ch - self.last_offset) % ch
           end_pt = (len(v)-start_pt) % ch
           t = v[start_pt:]
           self.last_offset += end_pt
        except Exception as e:
           self._exc = traceback.format_exc()
           print self._exc
           raise

if __name__ == '__main__':

    new_obj = ReadoutObj("digitizer.1.nedm1")
    new_obj.startReadout(mod_list=[1])
    time.sleep(10) # Read for 10 secs
    new_obj.stopReadout()

