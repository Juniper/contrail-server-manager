Puppet::Parser::Functions.newfunction(:convert_netmask_to_cidr, :type => :rvalue) do |args|
  require 'ipaddr'
  retcon = IPAddr.new(args[0]).to_i.to_s(2).count("1")
end
