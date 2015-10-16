import logging
from .digitizer_utils import ReadoutException, OpenNewReadoutFile, EndReadoutNow

class Trigger(object):
    """
    Base class for all triggers
    """
    def call_trigger(self, v, channel_list, total_ch):
        if not hasattr(self, "trigger"):
            return True
        return self.trigger(dict([(c,v[c::total_ch]) for c in channel_list]))

    """
    def trigger(self, x):
		This is the function that should be overloaded by the derived class.
        The possible return values are:

          False - write no data
          True  - write all data
		  [None, OpenNewReadoutFile, (1, 8), ...] - a list of commands with the
             following meanings:
             None - write all data
			 OpenNewReadoutFile - a class, will open a new readout file,
               closing the current file
			 (x,y) - tuple, will write the current data (all selected channels)
             from index x to y
        return True
    """

def get_trigger(exec_str=None):
   if not exec_str or exec_str=="":
       return Trigger()
   import imp, uuid
   import sys
   aname = str(uuid.uuid4())
   mod = imp.new_module(aname)
   mod.__dict__["Trigger"] = Trigger
   mod.__dict__["EndReadoutNow"] = EndReadoutNow
   mod.__dict__["OpenNewReadoutFile"] = OpenNewReadoutFile
   exec exec_str in mod.__dict__
   for name, c in mod.__dict__.items():
       try:
           x = issubclass(c, Trigger)
       except:
           continue
       if x and c != Trigger:
           logging.info("Using trigger class: " + name)
           o = c()
           # If trigger was not defined, the following will throw
           o.trigger
           sys.modules[aname] = mod
           return o
   raise ReadoutException("No Trigger class found")



