#!/usr/bin/env bash

LCP_HOME="${LCP_HOME:-$PWD/.lcp}"
INPUT="./test/samples/sample.epub"
CONTENT_ID=00000000-0000-4000-8000-000000000001

lcpencrypt \
  -input "$INPUT" \
  -uuid "$CONTENT_ID" \
  -storage "$LCP_HOME/files/storage" \
  -url "http://localhost:8989/resources" \
  -lcpsv "http://admin:admin@localhost:8989" \
  -verbose

curl -fsS -u admin:admin "http://localhost:8989/publications/$CONTENT_ID" | jq .
