Provisioning Contrail Docker Containers
=======================================

### 1. Introduction

This document describes the changes that are needed in the Server Manager module in order to support the provisioning of Contrail services that will be distributed as docker containers in version 4.0. It also serves as a user-guide that describes the procedure to provision a node with a particular contrail role running the appropriate service in a docker container.

### 2. Problem Statement

The rationale behind the decision to containerize the contrail subsystems can be found [here]( https://github.com/Juniper/contrail-docker/blob/master/specs/contrail-docker.md). The Contrail Serveer Manager in its current form has no support for deploying and configuring these new Contrail docker containers and so users wishing to provision the containers using the Server Manager module will not be able to.

### 3. Proposed Solution

Server Manager module needs to be augmented with the ability to deploy the contrail containers using the existing Server Manager workflow.

## 3.1 Alternatives Considered

Use the existing framework of puppet/cobbler to provision the new containers. This approach was dropped in an effort to move away from the puppet framework in favor of the agent-less architecture of Ansible. Another rationale that favored the use of Ansible is that Ansible scripts are being used to build the docker containers themselves and these scripts could be re-used to provision them as well.

## 3.2 API schema Changes

None.

## 3.3 User Workflow Impact

There is no impact to the existing Server Manage workflow except that in place of adding the contrail packages during the "add image" phase, contrail docker containers will be used in the JSON files describing the image being added. Refer to section 4.2 for details.

## 3.4 UI Changes

TODO

## 3.5 Operations and Notification Impact

### 4. Implementation

## 4.1 Assignee(s)

Ramprakash

## 4.2 Work Items

### Modifications needed to the existing server-manager code to support 
### provisioning of contrail containers:
1.  Ansible playbook scripts needed to provision the relevant containers are 
    added in the contrail-server-manager/src/ansible/playbooks directory
2.  The existing workflow of using server-manager to provision a node is not 
    disturbed in any way:
    *   server-manager add image
    *   server-manager add server 
    *   server-manager provision
    
    The difference here is that during the "add image", if the "category" of the
    image is "container", then the image gets pushed into the docker registry
    (configured in the global server-manager configuration) in the following
    format :
    
            `<image_id>-<image_type>-<version>`
    
                |            |          |--- e.g: liberty:3.1.1.0-29
                |            |          
                |            |--- e.g: controller, analytics, agent - based on 
                |                      roles
                |--- e.g: contrail-container
                
    By default, the docker registry will be run on the node running Server Manager. So as part of starting the 
    "contrail-server-manager service a docker registry container is also started.
3.  During the "add server", all configuration parameters needed by the
    container that will be launched on that server needs to be provided as part
    of the json configuration file
4.  Running the playbooks via python is not compatible with the existing 
    server-manager because of the use of gevent library in the existing server-
    manager codebase (Refer [Gevent docs] (http://www.gevent.org/whatsnew_1_2.html#compatibility)) for details. 
    This is because ansible code uses multiprocessing.Queue module and this 
    module is incompatibe with gevent greenlets. To work around this limitation
    and also to keep the ansible playbook module modular, it has been decided 
    to run the module as a separate server that exposes the following REST APIs:
    *   server\_ip:9003/run\_playbook
    *   server\_ip:9003/playbook\_status
5.  These REST APIs are used by the server-manager during the provision phase to
    run the relevant playbook and to get the status for a previous playbook run
6.  The playbook does the following tasks:
    *   create a single configuration file on the server being provisioned in
        the /etc/contrail/<role_name>.conf
        a sample config file can be found [here]
        (https://github.com/Juniper/contrail-docker/blob/master/tools/python-contrailctl/examples/configs/controller.conf)
    *   create mount points for logs, persistent databases if required for the
        containers. Currently "/var/log/contrail" directory on the host is being mounted as "/var/log" of the container.
    *   launch the containers
7.  The logs for the actual playbook run can be found in the existing
    /var/log/contrail-server-manager/debug.log file
8.  The logs of the contrail services running inside the containers can be monitored from the Server Manager using the newly introduced command:

        server-manager display logs --server_id <server_id> [--file_name <file_name>]
        
    Without the "--file_name" option, the command lists the log files found in /var/log/contrail directory of the target node.
    And then the user can view the contents of any one of the log files by using the file name in the "--file_name" option.


### 5. Performance and Scaling Impact

## 5.1 API and Control Plane

## 5.2 Forwarding Performance

### 6. Upgrade

### 7. Deprecations

### 8. Dependencies

This new feature needs to run a docker registry on the node running the Server Manager module. In order to facilitate this and to push the docker containers into the registry, the following packages need to be installed along with the "contrail-server-manager" package:
    1. docker-engine : currently uses docker-engine_1.12.3-0~trusty_amd64.deb from the get.docker.com repository.
    2. ansible : currently uses ansible_2.2.0.0-1ppa~trusty_all.deb from the official Ansible trusty repository.
    2. The following package from the pypi python package repository and its dependencies:
            docker-py-1.9.0rc2.tar.gz.1
    
The "docker-py" and the "docker-engine" packages also need to be run on all the target nodes provisioned using Server Manager and for this reason, these packages will have to be exported as part of the contrail-third-party repository that Server Manager has. 
            
### 9. Testing
1.  All existing provisioning sanity tests.
2.  Provisioning contrail container roles alongside non-containerized nodes.
3.  Running multiple containers in the same node to check for possible race conditions/deadlocks in the ansible scripts.
4.  Ensure the configuration parameters are propogated correctly to the contrail services running in the containers - both using the cluster jsons and overriding the cluster jsons using the server jsons.

### 10. Documentation Impact
