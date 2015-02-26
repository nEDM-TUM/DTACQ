#                               -*- Autoconf -*-
# TWaveform configure.ac
#
# Initial version written by M. Marino Aug 2011.
# Rewritten by V. Belov Sep 2011.
# Generates the configure script in use during the configuration phase of the
# build for TWaveform.  Should be built with autoconf 2.63 

#########################################################################
# Init stage
#########################################################################
AC_PREREQ(2.63)
AC_INIT([ACQ], [1.0])
AC_CONFIG_SRCDIR([ACQ/CircularBuffer.hh])

# works for me, even in screen on Darwin
AS_IF([test x"$PS1" != x],[BOLD=`tput smso`;OFFBOLD=`tput rmso`;])dnl make life brighter

#########################################################################
# Check base system
#########################################################################
AC_CANONICAL_HOST
AC_PROG_AWK
AC_PROG_SED
AC_PROG_LN_S
AC_PROG_MKDIR_P

#########################################################################
# Check the compiler
#########################################################################
AC_PROG_CC
AC_PROG_CXX
AC_PROG_CXXCPP
#AC_PROG_LIBTOOL
AC_SUBST(LD)
AS_IF([test x"${build_cpu}" = "xx86_64"],[
  case "${host_cpu}" in
    i?86)
      CFLAGS="$CFLAGS -m32"
      CXXFLAGS="$CXXFLAGS -m32"
      LDFLAGS="$LDFLAGS -m32"
      AC_MSG_NOTICE([Cross compiling on an x86_64 for i386... using -m32 flag])
      # Strictly speaking one needs to check that compiler used is not a 
      #   cross-compiler, but it's so rare in _this_ case
  esac])

#########################################################################
#Find python, this is necessary for some of the build 
#########################################################################
m4_include(python.m4)
AM_PATH_PYTHON([2.5],
               [HAVE_PYTHON=yes
                PYTHONLIBDIR=`$PYTHON -c 'from distutils.sysconfig import get_python_lib; print "%s/config" % get_python_lib(0,1)'`
                PYTHONLIBFLAGS=`python-config --ldflags`
                PYTHONINCLUDEFLAGS=`python-config --include`
                NUMPYINCLUDEFLAGS=`python -c 'import numpy; import sys; sys.stdout.write("-I" + numpy.get_include())'`
               ],
               [HAVE_PYTHON=no
                AC_MSG_ERROR([python not found, required for build])])
AC_SUBST(HAVE_PYTHON)
AC_SUBST(PYTHONLIBDIR)
AC_SUBST(PYTHONLIBFLAGS)
AC_SUBST(PYTHONINCLUDEFLAGS)
AC_SUBST(NUMPYINCLUDEFLAGS)


#########################################################################
# Check extra dependencies
#########################################################################
#########################################################################
# Make build flags
#########################################################################
# handle dynamic libraries
case "$host_os" in
  darwin*)
#    EXTRALIBFLAGS="-bind_at_load" 
#    SOFLAGS="-dynamiclib"
    SHREXT=dylib
    SOFLAGS="-dynamiclib -install_name @rpath/"
    ORIGINFLAGS="@loader_path/../lib"
    LIBRARY_SEARCH_PATH=DYLD_LIBRARY_PATH
  ;;
  linux*)
    SOFLAGS="-shared -Wl,-soname,"
    SHREXT=so
    LDFLAGS="$LDFLAGS -Wl,-rpath-link,\$(prefix)/lib -Wl,-z,defs" 
    ORIGINFLAGS=\'\$\$ORIGIN/../lib\',--enable-new-dtags
    LIBRARY_SEARCH_PATH=LD_LIBRARY_PATH
  ;;
  *)
  AC_MSG_ERROR([Don't know how to build dynamic libraries on your system])
  ;;
esac
AC_SUBST(SOFLAGS)
AC_SUBST(SHREXT)
AC_SUBST(ORIGINFLAGS)
AC_SUBST(LIBRARY_SEARCH_PATH)

# check x86_64
case "${host_cpu}" in
    x86_64*)
        CXXFLAGS="${CXXFLAGS} -fPIC"
        AC_MSG_NOTICE([Compiling on an x86_64 chipset... setting -fPIC flag.])
  # only on amd64 should one compile static libs with this flag
  # Other tested architectures currently compile PIC libraries
  # and so it is no problem to link a dynamic library using the PIC
  # libs
esac

# Setting default warning flags.
WARNINGFLAGS="-W -Wall -Wextra"
case "${CXX}" in
  icc*)
  # If using icc, remove warning flags.
  # icc output is otherwise too verbose.
  WARNINGFLAGS=""
esac

AC_SUBST(WARNINGFLAGS)

AS_IF([test x"$as_echo" = x],
 [AC_SUBST(AX_ECHO,[echo])
  AC_SUBST(AX_ECHO_N,[echo $ECHO_N " $ECHO_C"])],
 [AC_SUBST(AX_ECHO,$as_echo)
  AC_SUBST(AX_ECHO_N,$as_echo_n)])
#---------------------------------------
# Get directories to compile
#_AS_ECHO_N([looking for all compilable directories... ])
#DIRECTORIES=`find $EXOANALYSISROOT -type d -exec sh -c 'if test -d {}/src; then printf "{} "; fi' \;`
#DIRECTORIES=`echo $DIRECTORIES | $SED "s|$EXOANALYSISROOT/||g"`
#AC_MSG_RESULT(done)
#AC_SUBST(DIRECTORIES)

#EXTRACXXFLAGS="${EXTRACXXFLAGS} -O2 -ggdb"
#AC_SUBST(EXTRACXXFLAGS)

dnl AC_SUBST(CPPFLAGS)
dnl LDFLAGS=`$ROOTCONF --ldflags --glibs` 
dnl AC_SUBST(LDFLAGS)

#########################################################################
# Make output
#########################################################################

# deliver all DEFINES via command line as well
AC_OUTPUT_MAKE_DEFS
AX_DEFS=$DEFS
AC_SUBST(AX_DEFS)
# rootcint has issues with some of the defines, in particular those that define
# the arguments of the select function.  Therefore, we remove those defines and
# add the rest to ROOTCINTDEFS
ROOTCINTDEFS=`echo $AX_DEFS | $SED "s/-DSELECT_TYPE_ARG[[1-5]]*=[[^-D]]*//g"`
AC_SUBST(ROOTCINTDEFS)
#
AC_CONFIG_FILES([
                 buildTools/config.mk
                ])
AC_OUTPUT

AC_MSG_NOTICE
AC_MSG_NOTICE([**********************************************************************************])
AC_MSG_NOTICE([Run])
AC_MSG_NOTICE
AC_MSG_NOTICE([  ./configure --help])
AC_MSG_NOTICE
AC_MSG_NOTICE([for a list of options and configuration flags to adjust the configuration.])
AC_MSG_NOTICE([**********************************************************************************])

AC_MSG_NOTICE([You have successfully configured ACQ.])
AC_MSG_NOTICE([Please now compile by issuing the command (where the @%:@ in -j@%:@ refers to the CPUs ]) 
AC_MSG_NOTICE([across which you'd like to split the build process @<:@optional@:>@):])
AC_MSG_NOTICE
AC_MSG_NOTICE([  make clean ])
AC_MSG_NOTICE([  make @<:@-j@%:@@:>@ ])
AC_MSG_NOTICE


