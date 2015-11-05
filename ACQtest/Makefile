include ../buildTools/config.mk


APPS := testDigitizer testReadout
test: $(APPS) 

include ../buildTools/BasicMakefile

INCLUDEFLAGS += -I../
LIBFLAGS += -L../lib -lACQ $(BOOST_SYSTEM_LIB)
