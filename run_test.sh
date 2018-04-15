docker run --rm --name dns-geo-analyzer --env-file $1.env -v $(pwd)/resolver.py:/resolver.py readytalk/dns-geo-analyzer:latest
