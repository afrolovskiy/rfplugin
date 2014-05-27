#!/bin/bash
for ((i = 0; i < 100; i++))
do
  ./gcc-pyplugin plugin.py $@ -lpthread > /dev/null
done

