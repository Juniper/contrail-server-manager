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

    def remove_containers(self, image):
        return self._docker_client.remove_image(image, force=True)

    def push_containers(self, image):
        try:
            stream = self._docker_client.push(image, stream=True)
        except Exception as e:
            msg = "docker push failed for image %s: %s" % (image, e)
            #raise ServerMgrException(msg, ERR_OPR_ERROR)
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            return False

        progress = 0
        for line in stream:
            if "connection refused" in line:
                msg = "docker push failed for image %s: %s" % (image, line)
                self._smgr_log.log(self._smgr_log.ERROR, msg)
                return False

            s = eval(line)
            #NOTE: example line is:
            # {"status":"Pushing","progressDetail":{"current":1536,
            #  "total":2913},"progress":"[====\u003e # ]
            # If docker python API changes the format of this, the next
            # assignment will be broken.
            try:
                current = s['progressDetail']['current']
                total   = s['progressDetail']['total']
                cur_progress = int(round((float(current)/float(total))*100))
                # Log every 20% of progress
                if (cur_progress >= progress + 20):
                    progress = cur_progress
                    self._smgr_log.log(self._smgr_log.INFO, line)
            except KeyError:
                #self._smgr_log.log(self._smgr_log.DEBUG, line)
                continue

###############################################################################
