#                               -*- Autoconf -*-
# DTACQ configure.ac
#
# Initial version written by M. Marino Aug 2011.
# Generates the configure script in use during the configuration phase of the
# build for DTACQ.  Should be built with autoconf 2.69

#########################################################################
# Init stage
#########################################################################
AC_PREREQ(2.69)
AC_INIT([ACQ], [1.0])
AC_CONFIG_SRCDIR([ACQ/CircularBuffer.hh])

AC_CONFIG_MACRO_DIR([m4])

# works for me, even in screen on Darwin
AS_IF([test x"$PS1" != x],[BOLD=`tput smso`;OFFBOLD=`tput rmso`;])dnl make life brighter

#########################################################################
# Check base system
#########################################################################
AC_CANONICAL_HOST
AC_PROG_SED
AC_PROG_LN_S
AC_PROG_MKDIR_P

#########################################################################
# Check the compiler
#########################################################################
AC_LANG([C++])
m4_include(ax_cxx_compile_stdcxx_11.m4)
AX_CXX_COMPILE_STDCXX_11(noext)
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
# BOOST
#########################################################################
m4_include(ax_boost_base.m4)
m4_include(ax_boost_system.m4)
m4_include(ax_boost_thread.m4)
m4_include(ax_boost_chrono.m4)
m4_include(ax_boost_timer.m4)
AX_BOOST_BASE([1.59],,[AC_MSG_ERROR([DTACQ needs Boost, but it was not found in your system])])

AX_BOOST_SYSTEM
AX_BOOST_THREAD
AX_BOOST_CHRONO
AX_BOOST_TIMER

LDFLAGS="$LDFLAGS $BOOST_LDFLAGS"
CXXFLAGS="$CXXFLAGS $BOOST_CPPFLAGS"
#AC_CHECK_LIB([boost_timer],, AC


#########################################################################
#Find python, this is necessary for some of the build
#########################################################################
m4_include(ax_python_devel.m4)
m4_include(ax_boost_python.m4)
AX_PYTHON_DEVEL
PYTHONLIBFLAGS="$PYTHON_EXTRA_LDFLAGS $PYTHON_LIBS"
PYTHONINCLUDEFLAGS="$PYTHON_CPPFLAGS"
NUMPYINCLUDEFLAGS=`$PYTHON -c 'import numpy; import sys; sys.stdout.write("-I" + numpy.get_include())'`

PYTHON_EXTRA_LIBS=" "
AX_BOOST_PYTHON
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

#########################################################################
# Make output
#########################################################################

# deliver all DEFINES via command line as well
AC_OUTPUT_MAKE_DEFS
AX_DEFS=$DEFS
AC_SUBST(AX_DEFS)
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


