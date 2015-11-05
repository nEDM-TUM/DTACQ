SRCDIRS =  ACQ ACQPython 

.PHONY: all clean 

all: shared 

shared: 
	@for i in $(SRCDIRS); do (echo Entering directory $$i; $(MAKE) -C $$i shared) || exit $$?; done

clean:
	@for i in $(SRCDIRS) ACQtest; do $(MAKE) -C $$i clean || exit $$?; done
	@rm -rf lib

test:
	@for i in ACQtest; do (echo Entering directory $$i; $(MAKE) -C $$i) || exit $$?; done


