# DNS Resolver Testing

The intent of this script and docker file is to test geo-location of DNS resolution.  Many providers do this in different ways, and we need to be able to test that data.

# Usage

## Local

Set your ENV.  You can provide a `<environment>.env` file and pass that to the run_test.sh script:

```
./run_test.sh example
```

This will run the docker container, but mount the script to it from local for testing

## Docker

You can run this anywhere using docker.  Just pass an env file or set the following ENV

```
export NAMESERVERS=google,8.8.8.8 cloudflare,1.1.1.1 opendns,208.67.222.222
export SITES=google,google.com

docker run --rm -itd --name resolver --env-file example.env readytalk/resolver
```

Note the nameserver and sites have the format <shortname>,<dns/ip>.  This is to avoid having dots in the metric names for ES

## Options

### IP Geolocation

You can enable this by setting the IPSTACK_API_KEY env variable.  This will use your api key to lookup geolocation data.

WARNING: This will use up your API calls.  Don't make too many

### Elasticsearch

Set the ES_ENDPOINT and ES_INDEX to send these json objects to elasticsearch.  Currently uses ES version 5.0, but could easily work with 6.0 by modifying the requirements.txt

## NOTES

The format of the ENV is very specific.  The short names are used so that we don't have dots in the keys, which makes the data ugly in ES
