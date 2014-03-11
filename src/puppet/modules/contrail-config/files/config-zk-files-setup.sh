ostype=$1; shift
cfgm_index=$1; shift
zk_ip_list=("$@")
echo "maxSessionTimeout=120000" >> /etc/zookeeper/zoo.cfg
export ZOO_LOG4J_PROP="INFO,CONSOLE,ROLLINGFILE" >> /etc/zookeeper/zookeeper-env.sh
sed -i 's/^#log4j.appender.ROLLINGFILE.MaxBackupIndex=10/log4j.appender.ROLLINGFILE.MaxBackupIndex=11/g' /etc/zookeeper/log4j.properties

zk_index=1
for zk_ip in "${zk_ip_list[@]}"
do
    echo "server.$zk_index=$zk_ip:2888:3888" >> /etc/zookeeper/zoo.cfg
    zk_index=`expr $zk_index + 1`
done
echo "$cfgm_index" > /var/lib/zookeeper/data/myid
