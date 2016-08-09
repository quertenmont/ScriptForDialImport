#!/usr/bin/env python
#coding: utf8 

import thread, time
import os, sys, re
from os.path import expanduser
import urlparse
from xml.dom import minidom
from glob import glob
try: 
    import Tkinter as tk
    from tkMessageBox import askquestion
except ImportError:
    print "ERROR: You need the python_tk package"
    sys.exit(1)

try:
    from selenium.common.exceptions import NoSuchElementException, ElementNotVisibleException, WebDriverException
    from selenium import webdriver
    from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as ec
    from selenium.webdriver.support.ui import Select
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError: 
    print "ERROR: You need the selenium package"
    sys.exit(1)

try:
    from mechanize._html import DefaultFactory,FormsFactory,RobustFactory
    from mechanize import Browser
    from mechanize._form import XHTMLCompatibleFormParser
except ImportError: 
    print "ERROR: you need the mechanize package"
    sys.exit(1)

# helper functions
def getSubfieldWithAttribute(datafield, attribute, value=""):
   for subfield in datafield.getElementsByTagName("subfield"):
      if(value==""):
         if(subfield.hasAttribute(attribute)): return subfield
      else:
         if(subfield.hasAttribute(attribute) and subfield.getAttribute(attribute)==value): return subfield
   return None

# custom exception class
class Error(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

# known journals
journals = {
    "JHEP": { "journal": "Journal of High Energy Physics", "EISSN": "1029-8479" }, 
    "Phys.Rev.Lett.": { "journal": "Physical Review Letters", "EISSN": "1079-7114" },
    "Phys.Rev.": { "journal": "Physical review. D, Particles and fields", "EISSN": "0556-2821" },
    "Eur.Phys.J.": { "journal": "European Physical Journal C. Particles and Fields", "EISSN": "1434-6052" },
    "JINST": { "journal": "Journal of Instrumentation", "EISSN": "1748-0221" },
    "Phys.Lett.": { "journal": "Physics Letters. Section B: Nuclear, Elementary Particle and High-Energy Physics", "EISSN": "1873-2445" },
    "Nature": { "journal": "Nature Physics", "EISSN": "1745-2481" }
}

# importer class
class DialImporter:
    """Import data from Inspires using DOI, and push it to UCLouvain DIAL"""

    CopyRights  = '####################################\n'
    CopyRights += '#    DIAL import from INSPIRE      #\n'
    CopyRights += '#   Loic.quertenmont@gmail.com     #\n'
    CopyRights += '#          January 2015            #\n'
    CopyRights += '####################################\n'

    br = Browser(factory=RobustFactory())
    br.set_handle_refresh(True)
    br.set_handle_robots(False)
    br.addheaders = [('User-agent', 'Firefox')]

    info = {}
    done = []

    def __init__(self, dialUsername, dialPassword):
        self.dialUsername = dialUsername
        self.dialPassword = dialPassword
        cfgdir = os.path.join(expanduser("~"),'.dialimport')
        if not os.path.exists(cfgdir): os.mkdir(cfgdir)
        tmpdir = os.path.join(cfgdir,'temp')
        if not os.path.exists(tmpdir): os.mkdir(tmpdir)
        self.cfgdir = cfgdir
        self.tmpdir = tmpdir
        self.done_file = os.path.join(cfgdir,'done')
        self.mydois_file = os.path.join(cfgdir,'mydois.html')

    def get_info(self, DOI):
        """ Fetch info from Inspires 
            Returns an error string or empty if successful """

        # empty info dict
        self.info = {}

        # strip whites
        DOI = DOI.strip()

        # check in list of already processed DOIs
        if self.already_processed(DOI): 
            return "Already processed, skipping"

        # open front page
        searchpage='http://inspirehep.net/search?&of=hd&p='+DOI
        self.br.open(searchpage)
        if("Your search did not match any records" in self.br.response().read()):
            return "DOI not known by inspirehep, skipping"

        # get url xml info
        links = self.br.links(url_regex="/xm")
        for link in links:
            linkToXML = urlparse.urljoin(link.base_url, link.url)
            break
        # else: return "Could not get XML info from inspirehep, skipping"

        # get url of pdf file
        links = self.br.links(url_regex="http://arXiv.org/pdf/")
        linkToPDF = ""
        for link in links:
            linkToPDF = urlparse.urljoin(link.base_url, link.url)
            break
        if not linkToPDF: return "Could not get PDF info: no arxiv entry ? Skipping"

        # download files
        pathToPDF = os.path.join(self.tmpdir,os.path.basename(linkToPDF))
        print linkToPDF, pathToPDF
        pathToXML = pathToPDF.replace(".pdf",".xml")
        print linkToXML, pathToXML
        self.br.retrieve(linkToXML, pathToXML)   
        self.br.retrieve(linkToPDF, pathToPDF)
        self.info['pathToPDF'] = pathToPDF
        self.info['pathToXML'] = pathToXML

        # fill info from XML
        collection = minidom.parse(pathToXML)
        record = collection.getElementsByTagName("record")[0]
        datafields = record.getElementsByTagName("datafield")
        self.info['OtherAuthors'] = False
        self.info['Authors'] = []

        # add the collaboration to the list of authors
        for datafield in datafields:
           if(not datafield.getAttribute("tag") == "710"): continue
           collaboration = getSubfieldWithAttribute(datafield, "code", "g").firstChild.data
           if(collaboration=="ALEPH" ): collaboration = "ALEPH Collaboration"
           if(collaboration=="DELPHI"): collaboration = "DELPHI Collaboration"
           if(collaboration=="L3"    ): collaboration = "L3 Collaboration"
           if(collaboration=="OPAL"  ): collaboration = "OPAL Collaboration"
           self.info['Authors'].append(collaboration)
  
        # get the list of authors associated to Louvain
        # this sometimes fails with AttributeError
        try: 
            for datafield in datafields:
               # if(not datafield.getAttribute("tag") == "700"): continue
               # added tag 100 for first author
               if(not datafield.getAttribute("tag") in ["100","700"]): continue
               if("Louvain" in getSubfieldWithAttribute(datafield, "code", "u").firstChild.data):
                  self.info['Authors'].append(getSubfieldWithAttribute(datafield, "code", "a").firstChild.data)
               else:
                  self.info['OtherAuthors'] = True
                  continue
        except AttributeError:
            return "skipping: could not read some XML info" 

        if not len(self.info['Authors']): 
            return "skipping: no UCLouvain authors"

        # get the title
        self.info['Title'] = ""
        for datafield in datafields:
           if(not (datafield.getAttribute("tag") == "246" or datafield.getAttribute("tag") == "245")): continue
           self.info['Title'] = getSubfieldWithAttribute(datafield, "code", "a").firstChild.data
  
        # get the abstract
        self.info['Abstract'] = ""
        for datafield in datafields:
           if(not (datafield.getAttribute("tag") == "520")): continue
           abstractDesc = getSubfieldWithAttribute(datafield, "code", "9")
           if(abstractDesc!=None and abstractDesc.firstChild.data!="arXiv"): continue
           abstractElem = getSubfieldWithAttribute(datafield, "code", "a")
           if(abstractElem!=None): self.info['Abstract'] = abstractElem.firstChild.data
  
        # get the DOI
        self.info['DOI'] = ""
        for datafield in datafields:
           if(not (datafield.getAttribute("tag") == "024")): continue
           self.info['DOI'] = getSubfieldWithAttribute(datafield, "code", "a").firstChild.data
  
        self.info['STATUS'] = ""
        self.info['YEAR'] = ""
        # get the YEAR of submission
        for datafield in datafields:
           if(not (datafield.getAttribute("tag") == "269")): continue
           self.info['YEAR'] = getSubfieldWithAttribute(datafield, "code", "c").firstChild.data.split('-')[0]
        # get the YEAR of publication
        for datafield in datafields:
           if(not (datafield.getAttribute("tag") == "260")): continue
           self.info['YEAR'] = getSubfieldWithAttribute(datafield, "code", "c").firstChild.data.split('-')[0]
           self.info['STATUS'] = "Accepté/Sous presse"
        # get the STATUS of publication
        for datafield in datafields:
           if(not (datafield.getAttribute("tag") in ["500","980"])): continue
           if("ubmitted" in getSubfieldWithAttribute(datafield, "code", "a").firstChild.data): self.info['STATUS'] = "Soumis"
           if("ublished" in getSubfieldWithAttribute(datafield, "code", "a").firstChild.data): self.info['STATUS'] = "Publié"
 
        # fill journal info 
        self.info['JOURNAL'] = " "
        self.info['VOLUME']  = " "
        self.info['PAGES']   = " "
        self.info['NUMBER']  = " "
        self.info['EISSN']   = "0000-0000"
        for datafield in datafields:
           if(self.info['JOURNAL'] != " " or not (datafield.getAttribute("tag") == "773")): continue #skip block the "JOURNAL" is already filled, otherwise we will get eratums as well
           self.info['PAGES']   = getSubfieldWithAttribute(datafield, "code", "c").firstChild.data
           self.info['JOURNAL'] = getSubfieldWithAttribute(datafield, "code", "p").firstChild.data
           self.info['VOLUME']  = getSubfieldWithAttribute(datafield, "code", "v").firstChild.data
           self.info['YEAR']    = getSubfieldWithAttribute(datafield, "code", "y").firstChild.data
  
  
        # check status: conference paper, unpublished
        isCONFpaper = False
        for datafield in datafields:
           if(not (datafield.getAttribute("tag") == "980")): continue
           if("Conference" in getSubfieldWithAttribute(datafield, "code", "a").firstChild.data):isCONFpaper=True
  
        if(isCONFpaper):
            return "This DOI will be skipped because it is a conference paper" 
  
        if(self.info['STATUS'] != "Publié"):
            return "This DOI will be skipped because it is not published (yet)" 
        return ''

    def already_processed(self, DOI):
        """ Returns true if the DOI has already been processed """
        if not self.done: 
            try:
                with open(self.done_file,'r') as f:
                    self.done = [doi.strip() for doi in f.readlines()]
            except IOError:
                # put something fake in self.done to prevent further useless tries
                self.done = ["xx.xxxx/xxxxxx"]
                pass
        return DOI in self.done

    def info(self):
        """ Show info """
        return self.info

    def get_author_dois(self, authorName):
        """ Using the authorName, get list of DOIs from Inspires 
            Returns an error string or empty if successful """
        dois = []
        res = os.system('wget -O '+self.mydois_file+' "http://inspirehep.net/search?ln=fr&ln=fr&p='+authorName+'&of=htcv&action_search=Recherche&sf=&so=d&rm=&rg=25&sc=0"')
        if(res):
            raise Error("Could not access inspirehep")
        else:
            with open(self.mydois_file, 'r') as f:
                for line in f:
                    if('dx.doi.org' in line):
                        DOI = '10.' + (line.split('>10.')[1]).split('</a>')[0]
                        dois.append(DOI)
        return dois
   
    def cleanup_files(self):
        """ remove temp files from tmpdir """
        print "deleting:"
        for fi in glob(os.path.join(self.tmpdir,'*')):
            print fi
            time.sleep(0.2)
            os.remove(fi)
        print "Cleanup done"

    def push_to_dial(self):
        """ Push the current info to DIAL
            Returns an error string or empty if successful """

        if not self.info:
            return "Push should only be called once the information has been filled"


        #create the browser emulator 

# the lines below are necessary to work with FF 47+, however some function (select) are broken in that version
#        firefox_capabilities = DesiredCapabilities.FIREFOX
#        firefox_capabilities['marionette'] = True
#        driver = webdriver.Firefox(capabilities=firefox_capabilities)

        # specify obsolete firefox version due to bugs with the recent ones
        binary = FirefoxBinary('/home/jdf/temp/firefox/firefox')
        driver = webdriver.Firefox(firefox_binary=binary)
        driver.implicitly_wait(10) 
        wait = WebDriverWait(driver, 10)

        #transform journal name and get ISSN as used in DIAL
        try:
            self.info['EISSN']   = journals[self.info['JOURNAL']]['EISSN']
            self.info['JOURNAL'] = journals[self.info['JOURNAL']]['journal']
        except KeyError:
            driver.quit()
            return "This DOI will be skipped because its Journal: "+self.info['JOURNAL']+" is unknown. You can add it to the 'journals' list"

        #LOGIN PAGE
        driver.get("http://dial.academielouvain.be/cgi-bin/valet_UCL/submit.cgi?view=ucl_document")
        elem = driver.find_element_by_name("username")
        elem.send_keys(self.dialUsername)
        elem = driver.find_element_by_name("password")
        elem.send_keys(self.dialPassword)
        elem.submit()

        #NEW DEPOSIT
        try:
            elem = driver.find_element_by_name("newDeposit")
            elem.submit()
        except NoSuchElementException:
            driver.quit()
            return "Login failed, exiting"

        #CHECK IF RECORD ALREADY EXIST
        elem = driver.find_element_by_name("title")
        elem.send_keys(self.info['Title'])
        elem = driver.find_element_by_xpath("//input[@value='Rechercher']")
        elem.click()
        time.sleep(3) #sleep for 5sec to get the search results

        elem = driver.find_element_by_id("results")
        searchResults = repr(elem.text)
        if(not "Aucun document ne correspond aux crit" in searchResults):
           # Record is already in DIAL, add it to the list of DOI's to skip
           with open(self.done_file,"a") as f:
               f.write(self.info["DOI"]+"\n");
           driver.quit()
           return "This DOI will be skipped because it is already in DIAL"
           
        select = Select(driver.find_element_by_id("year"))
        select.select_by_visible_text(self.info['YEAR'])
        elem.submit()

        # Type de document
        select = Select(driver.find_element_by_id("documentType"))
        select.select_by_value("serial")

        # SousType de document
        select = Select(driver.find_element_by_id("subtype"))
        select.select_by_visible_text("Article de recherche")

        # Abstract
        elem = driver.find_element_by_id("abstract")
        elem.send_keys(self.info['Abstract'])

        # Language
        select = Select(driver.find_element_by_id("language"))
        select.select_by_value("eng")

        # Do this before the authors, because it crashes from time to time, so better to start by this
        # Ajouter l'affiliation IRMP
        elem = driver.find_element_by_id("action-affiliation")
        elem.click()
        ## time.sleep(1) #sleep for 1sec to get the dialog form
        select = Select(driver.find_element_by_id("__affiliation_institution"))
        select.select_by_visible_text("UCL")
        time.sleep(3) #sleep for 1sec to get the departements right
        select = Select(driver.find_element_by_id("__affiliation_departement"))
        time.sleep(3) #sleep for 1sec to get the departements right
        options = select.options
        for option in options:
           if("SST/IRMP" in repr(option.text)):
              select.select_by_visible_text(option.text)
              break

        elem = driver.find_element_by_xpath("//div[@aria-labelledby='ui-dialog-title-dialog-affiliation']/div/div/button[@type='button']/span[text()='Ajouter']")
        elem.click()
        time.sleep(1)

        #Auteurs
        for a in self.info['Authors']:
           addAuthor = driver.find_element_by_id("action-user")
           addAuthor.click()

           elem = driver.find_element_by_id("author_name")
           if("Lemaitre" in a):
               # VL is never found, probably because of the ^ in his name : should we substitute it by default ?
               a = re.sub('Lemaitre',u'Lemaître',a)

           elem.send_keys(a)
           time.sleep(1) # sleep for the auto complete to finish

           elem.send_keys(Keys.ARROW_DOWN)
           # if("Lemaitre" in a): elem.send_keys(Keys.ARROW_DOWN) #for unkown reason lemaitre is second on the list
           elem.send_keys(Keys.RETURN)
           time.sleep(1) # sleep for the auto complete to finish
           ## elem.click()

           select = Select(driver.find_element_by_id("author_role"))
           select.select_by_visible_text("Auteur")
          
           select = Select(driver.find_element_by_id("author_institution"))
           select.select_by_visible_text("UCL")
  
           clicked = False
           tries = 0
           while not clicked and tries < 5:
               try:
                   elem = driver.find_element_by_xpath("//div[@aria-labelledby='ui-dialog-title-dialog-author']/div/div/button[@type='button']/span[text()='Ajouter']")
                   elem.click()
                   tries += 1 
               except ElementNotVisibleException:
                   # popup is gone, ok
                   clicked = True
               except WebDriverException:
                   # something is covering the popup, trying again later
                   time.sleep(2)
           # time.sleep(5)

        #check the box for additional authors
        if(self.info['OtherAuthors'] == True):
           elem = driver.find_element_by_name("etal")
           elem.click()

        #document status
        select = Select(driver.find_element_by_id("documentStatus_s"))
        if(self.info['STATUS'] != ""):   select.select_by_visible_text(self.info['STATUS']) 
        else:   select.select_by_value("na")

        #add DOI
        elem = driver.find_element_by_id("doi")
        elem.send_keys(self.info['DOI'])

        elem = driver.find_element_by_id("periodical_title")
        elem.send_keys(self.info['JOURNAL'])
        elem = driver.find_element_by_id("periodical_volume")
        elem.send_keys(self.info['VOLUME'])
        elem = driver.find_element_by_id("periodical_numero")
        elem.send_keys(self.info['NUMBER'])
        elem = driver.find_element_by_id("periodical_pages")
        elem.send_keys(self.info['PAGES'])
        elem = driver.find_element_by_id("periodical_year")
        elem.send_keys(self.info['YEAR'])
        elem = driver.find_element_by_id("eissn")
        elem.send_keys(self.info['EISSN'])

        #peer reviewed journal
        elem = driver.find_element_by_xpath("//input[@type='radio'][@value='yes']")
        elem.click()

        time.sleep(2)
        elem.submit() #all done

        #MOVING TO NEXT PAGE 
        #set the path to the pdf file:
        elem = driver.find_element_by_id("original_filename")
        elem.send_keys(self.info['pathToPDF'])
        time.sleep(5) # DEBUG

        #set the access to "libre"
        elem = driver.find_element_by_xpath("//input[@type='radio'][@value='libre']")
        elem.click()

        #check the agreement box
        elem = driver.find_element_by_id("licence")
        elem.click()

        elem = driver.find_element_by_id("uploadSubmit")
        elem.click() #upload the file

        time.sleep(15) #wait for 15sec to upload the file

        elements = driver.find_elements_by_xpath("//input[@type='submit']")
        for elem in elements:
           if("Passez" in repr(elem.get_attribute('value'))): elem.click()
        ## time.sleep(3) #to get the new webpage

        # we are on the last page to validate all the data
        # TODO : manage this in the GUI
        VERIFY = True
        if(VERIFY==True):
           # print "Imported data can be verified"
           # ans = raw_input("If data could be imported press 'y' otherwise press 'n' and the script will stop here\n")
           # if(ans not in ["y","Y"]): sys.exit(1)
           root = tk.Tk()
           root.withdraw()
           ans = askquestion("Confirm submission","Please review the input in the browser.\nDo you want to Submit this to Dial ?")
           if ans != "yes": 
               driver.quit()
               return 'Quitting on user request'
        
        elements = driver.find_elements_by_xpath("//input[@type='submit']")
        for elem in elements:
           if("Enregistrer le" in repr(elem.get_attribute('value'))): elem.click()
        time.sleep(15) #wait for the record to be inserted in DIAL
        driver.quit()

        # add successful DOI to the done file
        with open(self.done_file,"a") as f:
            f.write(self.info["DOI"]+"\n");
        return '' 





if __name__ == '__main__':
    """ This is only a test procedure, do not use it """
    dois = ['10.1103/PhysRevLett.108.111801']
    test = DialImporter("jdefavereau",passwd)
    print test.already_processed('10.1007/JHEP02(2014)057')
    # test.get_author_dois()
    for doi in dois: 
        print doi
        print test.get_info(doi)
        # DEBUG: to be able to add existing entries
        test.info['Title'] += ' DEBUG DEBUG'
        # DEBUG: to make upload shorter 
        test.info['Authors'] = [test.info['Authors'][1]]
        print test.info
        print test.push_to_dial()
