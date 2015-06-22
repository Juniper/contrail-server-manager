#!/bin/bash
source bin/activate
rm .figleaf
figleaf monitoring/monitoring.py
figleaf2html -d /var/www/figleafhtml .figleaf
