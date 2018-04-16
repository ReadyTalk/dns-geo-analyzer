docker rm -f dns-geo-analyzer
docker run -itd -p 8000:8000 --name dns-geo-analyzer --env-file $1.env -v $(pwd)/resolver.py:/resolver.py readytalk/dns-geo-analyzer:prometheus
