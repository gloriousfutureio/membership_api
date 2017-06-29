FROM alpine:3.6

LABEL maintainer "jeff.n.may@gmail.com"

WORKDIR /usr/src/app

RUN apk add --no-cache \
        build-base \
        mariadb-dev \
        python3 \
        python3-dev

# Requires running with the context from root:
#     docker build . -f path/to/this/Dockerfile

ADD requirements.txt ./

RUN pip3 install --no-cache-dir -r requirements.txt

ADD config ./config
ADD membership ./membership
ADD flask_app.py ./

EXPOSE 8080

ENTRYPOINT ["python3", "flask_app.py"]
