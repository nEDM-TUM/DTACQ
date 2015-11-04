include ../buildTools/config.mk

SHLIB := ../lib/pyacq.$(SHREXT)

include ../buildTools/BasicMakefile

INCLUDEFLAGS += $(PYTHONINCLUDEFLAGS) -I../
LIBFLAGS += -L../lib -lACQ $(BOOST_PYTHON_LIB) $(BOOST_SYSTEM_LIB) $(BOOST_THREAD_LIB) $(PYTHONLIBFLAGS)
