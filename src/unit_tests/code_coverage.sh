#!/bin/bash
source bin/activate
rm .figleaf
figleaf simulate.py
figleaf2html -d /var/www/figleafhtml .figleaf
