#!/usr/bin/python
import argparse
import ast
import atexit
import getpass
import json
import os
import re
import requests
import shlex
import subprocess
import sys
import time
import uuid

from docker import Client

OVN_REMOTE = ""
OVN_BRIDGE = "br-int"


def call_popen(cmd):
    child = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    output = child.communicate()
    if child.returncode:
        raise RuntimeError("Fatal error executing %s" % (cmd))
    if len(output) == 0 or output[0] == None:
        output = ""
    else:
        output = output[0].strip()
    return output


def call_prog(prog, args_list):
    cmd = [prog, "--timeout=5", "-vconsole:off"] + args_list
    return call_popen(cmd)


def ovs_vsctl(args):
    return call_prog("ovs-vsctl", shlex.split(args))


def ovn_nbctl(args):
    args_list = shlex.split(args)
    database_option = "%s=%s" % ("--db", OVN_REMOTE)
    args_list.insert(0, database_option)
    return call_prog("ovn-nbctl", args_list)


def plugin_init(args):
    pass


def get_annotations(pod_name, namespace):
    api_server = ovs_vsctl("--if-exists get open_vswitch . "
                           "external-ids:api_server").strip('"')
    if not api_server:
        return None

    url = "http://%s/api/v1/pods" % (api_server)
    response = requests.get("http://0.0.0.0:8080/api/v1/pods")
    if response:
        pods = response.json()['items']
    else:
        return None

    for pod in pods:
        if (pod['metadata']['namespace'] == namespace and
           pod['metadata']['name'] == pod_name):
            annotations = pod['metadata'].get('annotations', "")
            if annotations:
                return annotations
            else:
                return None


def get_pod(pod_name, namespace):
    api_server = ovs_vsctl("--if-exists get open_vswitch . "
                           "external-ids:api_server").strip('"')
    if not api_server:
        return None

    url = "http://%s/api/v1/namepsaces/%s/pods/%s" % (api_server, namespace,
            pod_name)
    response = requests.get(url)
    if response:
        return response.json()
    else:
        return None


def associate_security_group(lport_id, security_group_id):
    pass


def get_ovn_remote():
    try:
        global OVN_REMOTE
        OVN_REMOTE = ovs_vsctl("get Open_vSwitch . "
                               "external_ids:ovn-remote").strip('"')
    except Exception as e:
        error = "failed to fetch ovn-remote (%s)" % (str(e))


def plugin_setup(args):
    ns = args.k8_args[0]
    pod_name = args.k8_args[1]
    container_id = args.k8_args[2]

    command = "docker network connect di %s" % (conatiner_id)
    try:
        call_popen(shlex.split(command))
    except Exception as e:
        error = "Failed to connect to lswitch (%s)" % (str(e),)
        sys.stderr.write(error)


def plugin_status(args):
    ns = args.k8_args[0]
    pod_name = args.k8_args[1]
    container_id = args.k8_args[2]

    veth_outside = container_id[0:15]
    ip_address = ovs_vsctl("--if-exists get interface %s "
                           "external_ids:ip_address"
                           % (veth_outside)).strip('"')
    if ip_address:
        style = {"ip": ip_address}
        print json.dumps(style)


def disassociate_security_group(lport_id):
    pass


def plugin_teardown(args):
    ns = args.k8_args[0]
    pod_name = args.k8_args[1]
    container_id = args.k8_args[2]

    command = "docker network disconnect di %s" % (conatiner_id)
    try:
        call_popen(shlex.split(command))
    except Exception as e:
        error = "Failed to connect to lswitch (%s)" % (str(e),)
        sys.stderr.write(error)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='Subcommands',
                                       dest='command_name')

    # Parser for sub-command init
    parser_plugin_init = subparsers.add_parser('init', help="kubectl init")
    parser_plugin_init.set_defaults(func=plugin_init)

    # Parser for sub-command setup
    parser_plugin_setup = subparsers.add_parser('setup',
                                                help="setup pod networking")
    parser_plugin_setup.add_argument('k8_args', nargs=3,
                                     help='arguments passed by kubectl')
    parser_plugin_setup.set_defaults(func=plugin_setup)

    # Parser for sub-command status
    parser_plugin_status = subparsers.add_parser('status',
                                                 help="pod status")
    parser_plugin_status.add_argument('k8_args', nargs=3,
                                      help='arguments passed by kubectl')
    parser_plugin_status.set_defaults(func=plugin_status)

    # Parser for sub-command teardown
    parser_plugin_teardown = subparsers.add_parser('teardown',
                                                   help="pod teardown")
    parser_plugin_teardown.add_argument('k8_args', nargs=3,
                                        help='arguments passed by kubectl')
    parser_plugin_teardown.set_defaults(func=plugin_teardown)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
