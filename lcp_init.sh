#!/usr/bin/env bash

# test/config.yaml のパスはリポジトリのルートからの相対パス
cd "$(dirname "$0")"

mkdir -p .lcp/{db,files/storage}

export LCPSERVER_CONFIG="$PWD/test/config.yaml"
exec lcpserver
