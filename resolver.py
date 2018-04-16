#!/usr/bin/env python3

import socket
import os
import sys
import dns.resolver
import json
import requests
from elasticsearch import Elasticsearch
from prometheus_client import start_http_server, Summary, Counter
import random
import time
import datetime

# Define prometheus variables
DNS_REQUEST_TIME = Summary('dnsgeo_dns_request_processing_seconds', 'Time spent processing DNS requests')
GEO_REQUEST_TIME = Summary('dnsgeo_ipstack_request_processing_seconds', 'Time spent processing Geo lookups')
GEO_REQUESTS = Counter('dnsgeo_ipstack_requests_total', 'Total geo requests to ipstack')
GEO_REQUESTS2 = Counter('dnsgeo_getcitydetails_requests_total', 'Total requests to getcitydetails')

DNS_REQUESTS = Counter('dnsgeo_dns_requests_total', 'Total DNS Requests')
DNS_GEO_DATA = Counter('dnsgeo_dns_location', 'DNS Data from resolver', ['ip', 'nameserver', 'nameserver_ip', 'site_shortname', 'site', 'region_code', 'region_name', 'zip'])
DNS_BASE_DATA = Counter('dnsgeo_dns_resolution', 'DNS Data without geolocation', ['ip', 'nameserver', 'nameserver_ip', 'site_shortname', 'site'])
LOCAL_IP_DATA = Counter('dnsgeo_local_data', 'Local IP DNS Data', ['ip', 'region_code', 'region_name', 'zip'])

@DNS_REQUEST_TIME.time()
def query_nameserver(nameserver, name):
    """
    Do a DNS query against a specified  nameserver
    """
    resolver = dns.resolver.Resolver()
    resolver.nameservers=[nameserver]
    for rdata in resolver.query(name, 'A'):
        DNS_REQUESTS.inc()
        return(rdata)


def get_external_ip():
    """
    Get my current externally-visible IP
    """
    r = requests.get('http://whatismyip.akamai.com')
    return r.text


@GEO_REQUEST_TIME.time()
def get_geo(ip_addr):
    """
    Query the ipstack API for geoloaction details
    """
    r = requests.get('http://api.ipstack.com/{0}?access_key={1}'.format(ip_addr, IPSTACK_API_KEY))
    geo = json.loads(r.text)
    geo.pop('location')
    GEO_REQUESTS.inc()
    return geo


def get_geo2(ip_addr):
    """ 
    An attempt at using getcitydetails instead of the ipstack API
    The accuracy appears to be terrible
    """
    r = requests.get('http://getcitydetails.geobytes.com/GetCityDetails?callback=?&fqcn={0}'.format(ip_addr))
    rjson = r.text[ r.text.index("(") + 1 : r.text.rindex(")") ]
    geo = json.loads(rjson)
    GEO_REQUESTS2.inc()
    return geo

def send_to_es(json_dict):
    """
    Send a dict as json to an Elasticsearch Index
    """
    ES.index(index = ES_INDEX, body=str(json_dict), doc_type='test')


def construct_record():
    """
    Build a json dict of a bunch of DNS data
    """
    record = {}
    record['date'] = str(datetime.datetime.now())
    local_ip = get_external_ip()
    record['local'] = {}
    record['local']['ip'] = str(local_ip)

    # For testing the new geo2 function
    # print(json.dumps(get_geo2(local_ip), indent=4, sort_keys=True))

    try:
        record['local']['geo_data'] = get_geo(local_ip)
    except NameError:
        pass # This feature was not enabled
    else:
        local_region_code = record['local']['geo_data']['region_code']
        local_region_name = record['local']['geo_data']['region_name']
        local_zip = record['local']['geo_data']['zip']
        LOCAL_IP_DATA.labels(local_ip, local_region_code, local_region_name, local_zip).inc()

    record['dns_data'] = test_dns(NAMESERVERS, SITES)

    return record


def test_dns(nameservers, queries):
    """
    Get some dns info using a list of nameservers and sites
    """
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
            else:
                # Prometheus
                #DNS_DATA = Counter('dnsgeo_dns_locations', 'DNS Data from resolver', ['ip', 'nameserver', 'nameserver_ip', 'site_shortname', 'site', 'region_code', 'region_name', 'zip'])
                region_code = dns_data[server[0]][query[0]]['geo_data']['region_code']
                region_name = dns_data[server[0]][query[0]]['geo_data']['region_name']
                zipcode = dns_data[server[0]][query[0]]['geo_data']['zip']
                DNS_GEO_DATA.labels(ip, server[0], server[1], query[0], query[1], region_code, region_name, zipcode).inc()
            DNS_BASE_DATA.labels(ip, server[0], server[1], query[0], query[1]).inc()


    return dns_data

if __name__ == '__main__':
    """ Get all the environment config and run it """

    # Check for the basic configuration.  If not present, exit
    try:
        INIT_NAMESERVERS = os.environ['NAMESERVERS'].split(" ")
        INIT_SITES = os.environ['SITES'].split(" ")
        REQUEST_INTERVAL = int(os.environ['REQUEST_INTERVAL'])
    except KeyError:
        print("You need to configure all the variables.  Please check the README, exiting...")
        sys.exit(1)
    except ValueError:
        print("REQUEST_INTERVAL must be an integer, exiting...")
        sys.exit(2)

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
    except ValueError:
        print("PROMETHEUS_PORT must be an integer, disabling Prometheus endpoint")
    else:
        print("Prometheus endpoint server starting on port {0}".format(PROMETHEUS_PORT))
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
        time.sleep(REQUEST_INTERVAL)
