operatingsystem=$1
filename=$2
if [ $operatingsystem == "centos" -o $operatingsystem == "fedora" ]; then
    grep -q '^max-connections' $filename
    if [ $? -ne '0' ]; then
        echo "max-connections=2048" >> $filename
    else
        sed -i 's/^max-connections.*$/max-connections=2048/g' $filename
    fi
fi
if [ $operatingsystem == "Ubuntu" ]; then
    grep -q 'tcp_listeners.*0.0.0.0.*5672' $filename 
    if [ $? -ne '0' ]; then
        echo "[" >> $filename
        echo "   {rabbit, [ {tcp_listeners, [{\"0.0.0.0\", 5672}]} ]" >> $filename
        echo "    }" >> $filename
        echo "]." >> $filename
    fi
fi
