import logging
from .digitizer_utils import ReadoutException, EndReadoutNow

class Trigger(object):
    """
    Base class for all triggers
    """
    def call_trigger(self, v, channel_list, total_ch):
        if not hasattr(self, "trigger"):
            return True
        return self.trigger(dict([(c,v[c::total_ch]) for c in channel_list]))

def get_trigger(exec_str=None):
   if not exec_str or exec_str=="":
       return Trigger()
   import imp, uuid
   import sys
   aname = str(uuid.uuid4())
   mod = imp.new_module(aname)
   mod.__dict__["Trigger"] = Trigger
   mod.__dict__["EndReadoutNow"] = EndReadoutNow
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



