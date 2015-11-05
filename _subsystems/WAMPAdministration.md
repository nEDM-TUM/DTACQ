---
title: WAMP Server administration
description: How to administer a WAMP server for the nEDM experiment
layout: basic
---

## Administration

This describes running the WAMP server on a Mac OS X system.  At the time of
writing, it was running on the mini.nedm1 Mac mini.  The daemon runs using the
launchd system on Mac OS X.  For an example of a `plist` file used to define
this daemon see [here]({{ site.github.repository_url }}/blob/master/nEDM/nedm1.digitizer.plist).

To use this file, first edit the paths in the file to correspond to the paths on your system.

Then assign the following environment variables correctly:

* `DB_USER_NAME` - user name with write access to the database
* `DB_PASSWORD`  - password of account
* `DB_NAME` - name of database to store the files
* `DB_URL` - URL of database server
* `DTACQ_USER_NAME` - username for logging on to DTACQ cards (typically `root`)
* `DTACQ_PASSWORD` - password for login on DTACQ cards (for SSH access)

Note the values of these variables:

* `WorkingDirectory` - path where temporary files will be stored before upload to the DB
* `StandardOut(Error)Path` - path to log file
* `RunAtLoad` - start daemon on boot
* `KeepAlive` - keep daemon running if it dies (or is killed)

### Starting

After the `nedm1.digitizer.plist` is correctly modified, move it to a standard place, e.g.:

{% highlight bash %}
mv nedm1.digitizer.plist ~/Library/LaunchAgents
{% endhighlight %}

Then start the daemon by loading it:
{% highlight bash %}
launchctl load ~/Library/LaunchAgents/nedm1.digitizer.plist
{% endhighlight %}

Stopping (permanently) can be done by:
{% highlight bash %}
launchctl unload ~/Library/LaunchAgents/nedm1.digitizer.plist
{% endhighlight %}

### Restarting or upgrading

Restarting the server can be done by sending it a signal (either `INT` or
`KILL` depending upon whether or not it's still responsive).  The launchd
daemon will automatically restart it.  Use `ps -ef | grep python` to determine
the process ID and then call `kill -INT [the_pid]` (or `kill -KILL [the_pid]`),
where `[the_pid]` is the appropriate process id.


