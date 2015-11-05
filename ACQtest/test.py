import pyacq
import time
import sys
import traceback

"""
We can define either a class or a function to pass to BeginReadout
"""
class anObj(object):
    def __call__(self, x):
        try:
           v = x.vec()
           print v, x
        except:
           traceback.print_exc()
           raise 
        

if len(sys.argv) != 2:
    print "Usage: prog url_of_digitizer"
    sys.exit(1)

dev= pyacq.Device(sys.argv[1])
print dev.ReadoutSize()
print dev.SendCommand("fpga_version")
ch = int(dev.SendCommand("NCHAN"))

# get_total_channels
total_chan = sum([dev.NumChannels(int(i)-1) for i in dev.SendCommand("sites").split(',')]) 
print total_chan, ch

print "Begin"
o = anObj(total_chan)
dev.BeginReadout(function=o, buffer_size=1*1024*1024)
print dev.IsRunning()
time.sleep(2)
print "Stop"
dev.StopReadout()
print dev.IsRunning()

