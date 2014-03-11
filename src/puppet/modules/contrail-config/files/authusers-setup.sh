oIFS="$IFS"; IFS=, ; set -- $1 ; IFS="$oIFS"
for i in "$@"; do
    sed -i -e "/$i:/d" -e "/$i.dns:/d" /etc/irond/basicauthusers.properties
    echo "$i:$i" >> /etc/irond/basicauthusers.properties
    echo "$i.dns:$i.dns" >> /etc/irond/basicauthusers.properties
done
