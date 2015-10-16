from paramiko.client import SSHClient, AutoAddPolicy
from .settings import dtacq_un, dtacq_pw

class OpenNewReadoutFile(object):
    pass

class ReadoutException(Exception):
    pass

class ReleaseDigitizerNow(Exception):
    pass

class EndReadoutNow(Exception):
    pass


def execute_cmd(ip_addr, cmd):
    client = SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(AutoAddPolicy())
    client.connect(ip_addr,
      username=dtacq_un,
      password=dtacq_pw)
    _, aout, aerr = client.exec_command(cmd)
    return aout.read(), aerr.read()

