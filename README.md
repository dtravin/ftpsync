#FTP folder synchronizer

##Local development
Install dependencies
```
apt-get install -y python-setuptools python-pip
pip install -r requirements.txt
```
Run tests
```
git clone https://github.com/dtravin/ftpsync.git
python test.py
```

###Dockerize
Create a working directory and copy the config file there ftpsyncd.conf
```
mkdir -p /opt/ftpsync
cp -rf ftpsyncd.conf /opt/ftpsync
```

Build docker image
```
docker rm ftpsync
docker build -t ftpsync .
```
Run container
```
docker run -d --name ftpsync -v /opt/ftpsync:/volume ftpsync
```

Watch the logs
```
docker exec -t -i ftpsync /bin/bash
tail -f /var/log/ftpsyncd*
```

Troubleshooting
```
docker run -i -t -v /opt/ftpsync:/volume ftpsync /bin/bash
cd /volume
python /opt/ftpsync/ftpsyncd.py

```