#!/bin/bash

if [ $# -ne 2 ]
then
        echo "Usage $0 <contrail package deb file> <puppet manifest to replace>"
        exit
fi

deb_file=$1
puppet_manifest=$2

rm -rf ~/debmodify
mkdir ~/debmodify
echo "Contrail package : $deb_file"
echo "Puppet manifest to replace : $puppet_manifest"
dpkg-deb -x $deb_file ~/debmodify
dpkg-deb -e $deb_file ~/debmodify/DEBIAN
cp $puppet_manifest ~/debmodify/opt/contrail/puppet/contrail-puppet-manifest.tgz 
cp $deb_file $deb_file.old
dpkg -b ~/debmodify $deb_file 
