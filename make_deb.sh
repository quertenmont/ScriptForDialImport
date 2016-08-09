#!/bin/bash
dial_folder=dialimporter_0.9-1
sudo cp dialimport_gui.py ${dial_folder}/usr/local/bin/
sudo cp DialImportFromInspire.py ${dial_folder}/usr/lib/python2.7/dist-packages/
sudo cp dialimporter.desktop ${dial_folder}/usr/share/applications/
sudo chown root:root ${dial_folder}/usr/local/bin/dialimport_gui.py ${dial_folder}/usr/lib/python2.7/dist-packages/DialImportFromInspire.py ${dial_folder}/usr/share/applications/dialimporter.desktop
dpkg-deb --build ${dial_folder}/
