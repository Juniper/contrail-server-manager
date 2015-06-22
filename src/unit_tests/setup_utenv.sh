#!/bin/bash

pip install virtualenv
cd ..
virtualenv --system-site-packages unit_tests
cd unit_tests
source ./bin/activate
FILE=test-requirements.txt
easy_install http://darcs.idyll.org/~t/projects/figleaf-latest.tar.gz
while read line; do
   pip install $line
done < $FILE
mkdir fake-logs
deactivate
