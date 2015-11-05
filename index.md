---
title: DTACQ
layout: basic
is_index: true
---

Provides readout functionality for[ D-tAcq](http://www.d-tacq.com/) ethernet
digitizer cards.  The software is written in C++ (for speed) and python (for
easy integration with other systems).

## Requirements

1. [Boost](http://www.boost.org/) >= 1.59
2. Python development packages

## Building

As simple as:
{% highlight bash %}
./configure
make
{% endhighlight %}

To build tests, one can do:

{% highlight bash %}
make test
{% endhighlight %}

This will build tests in the `ACQtests` directory.  The executables in that
directory provide some example code.

