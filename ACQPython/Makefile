include ../buildTools/config.mk

SHLIB := ../lib/pyacq.$(SHREXT)

include ../buildTools/BasicMakefile

INCLUDEFLAGS += $(PYTHONINCLUDEFLAGS) -I../
LIBFLAGS += -L../lib -lACQ -lboost_python -lboost_system -lboost_thread $(PYTHONLIBFLAGS) 
