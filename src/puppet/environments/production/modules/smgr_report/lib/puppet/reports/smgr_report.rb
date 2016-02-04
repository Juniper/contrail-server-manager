require 'puppet'
require 'net/http'
require 'uri'

Puppet::Reports.register_report(:smgr_report) do

desc <<-DESC
A new report processor.
DESC

  def process
    client = self.host
    logs = self.logs
    print "start new report\n"
    print "host: " + self.host + "\n"
    print "status: " + self.status+ "\n"
    hostname = Socket.gethostname
    cur_time=Time.now.strftime("%d-%m-%Y_%H:%M:%S")
    print "Server Hostname:" + hostname + "\n"
    print "Server cur_time:" + cur_time+ "\n"
    log_dir = "/var/log/contrail-server-manager/provision"
    config_version = self.host + "_" + cur_time
    dir = File.join(log_dir, client)
    Dir.mkdir(dir) unless File.exists?(dir)
    print config_version + "\n"
    file = config_version + ".log"
    destination = File.join(dir, file)
    log_data = ""
    logs.each do |item|
      resource = item.source
      msg = item.message
      time = item.time.strftime("%d-%m-%Y_%H:%M:%S")
      if msg.include? "TurningOffPuppetAgent__"
        puts "Puppet agent Turned Off."
        return
      end
      if msg.include? "Could not find node "
        puts "Catalog for server not found."
        return
      end
      if msg.include? "Caught TERM; calling stop"
        puts "Puppet agent exited"
        return
      end
      log_data += time + ":" + resource + ":" + msg + "\n"
    end
    File.open(destination,"w") do |f|
      f.write(log_data)


    if self.status == "failed"
      puts "puppet run failed"
      client_fqdn = client.split(".")
      client_hostname = client_fqdn[0]
      print "log data =" + log_data +"\n"

      http = Net::HTTP.new(hostname, 9002)

      log_path = client +"/" +file + "\n"
      print "http://" + hostname + ":9001/logs/"+ log_path + "\n"
      response = http.send_request('PUT', '/server_status?server_id=' + client_hostname + '&state=puppet_failed')
      puts "response code is " + response.code
      if response.code != "200"
        puts "Error posting puppet status"
      end
    else
      puts "puppet run successful"
    end
    end
  end
end
