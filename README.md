# ftpsync
FTP folder synchronizer

How to run
Create a working directory and copy the config file there ftpsyncd.conf
mkdir -p /opt/ftpsync


Build image
docker rm ftpsync
docker build -t ftpsync .

Run container
docker run -d --name ftpsync -v /opt/ftpsync:/volume ftpsync


Troubleshooting
docker run -i -t -v /opt/ftpsync:/volume ftpsync /bin/bash
cd /volume
python /opt/ftpsync/ftpsyncd.py

docker exec -t -i ftpsync /bin/bash