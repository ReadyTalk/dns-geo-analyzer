#!/usr/bin/env python3

import socket
import os
import dns.resolver
import json
import requests
from elasticsearch import Elasticsearch
from prometheus_client import start_http_server, Summary, Counter
import random
import time
import datetime

INTERVAL=60
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing DNS requests')
DNS_REQUESTS = Counter('dns_requests_total', 'Total DNS Requests')

@REQUEST_TIME.time()
def query_nameserver(nameserver, name):
    resolver = dns.resolver.Resolver()
    resolver.nameservers=[nameserver]
    for rdata in resolver.query(name, 'A'):
        DNS_REQUESTS.inc()
        return(rdata)


def get_external_ip():
    r = requests.get('http://whatismyip.akamai.com')
    return r.text


def get_geo(ip_addr):
    r = requests.get('http://api.ipstack.com/{0}?access_key={1}'.format(ip_addr, IPSTACK_API_KEY))
    geo = json.loads(r.text)
    geo.pop('location')
    return geo


def send_to_es(json_dict):
    ES.index(index = ES_INDEX, body=str(json_dict), doc_type='test')


def construct_record():
    record = {}
    record['date'] = str(datetime.datetime.now())
    local_ip = get_external_ip()
    record['local'] = {}
    record['local']['ip'] = str(local_ip)

    try:
        record['local']['geo_data'] = get_geo(local_ip)
    except NameError:
        pass # This feature was not enabled

    record['dns_data'] = test_dns(NAMESERVERS, SITES)
    return record


def test_dns(nameservers, queries):
    dns_data = {}
    for server in nameservers:
        dns_data[server[0]] = {}
        for query in queries:
            ip = query_nameserver(server[1], query[1])
            dns_data[server[0]][query[0]] = {}
            dns_data[server[0]][query[0]]['ip'] = str(ip)
            try:
                dns_data[server[0]][query[0]]['geo_data'] = get_geo(ip)
            except NameError:
                pass # Geolocation not enabled

    return dns_data

if __name__ == '__main__':
    """ Get all the environment config and run it """


    # Check for the basic configuration.  If not present, exit
    try:
        INIT_NAMESERVERS = os.environ['NAMESERVERS'].split(" ")
        INIT_SITES = os.environ['SITES'].split(" ")
    except KeyError:
        print("You need to configure all the variables.  Please check the README")
        sys.exit(1)

    # Parse the new nameserver lists
    NAMESERVERS = []
    for server in INIT_NAMESERVERS:
        NAMESERVERS.append(server.split(","))

    # Parse the sites list too
    SITES = []
    for site in INIT_SITES:
        SITES.append(site.split(","))

    # If the port is set, the enable the prometheus endpoint
    try:
        PROMETHEUS_PORT = int(os.environ['PROMETHEUS_PORT'])
    except KeyError:
        print("Prometheus endpoint disabled")
    else:
        start_http_server(PROMETHEUS_PORT)

    # Check for an API token for ipstack
    try:
        IPSTACK_API_KEY = os.environ['IPSTACK_API_KEY']
    except KeyError:
        print("You have not set an IPSTACK API endpoint.  Geolocation of IPs will not be performed")

    # Check if elasticsearch exporting is enabled.
    try:
        ES_ENDPOINT = os.environ['ES_ENDPOINT']
        ES_INDEX = os.environ['ES_INDEX']
    except KeyError:
        ES_ENABLED = False
        print("ES Variables not set, ES will not be used")
    else:
        print("Elasticsearch enabled, data will be sent")
        ES = Elasticsearch([ES_ENDPOINT])
        ES_ENABLED = True

    # Start the program loop
    while True:

        final_json = json.dumps(construct_record(), indent=4, sort_keys=True )

        if ES_ENABLED:
            send_to_es(final_json)

        # Print the result no matter what
        print(final_json)
        time.sleep(INTERVAL)
