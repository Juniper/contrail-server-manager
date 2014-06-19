ostype=$1; shift
cfgm_index=$1; shift
zk_ip_list=("$@")
zk_cfg="/etc/zookeeper/conf/zoo.cfg"
log4j="/etc/zookeeper/conf/log4j.properties"
myid="/var/lib/zookeeper/myid"

echo $ostype
echo $cfg_index
echo $zk_ip_list

echo "maxSessionTimeout=120000" >> $zk_cfg
echo "autopurge.purgeInterval=3" >> $zk_cfg
sed -i 's/^#log4j.appender.ROLLINGFILE.MaxBackupIndex=10/log4j.appender.ROLLINGFILE.MaxBackupIndex=11/g' $log4j
if [ $ostype == "Fedora" -o $ostype == "CentOS" ]; then
    echo "export ZOO_LOG4J_PROP=\"INFO,CONSOLE,ROLLINGFILE\"" >> /etc/zookeeper/zookeeper-env.sh
fi
if [ $ostype == "Ubuntu" ]; then
    echo "ZOO_LOG4J_PROP=\"INFO,CONSOLE,ROLLINGFILE\"" >> /etc/zookeeper/conf/environment
fi

zk_index=1
for zk_ip in "${zk_ip_list[@]}"
do
    echo "server.$zk_index=$zk_ip:2888:3888" >> $zk_cfg
    zk_index=`expr $zk_index + 1`
done
echo "$cfgm_index" > $myid
