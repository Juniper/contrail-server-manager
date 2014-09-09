contrail-server-manager
=======================

# contrail server management

This software is licensed under the Apache License, Version 2.0 (the "License");
you may not use this software except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

### Overview

Contrail Server Manager repo contains code that facilitates management of servers in a contrail cluster. It provides functions to install base OS on servers (reimaging), and configuring the servers by installing necessary packages, configuring and starting different services needed to provide a contrail role functionality on these servers (provisioning). Contrail server manager uses other widely deployed tools such as cobbler and puppet to accomplish the task of reimaging and provisioning.

Summary, server manager includes Openstack and Contrail installation and provisioning and lifecycle management of each node in a contrail cluster. More details on this feature is described here. http://juni.pr/1nHLtCB.
