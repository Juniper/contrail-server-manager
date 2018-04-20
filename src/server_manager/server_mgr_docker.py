import os
import re
import json
import subprocess
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
        self._docker_client = Client(timeout=240)
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

    def get_image_id(self, image):
        try:
            new_img_id = {}
            tmpdir = "/tmp/contrail_docker"
            cmd = ("mkdir -p %s" % tmpdir)
            subprocess.check_call(cmd, shell=True)

            cmd = ("tar xvzf %s -C %s > /dev/null" % (image, tmpdir))
            subprocess.check_call(cmd, shell=True)

            manifest_file = tmpdir + "/manifest.json"
            if not os.path.isfile(manifest_file):
                self._smgr_log.log(self._smgr_log.ERROR,
                        "Could not determine image_id in %s" % image)
                return None
            f = open(manifest_file, 'r')
            dt = json.load(f)
            cfg = re.split(r'\.', dt[0]['Config'])
            new_img_id['Id'] = str(cfg[0])

            cmd = ("rm -rf %s" % tmpdir)
            subprocess.check_call(cmd, shell=True)
            self._smgr_log.log(self._smgr_log.DEBUG,
                        "image_id for %s is %s" % (image, new_img_id['Id']))
            return new_img_id
        except Exception as e:
            msg = "Unable to determine image_id for %s (%s)" % (image, e)
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            return None

    def load_containers(self, image):
        try:
            imageid = self.get_image_id(image)
            if imageid == None:
                return [False, None]

            f = open(image, 'r')
            self._docker_client.load_image(f)
            msg = "docker loaded image %s" % (image)
            self._smgr_log.log(self._smgr_log.INFO, msg)
            f.close()

            return [True, imageid]
        except Exception as e:
            msg = "docker load failed for image %s: %s" % (image, e)
            self._smgr_log.log(self._smgr_log.INFO, msg)
            return [False, None]


    def tag_containers(self, image, repo, tag):
        try:
            self._docker_client.tag(image, repo, tag)
            return True
        except Exception as e:
            msg = \
               "tag container failed for image %s: check image version: %s" % \
               (repo,tag)
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            return msg

    def remove_containers(self, image):
        try:
            self._docker_client.remove_image(image, force=True)
        except:
            pass

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
