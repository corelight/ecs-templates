#!/bin/bash

# Check if two arguments are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 path_to_env_file path_to_target_file output_file"
    echo "Example: $0 example_env_file.env example_file_to_modify.conf"
    exit 1
fi

ENV_FILE="$1"
TARGET_FILE="$2"
TEMP_FILE="temp.txt"

# Load the environment variables from the provided file
set -a
source <(cat $ENV_FILE |  sed -e '/^#/d;/^\s*$/d' -e "s/'/'\\\''/g" -e "s/=\(.*\)/='\1'/g")
set +a

# Replace the environment variables in the target file
# Output the results to temp.txt
while IFS= read -r line; do
    # Only modify lines that have the pattern
    if [[ $line == *'${'*'}'* ]]; then
        # Extract the variable name from the placeholder
        variable_name=$(echo $line | grep -oP '\$\{\K[^}]+' | tr -d '{}')

        # Check if the variable exists in the environment file
        if [ ! -z "${!variable_name}" ]; then
            # If it exists, replace the placeholder with its value and uncomment the line
            replaced_line=$(eval "echo \"$line\"")
            uncommented_line=$(echo "$replaced_line" | sed 's/^\(\s*\)#/\1/')
            echo "$uncommented_line"
        else
            # If the variable was not found, print the original line without modification
            echo "$line"
        fi
    else
        echo "$line"
    fi
done < "$TARGET_FILE" > $TEMP_FILE

# Move the temp file to the target file to overwrite it with the changes
#mv $TEMP_FILE "$OUTPUT_FILE"
