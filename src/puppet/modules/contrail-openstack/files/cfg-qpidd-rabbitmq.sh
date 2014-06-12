filename=$1
    grep -q 'tcp_listeners.*0.0.0.0.*5672' $filename
    if [ $? -ne '0' ]; then
        echo "[" >> $filename
        echo "   {rabbit, [ {tcp_listeners, [{\"0.0.0.0\", 5672}]} ]" >> $filename
        echo "    }" >> $filename
        echo "]." >> $filename
    fi
