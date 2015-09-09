import cloudant
from pynedm import ProcessObject
from twisted.internet import threads
from clint.textui.progress import Bar as ProgressBar
import logging
from .settings import db_url, db_name, db_un, db_pw 

class UploadClass(object):
   def __init__(self, doc_to_save):
     self.doc_to_post = doc_to_save
     self.doc_to_post["type"] = "measurement"
     self.deferred = None

   def __acct(self):
     acct = cloudant.Account(uri=db_url)
     acct.login(db_un, db_pw)
     db = acct[db_name]
     return acct, db

   def __performUploadInThread(self):
     acct, db = self.__acct()
     resp = db.design("nedm_default").post("_update/insert_with_timestamp",params=self.doc_to_post).json()

     if "ok" not in resp:
         return "Measurement settings could not be saved in DB"
     resp["type"] = "DocUpload"
     return resp

   def performUpload(self):
     self.deferred = threads.deferToThread(self.__performUploadInThread)
     return self.deferred

   def shouldUploadFile(self):
     return "filename" in self.doc_to_post and self.deferred is not None


   def __performUploadFileInThread(self, resp):
     if "ok" not in resp:
         return "Document not saved!"
     acct, db = self.__acct()
     fn = self.doc_to_post["filename"]

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

   def uploadFile(self):
     if not self.shouldUploadFile():
       return "File will not be saved"
     self.deferred.addCallback(lambda x: threads.deferToThread(self.__performUploadFileInThread, x))
     return self.deferred

