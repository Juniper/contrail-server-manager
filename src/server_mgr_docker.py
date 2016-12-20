import os
from docker import Client
from server_mgr_err import *
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger

class SM_Docker():
    '''
    This class deals with all things docker that server manager needs
    '''

    _docker_client = None

    def __init__(self):
        self._docker_client = Client()
        self._smgr_log      = ServerMgrlogger()

    def new_image(self, pre, post):
        found = False
        for x in post:
            found = False
            new_id = x['Id']
            for y in pre:
                if x['Id'] == y['Id']:
                    found = True
                    break
            if found == False:
                return x
        if found == True:
            return None

    def load_containers(self, image):
        try:
            pre = self._docker_client.images()

            f = open(image, 'r')
            self._docker_client.load_image(f)
            msg = "docker loaded image %s" % (image)
            self._smgr_log.log(self._smgr_log.INFO, msg)
            f.close()

            post = self._docker_client.images()
            return [True, self.new_image(pre, post)]
        except Exception as e:
            msg = "docker load failed for image %s: %s" % (image, e)
            self._smgr_log.log(self._smgr_log.INFO, msg)                           
            return [False, None]
            

    def tag_containers(self, image, repo, tag):
        return self._docker_client.tag(image, repo, tag)

    def push_containers(self, image):
        try:                                                                    
            stream = self._docker_client.push(image, stream=True)
            for line in stream:
                self._smgr_log.log(self._smgr_log.INFO, line)                           
        except Exception as e:
            msg = "docker push failed for image %s: %s" % (image, e)
            #raise ServerMgrException(msg, ERR_OPR_ERROR)                        
            self._smgr_log.log(self._smgr_log.INFO, msg)                           

###############################################################################
