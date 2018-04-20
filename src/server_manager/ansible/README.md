Provisioning Contrail Docker Containers
=======================================

### 1. Introduction

This document describes the changes that are needed in the Server Manager module in order to support the provisioning of Contrail services that will be distributed as docker containers in version 4.0. It also serves as a user-guide that describes the procedure to provision a node with a particular contrail role running the appropriate service in a docker container.

### 2. Problem Statement

### 3. Proposed Solution

## 3.1 Alternatives Considered

## 3.2 API schema Changes

## 3.3 User Workflow Impact

## 3.4 UI Changes

## 3.5 Operations and Notification Impact

### 4. Implementation

## 4.1 Assignee(s)

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
        containers
    *   launch the containers
7.  The logs for the actual playbook run can be found in the existing
    /var/log/contrail-server-manager/debug.log file


### 5. Performance and Scaling Impact

## 5.1 API and Control Plane

## 5.2 Forwarding Performance

### 6. Upgrade

### 7. Deprecations

### 8. Dependencies

### 9. Testing
