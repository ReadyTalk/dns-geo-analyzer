FROM python:alpine

# Security stuff and utils
RUN apk --update add ca-certificates wget 

# Install dumb-init
RUN wget -O /usr/local/bin/dumb-init https://github.com/Yelp/dumb-init/releases/download/v1.2.1/dumb-init_1.2.1_amd64
RUN chmod +x /usr/local/bin/dumb-init

# Install the requirements
ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

# Add the script and make executable
ADD resolver.py /resolver.py
RUN chmod +x /resolver.py

# Dumb-init the script
ENTRYPOINT ["/usr/local/bin/dumb-init", "--"]
CMD ["/resolver.py"]
