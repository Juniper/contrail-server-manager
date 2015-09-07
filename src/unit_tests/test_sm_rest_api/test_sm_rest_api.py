# Module to implement unit tests for server manager CRUD REST API calls testing.
# As these units are tested most of other logic in server manager code including
# validations, error reporting logging, database interface etc. get tested.
# Server Manager has primarily 3 externla interfaces :
#     1. REST API to clients
#     2. Cobbler interface
#     3. puppet interface
# Of the three above, REST API interface from clients is NOT mocked. We make use of
# requests package to make REST calls to server manager and check responses.
# Cobbler interface is stubbed out (mocked).
# Puppet interface is NOT mocked. The serer manager to puppet interface is primarily
# handled thru creation of certain files for puppet manager to use. Our test functions
# will check that the files needed by puppet are created correctly to unit test correct
# functionality of that portion of the code.
# The tests can be broken into following categories. 
#     1. Configure server object REST API Calls
#     2. Configure cluster object REST API calls
#     3. Configure image object REST API calls
#     4. Configure package object REST API calls
#     5. Reimage operation REST API (for different image types)
#     6. Provision operation REST API (for different contrail package types)
#
import sys, os, time, pdb
from gevent import monkey
monkey.patch_all()
import gevent
import bottle
import unittest
import requests
from decimal import *
sys.path.append(os.path.abspath(os.pardir))
sys.path.append(os.path.abspath(os.pardir + "/utils"))
sys.path.append(os.path.abspath(os.pardir + "/vmware"))
from flexmock import flexmock, Mock
import mock
import server_mgr_main
import socket
import json

# Utility function to get a free port for running bottle server.
def get_free_port():
    tmp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tmp_sock.bind(('', 0))
    free_port = tmp_sock.getsockname()[1]
    tmp_sock.close()

    return free_port
# end get_free_port

# Utility function to make test functions wait till server manager
# is up and running.
def block_till_port_listened(server_ip, server_port):
    svr_running = False
    while not svr_running:
        try:
            s = socket.create_connection((server_ip, server_port))
            s.close()
            svr_running = True
        except Exception as err:
            if err.errno == errno.ECONNREFUSED:
                print "port %s not up, retrying in 2 secs" % (server_port)
                gevent.sleep(2)
# end block_till_port_listened

# Function to launch server manager on a separate gevent. test functions will
# use requests package to make calls to server manager using REST. It's called as
# part of test setup.
def launch_server_manager(
    listen_ip, listen_port, config_file):
    # Use a local logger.conf file for server manager debug and transaction logging settings.
    flexmock(server_mgr_main.ServerMgrlogger._ServerMgrlogger, log_file='./logger.conf')
    flexmock(server_mgr_main.ServerMgrTlog, log_file='./logger.conf')
    # mock all prints to go to a file
    #f = file('out.txt', 'w')
    #flexmock(sys, stdout=f)
    # Use local up address and unused port, instead of configured one to run SM.
    args_list = []
    args_list += ['--listen_ip_addr', '%s' %(listen_ip)]
    args_list += ['--listen_port', '%s' %(listen_port)]
    args_list += ['--config_file', config_file]
    with mock.patch('server_mgr_cobbler.xmlrpclib.Server') as mock_server:
        with mock.patch('server_mgr_cobbler.subprocess') as mock_subprocess:
	    vnc_server_mgr = server_mgr_main.VncServerManager(args_list)
	    pipe_start_app = vnc_server_mgr.get_pipe_start_app()
	    server_ip = vnc_server_mgr.get_server_ip()
	    server_port = vnc_server_mgr.get_server_port()
	    try:
	        bottle.run(app=pipe_start_app,server = 'gevent', host=server_ip, port=server_port)
	    except Exception as e:
	        # cleanup gracefully
	        print 'Exception error is: %s' % e
	        vnc_server_mgr.cleanup()
#end launch_api_server

#Class for testing Server manager rest API calls for server, cluster and tag object
class TestSMRestApi(unittest.TestCase):
    #setup function which sets up environemnt required for unit testing 
    @classmethod
    def setUpClass(cls):
        # Remove existing database and log files.
        try:
            os.remove("smgr_data.db")
            os.remove("debug.log")
            os.remove("inventory_debug.log")
            os.remove("monitoring_debug.log")
            os.remove("transaction.log")
        except:
            pass
        cls.server_ip = socket.gethostbyname(socket.gethostname())
        cls.server_port = get_free_port()
        cls._server_manager_greenlet = gevent.spawn(
            launch_server_manager, cls.server_ip, cls.server_port,
            "sm-config.ini")
        block_till_port_listened(cls.server_ip, cls.server_port)

    # Teardown function called after all test cases.
    @classmethod
    def tearDownClass(cls):
        tag_data = '{"tag4": "rack", "tag5": "user_tag", "tag6": "", "tag7": "", "tag1": "datacenter", "tag2": "floor", "tag3": "hall"}'
        response = requests.put('http://%s:%s/tag' %(
            cls.server_ip, cls.server_port), data=tag_data, headers = {'content-type': 'application/json'})

    # Test case to test cluster get REST API call.
    def testGetClusterEmptyRestApi(self):
        # Get clusters from db and make sure list is empty
        response = requests.get('http://%s:%s/cluster' %(self.server_ip, self.server_port))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(eval(response.content)['cluster'], [])
    # end testGetClusterEmptyRestApi

    # Test case to test cluster add REST API call.
    def testAddClusterRestApi(self):
        # Add clusters to DB, request adds 2 clusters. Make sure response of add is ok.
        # then get all clusters and check response to confirm there are 2 clusters.
        # also get a cluster by selection criteria and make sure correct cluster is returned.
        with open('test_cluster.json') as data_file:    
            cluster_payload = data_file.read()
        response = requests.put(
            'http://%s:%s/cluster' %(self.server_ip, self.server_port),
            data=cluster_payload,
            headers = {'content-type': 'application/json'})
        # Clusters should be added successfully.
        self.assertEqual(response.status_code, 200)
    # end testAddClusterRestApi

    # Test case to test cluster get REST API call, after 2 clusters are added to the DB.
    def testGetClusterAllRestApi(self):
        response = requests.get('http://%s:%s/cluster' %(self.server_ip, self.server_port))
        self.assertEqual(response.status_code, 200)
        clusters = response.json()['cluster']
        cluster_ids = [cluster['id'] for cluster in clusters]
        self.assertEqual(len(cluster_ids), 2)
        self.assertTrue(id in ['test-cluster-01', 'test-cluster-02'] for id in cluster_ids)
    # end testGetClusterAllRestApi

    # Test case to test cluster get REST API call for a specific cluster
    def testGetSpecificClusterRestApi(self):
        # Check get cluster with cluster-id for one of the clusters, should succeed
        response = requests.get(
            'http://%s:%s/cluster?id=%s' %(
                self.server_ip, self.server_port, "test-cluster-01"))
        self.assertEqual(response.status_code, 200)
        cluster = response.json()['cluster'][0]
        self.assertEqual(cluster['id'], 'test-cluster-01')
    # end testGetSpecificClusterRestApi

    # Test case to test cluster get REST API call for a non-existing cluster
    def testGetNonexistingClusterRestApi(self):
        # Check get cluster with a non-existing cluster id, should return empty response.
        response = requests.get(
            'http://%s:%s/cluster?id=%s' %(
                self.server_ip, self.server_port, "nonexistingcluster"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(eval(response.content)['cluster'], [])
    # end testGetNonexistingClusterRestApi

    # Test case to test cluster modify REST API call
    def testModifyClusterRestApi(self):
        # Modify one of the clusters, get and ensure modification is handled correctly.
        # When modifying, modify a column field in cluster_table, and also some parameters
        # in fields which are stored as blob (e.g. network, parameters, etc).
        response = requests.get(
            'http://%s:%s/cluster?id=%s&detail=True' %(
                self.server_ip, self.server_port, "test-cluster-01"))
        self.assertEqual(response.status_code, 200)
        cluster = response.json()['cluster'][0]
        cluster['email']='test@test.com'
        cluster['base_image_id']='test_base_image_id'
        cluster['parameters']['router_asn']='65000'
        cluster['parameters']['subnet_mask']='255.255.0.0'
        cluster['parameters']['haproxy']=''
        newdata = {"cluster":[]}
        newdata['cluster'].append(cluster)
        response = requests.put(
            'http://%s:%s/cluster' %(self.server_ip, self.server_port),
            data=json.dumps(newdata),
            headers = {'content-type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        response = requests.get(
            'http://%s:%s/cluster?id=%s&detail=True' %(
                self.server_ip, self.server_port, "test-cluster-01"))
        self.assertEqual(response.status_code, 200)
        cluster = response.json()['cluster'][0]
        self.assertEqual(cluster['email'], 'test@test.com')
        self.assertEqual(cluster['base_image_id'], 'test_base_image_id')
        self.assertEqual(cluster['parameters']['router_asn'], '65000')
        self.assertEqual(cluster['parameters']['subnet_mask'], '255.255.0.0')
        self.assertEqual(cluster['parameters']['haproxy'], '')
    # end testModifyClusterRestApi

    def testDeleteClusterRestApi(self):
        # Delete a cluster, confirm result of delete REST, then go ahead and make get call
        # on the deleted cluster and ensure that it is deleted.
        response = requests.delete(
            'http://%s:%s/cluster?id=%s' %(
                self.server_ip, self.server_port, "test-cluster-01"))
        self.assertEqual(response.status_code, 200)
        response = requests.get(
            'http://%s:%s/cluster?id=%s' %(
                self.server_ip, self.server_port, "test-cluster-01"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(eval(response.content)['cluster'], [])

        response = requests.get(
            'http://%s:%s/cluster' %(self.server_ip, self.server_port))
        self.assertEqual(response.status_code, 200)
        self.assertTrue('test-cluster-02' in response.content)

        response = requests.delete(
            'http://%s:%s/cluster?id=%s' %(
                self.server_ip, self.server_port, "test-cluster-02"))
        self.assertEqual(response.status_code, 200)
        response = requests.get(
            'http://%s:%s/cluster?id=%s' %(
                self.server_ip, self.server_port, "test-cluster-02"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(eval(response.content)['cluster'], [])
    # end testDeleteClusterRESTApi

    # Test case to test server get REST API call.
    def testGetServerEmptyRestApi(self):
        # Get servers from db and make sure list is empty
        response = requests.get('http://%s:%s/server' %(self.server_ip, self.server_port))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(eval(response.content)['server'], [])
    # end testGetServerEmptyRestApi

    # Test case to test server add REST API call.
    def testAddServerRestApi(self):
        # Add servers to DB, request adds 2 servers. Make sure response of add is ok.
        # then get all servers and check response to confirm there are 2 servers.
        # also get a server by selection criteria and make sure correct server is returned.
        with open('server.json') as data_file:    
            server_payload = data_file.read()
        response = requests.put(
            'http://%s:%s/server' %(self.server_ip, self.server_port),
            data=server_payload,
            headers = {'content-type': 'application/json'})
        # Server requires a cluster, so SM should return error code 404.
        self.assertEqual(response.status_code, 404)

        # Now create cluster and retry, it should succeed this time.
        with open('cluster.json') as data_file:    
            cluster_payload = data_file.read()
        response = requests.put(
            'http://%s:%s/cluster' %(self.server_ip, self.server_port),
            data=cluster_payload,
            headers = {'content-type': 'application/json'})
        self.assertEqual(response.status_code, 200)

        # Retry add server. It should succeed now.
        response = requests.put(
            'http://%s:%s/server' %(self.server_ip, self.server_port),
            data=server_payload,
            headers = {'content-type': 'application/json'})
        self.assertEqual(response.status_code, 200)
    # end testAddServerRestApi

    # Test case to test server get REST API call, after 2 servers are added to the DB.
    def testGetServerAllRestApi(self):
        response = requests.get('http://%s:%s/server' %(self.server_ip, self.server_port))
        self.assertEqual(response.status_code, 200)
        servers = response.json()['server']
        server_ids = [server['id'] for server in servers]
        self.assertEqual(len(server_ids), 2)
        self.assertTrue(id in ['testserver1', 'testserver2'] for id in server_ids)
    # end testGetServerAllRestApi

    # Test case to test server get REST API call for a specific server
    def testGetSpecificServerRestApi(self):
        # Check get server with server-id for one of the servers, should succeed
        response = requests.get(
            'http://%s:%s/server?id=%s' %(
                self.server_ip, self.server_port, "testserver1"))
        self.assertEqual(response.status_code, 200)
        server = response.json()['server'][0]
        self.assertEqual(server['id'], 'testserver1')
    # end testGetSpecificServerRestApi

    # Test case to test server get REST API call for a non-existing server
    def testGetNonexistingServerRestApi(self):
        # Check get server with a non-existing server id, should return empty response.
        response = requests.get(
            'http://%s:%s/server?id=%s' %(
                self.server_ip, self.server_port, "nonexistingserver"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(eval(response.content)['server'], [])
    # end testGetNonexistingServerRestApi

    # Test case to test server modify REST API call
    def testModifyServerRestApi(self):
        # Modify one of the servers, get and ensure modification is handled correctly.
        # When modifying, modify a column field in server_table, and also some parameters
        # in fields which are stored as blob (e.g. network, parameters, etc).
        response = requests.get(
            'http://%s:%s/server?id=%s&detail=True' %(
                self.server_ip, self.server_port, "testserver1"))
        self.assertEqual(response.status_code, 200)
        server = response.json()['server'][0]
        server['tag']['datacenter'] = 'new_demo_dc'
        server['roles'].remove('compute')
        server['email'] = 'test@test.com'
        newdata = {"server":[]}
        newdata['server'].append(server)
        response = requests.put(
            'http://%s:%s/server' %(self.server_ip, self.server_port),
            data=json.dumps(newdata),
            headers = {'content-type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        response = requests.get(
            'http://%s:%s/server?id=%s&detail=True' %(
                self.server_ip, self.server_port, "testserver1"))
        self.assertEqual(response.status_code, 200)
        server = response.json()['server'][0]
        self.assertEqual(server['tag']['datacenter'], 'new_demo_dc')
        self.assertTrue('compute' not in server['roles'])
        self.assertEqual(server['email'], 'test@test.com')
    # end testModifyServerRestApi

    def testDeleteServerRestApi(self):
        # Delete a server, confirm result of delete REST, then go ahead and make get call
        # on the deleted server and ensure that it is deleted.
        response = requests.delete(
            'http://%s:%s/server?id=%s' %(
                self.server_ip, self.server_port, "testserver2"))
        self.assertEqual(response.status_code, 200)
        response = requests.get(
            'http://%s:%s/server?id=%s' %(
                self.server_ip, self.server_port, "testserver2"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(eval(response.content)['server'], [])
    # end testDeleteServerRESTApi

    # Test case to test tag get REST API call.
    def testGetTagEmptyRestApi(self):
        # Get tag from db and make sure list has the 5 pre defined tags.
        response = requests.get('http://%s:%s/tag' %(self.server_ip, self.server_port))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(eval(response.content)['tag1'], 'datacenter')
        self.assertEqual(eval(response.content)['tag2'], 'floor')
        self.assertEqual(eval(response.content)['tag3'], 'hall')
        self.assertEqual(eval(response.content)['tag4'], 'rack')
        self.assertEqual(eval(response.content)['tag5'], 'user_tag')
    # end testGetTagEmptyRestApi

    # Test case to test tag add REST API call.
    def testAddTagRestApi(self):
        # Add tags to DB, request adds 2 tags. Make sure response of add is ok.
        # then get all tags and check response to confirm there are 7 tags.
        with open('test_tag.json') as data_file:    
            tag_payload = data_file.read()
        response = requests.put(
            'http://%s:%s/tag' %(self.server_ip, self.server_port),
            data=tag_payload,
            headers = {'content-type': 'application/json'})
        # Clusters should be added successfully.
        self.assertEqual(response.status_code, 200)
    # end testAddTagRestApi

    # Test case to test tag get REST API call, after 2 tags are added to the DB.
    def testGetTagAllRestApi(self):
        response = requests.get('http://%s:%s/tag' %(self.server_ip, self.server_port))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 7)
        tag_vals=[response.json()[each_tag] for each_tag in response.json()]
        for tag_val in tag_vals:
            self.assertTrue(tag_val in ['datacenter', 'floor', 'hall', 'rack', 'user_tag', 'test_tag_1', 'test_tag_2'])
    # end testGetTagAllRestApi

    # Test case to test tag modify REST API call
    def testModifyTagRestApi(self):
        # Modify one of the tag name to a invalid tag name and check that modification fails,
        # with proper error message.
        # Modify 2 of the tag values and do a get to check modification went through fine.
        response = requests.get('http://%s:%s/tag' %(self.server_ip, self.server_port))
        self.assertEqual(response.status_code, 200)
        newdata = response.content

        newdata = newdata.replace('tag7', 'tag8')
        response = requests.put('http://%s:%s/tag' %(
            self.server_ip, self.server_port),data=newdata,headers = {'content-type': 'application/json'})
        self.assertEqual(response.status_code, 404)
        self.assertTrue('Invalid tag tag8 specified' in response.content)

        newdata = newdata.replace('tag8', 'tag7')
        newdata = newdata.replace('test_tag_2', 'test_tag_value_new')
        response = requests.put('http://%s:%s/tag' %(
            self.server_ip, self.server_port),data=newdata,headers = {'content-type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        response = requests.get('http://%s:%s/tag' %(
                self.server_ip, self.server_port))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(eval(response.content)['tag7'], 'test_tag_value_new')
    # end testModifyTagRestApi

    def testDeleteTagRestApi(self):
        # Delete a tag, confirm result of delete REST and check
        # the delete method should not be allowed on tags.
        response = requests.delete('http://%s:%s/tag' %(self.server_ip, self.server_port))
        self.assertEqual(response.status_code, 405)
        self.assertTrue('405 Method Not Allowed' in response.content)
    # end testDeleteTagRESTApi
# end class TestSMRestApi

#Create a TestSuite for the testing server manager rest api functionality
def sm_rest_api_suite():
    suite = unittest.TestSuite()
    suite.addTest(TestSMRestApi('testGetClusterEmptyRestApi'))
    suite.addTest(TestSMRestApi('testAddClusterRestApi'))
    suite.addTest(TestSMRestApi('testGetClusterAllRestApi'))
    suite.addTest(TestSMRestApi('testGetSpecificClusterRestApi'))
    suite.addTest(TestSMRestApi('testGetNonexistingClusterRestApi'))
    suite.addTest(TestSMRestApi('testModifyClusterRestApi'))
    suite.addTest(TestSMRestApi('testDeleteClusterRestApi'))
    suite.addTest(TestSMRestApi('testGetServerEmptyRestApi'))
    suite.addTest(TestSMRestApi('testAddServerRestApi'))
    suite.addTest(TestSMRestApi('testGetServerAllRestApi'))
    suite.addTest(TestSMRestApi('testGetSpecificServerRestApi'))
    suite.addTest(TestSMRestApi('testGetNonexistingServerRestApi'))
    suite.addTest(TestSMRestApi('testModifyServerRestApi'))
    suite.addTest(TestSMRestApi('testDeleteServerRestApi'))
    suite.addTest(TestSMRestApi('testGetTagEmptyRestApi'))
    suite.addTest(TestSMRestApi('testAddTagRestApi'))
    suite.addTest(TestSMRestApi('testGetTagAllRestApi'))
    suite.addTest(TestSMRestApi('testModifyTagRestApi'))
    suite.addTest(TestSMRestApi('testDeleteTagRestApi'))
    return suite

#Run the sm rest api testsuite.
if __name__ == '__main__':
    mySuite = sm_rest_api_suite()
    runner = unittest.TextTestRunner()
    runner.run(mySuite)
