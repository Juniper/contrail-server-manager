#get_device_name.rb

module Puppet::Parser::Functions
    newfunction(:get_device_name, :type => :rvalue,
                :doc => "Given IP address find interface name matching the IP address") do |args|
        retcon = ""
        requested_ipaddr = args[0]
        interfaces_fact =  lookupvar('interfaces')
        interfaces = interfaces_fact.split(",")
        interfaces.each do |interface|
            intf_ip = lookupvar("ipaddress_#{interface}")
            if requested_ipaddr == intf_ip
                retcon = interface
            end
        end
        if retcon == ""
            raise Puppet::ParseError, "No matching interface found : #{requested_ipaddr}" 
        end
        retcon
    end
end
