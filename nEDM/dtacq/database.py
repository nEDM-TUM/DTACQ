import cloudant
from pynedm import ProcessObject
from twisted.internet import threads, defer
from clint.textui.progress import Bar as ProgressBar
import logging
from .settings import db_url, db_name, db_un, db_pw
import os
import json
import ctypes

class UploadClass(object):
   def __init__(self, doc_to_save):
     self.doc_to_post = doc_to_save
     self.doc_to_post["type"] = "measurement"
     self._fn = self.doc_to_post.get("filename", None)
     self._openfile = None
     self._filenumber = 0
     self.deferred = None
     self._first = True

     self.__performUpload()
     self.writeNewFile()

   def __acct(self):
     acct = cloudant.Account(uri=db_url)
     acct.login(db_un, db_pw)
     db = acct[db_name]
     return acct, db

   def isWriting(self):
     return self._openfile is not None

   def closeAndUploadFile(self):
     if not self.shouldUploadFile():
       d = defer.Deferred()
       d.callback("Not uploading file")
       return d

     self._openfile["file"].close()
     if "written" in self._openfile:
         self.deferred.addCallback(lambda x:
           threads.deferToThread(self.__performUploadFileInThread, x, self._openfile["name"]))
     else:
         # Means we never wrote, just delete
         os.remove(self._openfile["name"])
     self._openfile = None
     return self.deferred

   def writeNewFile(self):
     if not self._fn:
         return

     self.closeAndUploadFile()

     new_file_name = "{0}-{fn}{1}".format(*os.path.splitext(self._fn), fn=self._filenumber)
     self._filenumber += 1

     self._openfile = {
       "name" : new_file_name,
       "file" : open(new_file_name, "wb")
     }
     header = self.doc_to_post
     header["filename"] = new_file_name

     header_b = bytearray(json.dumps(header))
     while len(header_b) % 4 != 0:
         header_b += " "
     self._openfile["file"].write(bytearray(ctypes.c_uint32(len(header_b))) + header_b)

   def writeToFile(self, dat):
     """
     dat should be a function type taking a file object as argument
     """
     if not self._openfile: return
     self._openfile["written"] = True
     dat(self._openfile["file"])

   def __performUploadInThread(self):
     acct, db = self.__acct()
     resp = db.design("nedm_default").post("_update/insert_with_timestamp",params=self.doc_to_post).json()

     if "ok" not in resp:
         return "Measurement settings could not be saved in DB"
     resp["type"] = "DocUpload"
     return resp

   def __performUpload(self):
     self.deferred = threads.deferToThread(self.__performUploadInThread)
     return self.deferred

   def shouldUploadFile(self):
     return "filename" in self.doc_to_post and\
            self.deferred is not None and\
            self._openfile is not None

   def __performUploadFileInThread(self, resp, fn):
     if self._first and "ok" not in resp:
         return "Document not saved!"
     self._first = False
     acct, db = self.__acct()
     po = ProcessObject(acct=acct)

     class CallBack:
         def __init__(self):
             self.bar = None
         def __call__(self, size_rd, total):
             if self.bar is None:
                 self.bar = ProgressBar(expected_size=total, filled_char='=')
             self.bar.show(size_rd)

     logging.info("Sending file: {}".format(fn))
     resp = po.upload_file(fn, resp['id'], db=db_name, callback=CallBack())
     logging.info("response: {}".format(resp))

     if "ok" in resp:
         resp["url"] = "/_attachments/{db}/{id}/{fn}".format(db=db_name,fn=fn,**resp)
         resp["file_name"] = fn
         resp["type"] = "FileUpload"
         os.remove(fn)
     return resp


