Provisioning Contrail Docker Containers
=======================================

### 1. Introduction

Contrail 4.0 would provide support for Docker containers. The existing contrail components, which run as services on a BMS or VM, would be running within a Docker container in contrail 4.0. 
This document describes the changes in the Server Manager module in order to support the provisioning of contrail 4.0 Docker containers, which would be running the several contrail service components.

### 2. Problem Statement

The rationale behind the decision to containerize the contrail subsystems can be found [here]( https://github.com/Juniper/contrail-docker/blob/master/specs/contrail-docker.md). Contrail Server Manager 3.x or earlier provides functionality to provision different components or roles of contrail running as services or processes on a BMS or VM. With contrail 4.0, the contrail services would be contained in Docker containers. This necessitates change in contrail server manager to support the new mode of contrail deployment and support provisioning of these contrail Docker containers.

### 3. Proposed Solution

Contrail Docker containers will be built to include all the packages needed to run the processes within the container. Also included in the containers will be Ansible playbooks to create the configuration files and provision the services within the container. Any provisioning tool to deploy these containers, including server manager, will need to perform 2 simple steps:

       1.   Create a configuration file containing parameter values, one config file per container.
       2.   Deploy the container.

When deployed the container will pick the configuration parameters and execute ansible scripts within the container to provision and bring up processes within the container.


## 3.1 Alternatives Considered

Server Manager 3.x and earlier makes use of puppet manifests to provision contrail services on target systems. Using the existing framework of puppet to provision the new containers was considered as an alternative. It was dropped for couple of reasons:

    1. Puppet manifests tend to be rigid to accommodate changes needed in provisioning. Each new feature implemented in contrail makes puppet manifests more complex. Also puppet needs an agent running on target systems.

    2. Provisioning logic for the contrail components and processes goes hand-in-hand with the contrail code. It is easier to maintain and extend the provisioning logic with changes in contrail, if the actual provisioning is maintained within container along with rest of the code. Hence Ansible playbooks to provision different processes in the container are included in the container at build time. With this approach any external entity such as Server Manager would require minimal changes to support changes and new features in contrail.

## 3.2 API schema Changes

None.

## 3.3 User Workflow Impact

Today to provision contrail cluster from server manager user needs to perform following steps:

    1.  Add cluster with cluster provisioning parameters
    2.  Add server(s) with server(s) provisioning parameters
    3.  Add image with image provisioning parameters
    4.  Provision servers

This workflow for provisioning contrail cluster will remain unchanged with changes to support Docker containers. Only internally some things are done differently.

    1.  When image is added, today a package repo mirror is created on server manager meeting. Instead for Docker container, we will add the container to either local or remote Docker registry from where the container image will be picked at the time of deploying.
    2.  When provisioning servers, today puppet master on server manager provides the puppet manifests catalog to the targets to execute. The manifests have all the logic to create necessary config files etc. For Docker container, provisioning logic in server manager will create configuration file for the container and deploy container from registry.


## 3.4 UI Changes

TODO : There would be changes needed to specify containers (instead of roles) running on a BMS or VM. Also there would be changes to the provisioning parameters are required by containers.


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

Server Manager REST API interface will remain unchanged to support Docker containers. 

## 5.2 Forwarding Performance

### 6. Upgrade

TBD

### 7. Deprecations

Existing support to deploy contrail services on BMS or VM (non-containerized) will be deprecated once we have docker container support.

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
