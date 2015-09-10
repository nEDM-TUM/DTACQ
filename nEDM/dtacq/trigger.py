import logging
from .digitizer_utils import ReadoutException

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
   mod = imp.new_module(str(uuid.uuid4()))
   mod.__dict__["Trigger"] = Trigger
   exec exec_str in mod.__dict__
   for name, c in mod.__dict__.items():
       try:
           if issubclass(c, Trigger) and c != Trigger:
               logging.info("Using trigger class: " + name)
               return c()
       except: pass
   raise ReadoutException("No Trigger class found")



