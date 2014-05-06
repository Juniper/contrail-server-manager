ostype=$1; shift
cfgm_index=$1; shift
zk_ip_list=("$@")
if [ $ostype == "Fedora" -o $ostype == "CentOS" ]; then
    zk_cfg="/etc/zookeeper/zoo.cfg"
    log4j=" /etc/zookeeper/log4j.properties"
    myid="/var/lib/zookeeper/data/myid"
elif [ $ostype == "Ubuntu" ]; then
    zk_cfg="/etc/zookeeper/conf/zoo.cfg"
    log4j="/etc/zookeeper/conf_example/log4j.properties"
    myid="/var/lib/zookeeper/myid"
fi


echo "maxSessionTimeout=120000" >> $zk_cfg
export ZOO_LOG4J_PROP="INFO,CONSOLE,ROLLINGFILE" >> /etc/zookeeper/zookeeper-env.sh
sed -i 's/^#log4j.appender.ROLLINGFILE.MaxBackupIndex=10/log4j.appender.ROLLINGFILE.MaxBackupIndex=11/g' $log4j

zk_index=1
for zk_ip in "${zk_ip_list[@]}"
do
    echo "server.$zk_index=$zk_ip:2888:3888" >> $zk_cfg
    zk_index=`expr $zk_index + 1`
done
echo "$cfgm_index" > $myid
