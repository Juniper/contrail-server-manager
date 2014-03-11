pylibpath=`python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()"`
if [ $1 == "Fedora" -o $1 == "Centos" ]; then
    runuser -p apache -c "echo yes | django-admin collectstatic --settings=settings --pythonpath=$pylibpath/openstack_dashboard"
fi
