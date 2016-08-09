#!/usr/bin/python

from Tkinter import *
from tkMessageBox import showwarning, showinfo
from ScrolledText import ScrolledText
import ttk
import time
import re
import random

from DialImportFromInspire import *

# fake import function with 50% fail rate for tests
def fake_import(doi):
    time.sleep(0.2)
    if (random.random() < 0.5):
        return "fake error"

class login_win(Frame):

    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.pack(expand=YES, fill=BOTH)
        self.createWidgets()
        self.focus_set()
        self.grab_set()
        self.mainloop()
        self.destroy()

    def createWidgets(self):
        self.lframe = Frame(self)
        self.ltext  = Label(self.lframe,text="UCL login")
        self.lentry = Entry(self.lframe)
        self.pframe = Frame(self)
        self.ptext  = Label(self.pframe,text="UCL password")
        self.pentry = Entry(self.pframe, show="*")
        self.submit = Button(self,text="Submit",command=self.get_and_quit)

        self.lframe.pack(side=TOP,expand=YES,fill=X,padx=5, pady=5)
        self.pframe.pack(side=TOP,expand=YES,fill=X,padx=5, pady=5)
        self.ltext.pack(side=LEFT)
        self.lentry.pack(side=RIGHT)
        self.ptext.pack(side=LEFT)
        self.pentry.pack(side=RIGHT)
        self.submit.pack(side=TOP, padx=5, pady=5)
        self.lentry.bind('<Return>',(lambda event: self.get_and_quit()))
        self.pentry.bind('<Return>',(lambda event: self.get_and_quit()))
        self.lentry.focus()

    def get_and_quit(self):
        self.login  = self.lentry.get().strip()
        self.passwd = self.pentry.get().strip()
        if (self.login and self.passwd):
            self.quit()

class dial_gui(Frame):   

    doireg = re.compile('^[0-9]{2}\.[0-9]{4}/.+$')
           
    def __init__(self, master=None):
        Frame.__init__(self, master)   
        self.pack(expand=YES, fill=BOTH)
        log = login_win()
        self.login  = log.login
        self.passwd = log.passwd
        self.createWidgets()
        self.importer = DialImporter(log.login,log.passwd)

    def createWidgets(self):
        self.inframe = Frame(self)
        self.intext   = Label(self.inframe,text="Fetch DOIs for:")
        self.ininput  = Entry(self.inframe)
        self.ininput.bind('<Return>', (lambda event: self.fetch_dois()))
        self.inbutton = Button(self.inframe,text="get DOIs",command=self.fetch_dois)
        self.qb = Button(self, text='Quit', command=self.quit)   
        self.en = ScrolledText(self)
        self.en.insert(INSERT,'Enter DOI here, one line per DOI')
        self.rb = Button(self,text="Process",command=self.readentries)
        self.qb.pack(side=BOTTOM, fill=X, padx=10, pady=10)
        self.rb.pack(side=BOTTOM, fill=X, padx=10, pady=10)
        self.inframe.pack(side=TOP,fill=X,padx=10, pady=10)
        self.intext.pack(side=LEFT)
        self.ininput.pack(side=LEFT, padx=10)
        self.inbutton.pack(side=RIGHT)
        self.en.pack(side=TOP, fill=BOTH, padx=10, pady=10)
        self.ininput.focus()

    def fetch_dois(self):
        author = self.ininput.get().strip() 
        dois = "\n".join(self.importer.get_author_dois(author))
        self.en.delete('1.0', END)
        self.en.insert("1.0",dois)
        self.rb.focus()

    def readentries(self):
        self.content = self.en.get("1.0",END).strip().split("\n")
        badmatches = [doi for doi in self.content if not self.doireg.match(doi)]
        okmatches = [doi for doi in self.content if self.doireg.match(doi)]
        if len(badmatches):
            showwarning('','The following DOIs are malformed and will not be processed: \n'+'\n'.join(badmatches))
        fails = {}
        for doi in okmatches:
            print "Getting info about", doi
            error = self.importer.get_info(doi)
            if error: 
                fails[doi] = error
            else:
                print "Inserting into DIAL", doi
                try:
                    error = self.importer.push_to_dial()
                except Exception as push_err:
                    error = repr(push_err)
                if error : fails[doi] = error
        if len(fails):
            failmsg = '\n'.join([ key+", error: "+value for key, value in fails.items()])
            showwarning('','The following DOIs import failed :\n\n'+failmsg)
        else:
            showinfo('','Importation of all {} DOIs ended successfully'.format(len(okmatches)))
        self.importer.cleanup_files()

app = dial_gui()                       
app.master.title('Import to DIAL')    
app.mainloop()          
