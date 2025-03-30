#!/bin/bash

# Print received arguments
echo "Received arguments:"
echo "Load Names:"
for arg in "$@"; do
    echo "$arg"
done

# Add your processing logic here
# This is just a sample that prints the arguments
echo "Processing batch with the following parameters:"
echo "Load Names: $1"
echo "Organisms: $2"
echo "Library Prep Methods: $3" 