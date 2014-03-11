require 'facter'

Facter.add(:contrail_gateway) do
    setcode do
        Facter::Util::Resolution.exec(File.join(File.dirname(__FILE__), 'gateway.sh'))
    end
end

Facter.add(:contrail_interface) do
    setcode do
        Facter::Util::Resolution.exec(File.join(File.dirname(__FILE__), 'interface.sh'))
    end
end

Facter.add(:contrail_interface_rename_done) do
    setcode do
        Facter::Util::Resolution.exec(File.join(File.dirname(__FILE__), 'is_intf_renamed.sh'))
    end
end
