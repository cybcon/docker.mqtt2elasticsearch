FROM alpine:3.21.0

LABEL maintainer="Michael Oberdorf IT-Consulting <info@oberdorf-itc.de>"
LABEL site.local.program.version="1.1.1"

ENV CONFIG_FILE=/app/etc/mqtt2elasticsearch.json \
    ELASTICSEARCH_MAPPING_FILE=/app/etc/mqtt2elasticsearch-mappings.json

COPY --chown=root:root /src /

RUN apk upgrade --available --no-cache --update \
    && apk add --no-cache --update \
       python3=3.12.8-r1 \
       py3-pip=24.3.1-r0 \
    && pip3 install --no-cache-dir -r /requirements.txt --break-system-packages

USER 6352:6352

WORKDIR /app/bin

# Start Process
ENTRYPOINT ["python"]
CMD ["-u", "/app/bin/mqtt2elasticsearch.py"]
