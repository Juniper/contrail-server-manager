import argparse
import pdb
import commands
import sys

def provision_bgp(bgp_params, api_server_ip, api_server_port, router_asn , mt_options):
#    pdb.set_trace()
    if bgp_params == '':
        sys.exit(0)

    if  mt_options != "None":
        mt_options=mt_options[1:-1]
        multi_tenancy_list= mt_options.split(",")
        mt_options= "--admin_user %s --admin_password %s --admin_tenant_name %s" %(multi_tenancy_list[0],multi_tenancy_list[1],multi_tenancy_list[2])
    else :
        mt_options = ""
    bgp_peer_list = eval(bgp_params)
    for bgp_peer in bgp_peer_list:
        cmd = "python /opt/contrail/utils/provision_mx.py --api_server_ip %s --api_server_port %s --router_name %s --router_ip %s --router_asn %s %s" % (api_server_ip, api_server_port, bgp_peer[0], bgp_peer[1], router_asn, mt_options)
        ret,output = commands.getstatusoutput(cmd) 
        if (ret):
	    sys.exit(-1)
       

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bgp_params", help="BGP peer name and IP address")
    parser.add_argument("--api_server_ip", help="API Server IP")
    parser.add_argument("--api_server_port", help="API Server port")
    parser.add_argument("--router_asn", help="Router asn")
    parser.add_argument("--mt_options", help="Multi-tenancy options") 
    args = parser.parse_args()
    provision_bgp(args.bgp_params, args.api_server_ip, args.api_server_port, args.router_asn, args.mt_options)

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')
    main()
# end if __name__

