# contents

 - DialImportFromInspire.py: the import script, reads from inspirehep, writes to dial. 
 - dialimport_gui.py: the gui to make all this easier
 - dialimporter.desktop: the app file to have somewhere to click on (on linux)
 - dialimporter_0.9-1: folder used to build the deb file, see below

# usage
## any system:

 - copy DialImportFromInspire.py and dialimport_gui.py anywhere confortable
 - make sure the mechanize and selenium package are installed (pip install --user selenium mechanize)
 - start the gui with `./dialimport_gui.py`

## on ubuntu

 - run `dpkg-deb --build dialimporter_0.9-1` : you'll get an installable deb file with the latest version
 - run `dpkg -i dialimporter_0.9-1.deb` : dialimporter should now appear in your applications