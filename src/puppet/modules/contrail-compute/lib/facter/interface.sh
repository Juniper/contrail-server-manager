#!/bin/bash
netstat -rn | grep ^"0.0.0.0" | awk '{ print $8 }'
