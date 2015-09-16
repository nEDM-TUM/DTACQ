from .decorators import (notRunning, isRunning)
from .digitizer_utils import ReadoutException
import numpy

class ACQCard(object):
    min_frequency = 5000

    def __init__(self, dev):
        # Set up the counter for all cards
        dev.SendCommand("set.site 0 spad 1,2,0")
        self.isRunning = False
        self.readout_size = dev.ReadoutSize()
        self.min_buffer = 1*1024*1024/self.readout_size
        self.available_modules = dict([(i+1, dev.NumChannels(i)) for i in range(dev.NumSites())])
        self.dev = dev
        self.reset()

    def _checkCounter(self, full_pts, total_counter):
        self.last_counter += full_pts
        while self.last_counter > 0xFFFFFFFF:
            self.last_counter -= 0x100000000
        if self.last_counter != (total_counter % 0xFFFFFFFF):
            raise ReadoutException("ReadoutBuffer corrupted: expected({}) seen({})".format(self.last_counter, total_counter))

    @notRunning
    def reset(self, check_word=0, total_channels=0):
        self.last_counter = 0
        self.total_ch = total_channels
        self.check_word = check_word

    def performCmd(self, **kw):
        cmd = kw.get("cmd", [])
        if isinstance(cmd, list):
            return dict([(c, self.dev.SendCommand(str(c))) for c in cmd])
        else:
            return self.dev.SendCommand(cmd)

    @notRunning
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

    @notRunning
    def readCurrentGains(self):
        g = lambda x: dict([(i, int(x[i])) for i in range(len(x))])
        return dict([(m,g(self.dev.SendCommand("get.site {} gains".format(m))))
                       for m in self.available_modules])

    @notRunning
    def setClkDiv(self, **kw):
        clkdiv = int(kw.get("clkdiv", 1000))
        if clkdiv < self.minClkDiv:
            raise ReadoutException("Clkdiv must not be below the min ({})".format(self.minClkDiv))
        self.dev.SendCommand("set.site 1 clkdiv " + str(clkdiv))
        return self.dev.SendCommand("get.site 1 clkdiv")


class ACQ425ELF(ACQCard):
    minClkDiv = 50
    maxClkDiv = 50
    clk_divider = 1
    bit_right_shift = 0
    max_buffer = 2*1024*1024
    gain_settings = { 0 : "x1", 1 : "x2", 2 : "x4", 3 : "x8" }

    def validateData(self, v):
        ch = self.total_ch
        full_pts = len(v)/ch
        last_set = v[(full_pts-1)*ch:]
        cw = self.check_word
        total_counter = numpy.fromstring(numpy.array(last_set[cw:cw+2]).tostring(), numpy.uint32)[0]
        self._checkCounter(full_pts, total_counter)

class ACQ425ELFLIA(ACQ425ELF):
    gain_settings = { 0 : "x1" }
    def __init__(self, dev):
        super(ACQ425ELFLIA, self).__init__(dev)
        # Reset the counter, doesn't work for this card ! (yet)
        dev.SendCommand("set.site 0 spad 0,0,0")
        self.available_modules = dict([(i+1, dev.NumChannels(i)) for i in range(dev.NumSites())])
        self.setClkDiv()

    @notRunning
    def setClkDiv(self, **kw):
        return super(ACQ425ELFLIA, self).setClkDiv(clkdiv=100)

    @notRunning
    def reset(self, check_word=0, total_channels=0):
        self.last_counter = 0
        self.total_ch = 80
        self.check_word = check_word

    def validateData(self, v):
        pass



class ACQ437ELF(ACQCard):
    minClkDiv = 4
    bit_right_shift = 8
    max_buffer = 1*1024*1024
    gain_settings = { 0 : "x1", 1 : "x2", 2 : "x5", 3 : "x10" }

    def __init__(self, dev):
        super(ACQ437ELF, self).__init__(dev)
        if int(dev.SendCommand("get.site 1 hi_res_mode")) == 0:
          self.clk_divider = 256
        else:
          self.clk_divider = 512

    def validateData(self, v):
        ch = self.total_ch
        full_pts = len(v)/ch
        last_set = v[(full_pts-1)*ch:]
        cw = self.check_word
        total_counter = last_set[cw]
        self._checkCounter(full_pts, total_counter)


