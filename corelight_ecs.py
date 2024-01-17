#!/usr/bin/env python3
# -*- coding: utf-8 -*-
try:
    import logging
    import shutil
    import requests
    import time
    import sys
    import zipfile
    import os
    import random
    import getpass
    import errno
    import re
    import json
    from urllib.parse import urlparse
    import urllib3
    from urllib3.exceptions import InsecureRequestWarning, HTTPError
    import argparse
    from pathlib import Path, PurePath
except IndexError as error:
    print (error)
    print ('Unable to load python module... Exiting Script!')
    sys.exit(1)

# Default Variables
script_version = '2024010301'
script_repo = 'https://github.com/corelight/ecs-templates/tree/main'
f'\nVersion: {script_version}'
git_repository = "corelight"
git_branch = "main"
git_url_base_domain_and_schema = "https://github.com"
git_logstash_repo_name = f'ecs-logstash-mappings'
git_templates_repo_name = f'ecs-templates'
git_ingest_repo_name = f'ecs-mapping'
ls_output_filename = "9940-elasticsearch-corelight_zeek-output.conf"
es_default_timeout = 10
es_default_retry = 2
logstash_input_choices = [ 'tcp', 'tcp_ssl', 'kafka', 'hec', 'udp' ]
git_logstash_repo = f'{git_url_base_domain_and_schema}/{git_repository}/{git_logstash_repo_name}/archive/refs/heads/{git_branch}.zip'
git_logstash_sub_dir = "pipeline"
git_ingest_repo = f'{git_url_base_domain_and_schema}/{git_repository}/{git_ingest_repo_name}/archive/refs/heads/{git_branch}.zip'
git_ingest_sub_dir = "pipeline"
git_templates_repo = f'{git_url_base_domain_and_schema}/{git_repository}/{git_templates_repo_name}/archive/refs/heads/{git_branch}.zip'
git_templates_sub_dir = "templates"
script_description = f'''
Script that builds everything necessary to convert Corelight or Zeek Logs into the Elastic Common Schema (ECS) naming standard and store them into an Elastic Stack deployment.
The repository for this script can be found here: {script_repo}
Version: {script_version}
'''

# General
#version = script_version
time_now = time.time() # Get the current time
dir_time = time.strftime( '%Y-%m-%d_%H%M%S', time.gmtime( time_now ) )
script_name = os.path.basename( __file__ )
script_dir = os.path.realpath( os.path.join( __file__, '..' ) )
Script_UID = str( random.randint( 1000000000, 9999999999 ) )  # Random 10 digit number for correlating a specific run of the script to the logs.
# Main Output Directory
Script_Output_Dir = os.path.realpath( os.path.join( script_dir, "z_installer" ) )
# Temp Output Directory
Temp_Output_Dir = os.path.join( Script_Output_Dir, "temp" )
Config_Dir = os.path.join( Script_Output_Dir, "final_config" )

COLORS = {
    'HEADER': '\033[95m',
    'OKBLUE': '\033[94m',
    'OKCYAN': '\033[96m',
    'OKGREEN': '\033[92m',
    'WARNING': '\033[93m',
    'FAIL': '\033[91m',
    'ENDC': '\033[0m',
    'BOLD': '\033[1m',
    'UNDERLINE': '\033[4m'
}
LOG_COLORS = {
    'DEBUG': COLORS[ 'OKCYAN' ],
    'INFO': COLORS[ 'OKGREEN' ],
    'WARNING': COLORS[ 'WARNING' ],
    'ERROR': COLORS[ 'FAIL' ],
    'CRITICAL': COLORS[ 'BOLD' ] + COLORS[ 'FAIL' ]
}

# Create the output directories if they don't exist
try:
    os.makedirs( Script_Output_Dir )
except OSError as e:
    if e.errno != errno.EEXIST:
        raise
try:
    os.makedirs( Temp_Output_Dir )
except OSError as e:
    if e.errno != errno.EEXIST:
        raise


logger = logging.getLogger(__name__)

def arg_path_and_exists(path):
    path = Path(path)
    if Path.is_dir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f'"{path}" does not exist or is not a directory')
def arg_file_and_exists(path):
    path = Path(path)
    if Path.is_file():
        return path
    else:
        raise argparse.ArgumentTypeError(f'"{path}" does not exist or is not a file')

def input_bool(question, default=None):
    prompt = " [Y/n]:" if default else " [y/N]:"
    while True:
        val = input(f"\n{question}{prompt}").strip().lower()
        if not val:
            return default
        if val in ('y', 'yes'):
            return True
        if val in ('n', 'no'):
            return False
        logger.warning("Invalid response")

def input_string(question=None, default=None):
    val = None
    if question:
        val = input(f"\n{question}. Default: '{default}': ")
        if not val:
            return default
        else:
            val = val.strip()
    return val

def input_int(question, default=None):
    while True:
        try:
            val = input(f"\n{question}. Default: '{default}': ")
            if not val:
                return default
            else:
                int( val )
                return val
        except ValueError:
            logger.warning("Invalid response, please enter a number")

def check_request_status_code(responseObj, code=None, display_error=False):
    if not code:
        code = responseObj.status_code
    if code == 200:
        pass
    elif 400 <= code <= 599:
        if display_error:
            logger.error(responseObj.json())
        else:
            pass
    else:
        code = None
        logger.error(f"No status code found for {responseObj}")
    return code

def test_connection(session, baseURI):
    testUri = "/"
    uri = f'{baseURI}{testUri}'
    try:
        response = session.get(uri, timeout=5)
        check_status_code = check_request_status_code(response, display_error=False)
        response.raise_for_status()
    except requests.exceptions.SSLError as e:
        if "SSL: CERTIFICATE_VERIFY_FAILED" in str(e):
            logger.error(f"SSL Error: {e}")
            return "prompt_ignore_cert"
        else:
            raise
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logger.error(f"Authentication Error: {e}")
            return "prompt_auth"
        else:
            logger.error(f"HTTP Error: {e}")
            raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Request Error: {e}")
        raise

def es_export_to_elastic( session, baseURI, req_uri=None, req_resource_name=None, request_body=None, retry=es_default_retry, timeout=es_default_timeout, ignore_status_codes=None ):
    if ignore_status_codes is None:
        ignore_status_codes = list()
    if not req_uri:
        logger.error(f"Error: No uri path was specified for the request to Elasticsearch for '{req_resource_name}'")
        return
    uri = f'{baseURI}{req_uri}'
    if not request_body:
        logger.error(f"Error: No data was specified for the request to Elasticsearch for '{req_resource_name}' to '{uri}'")
        return
    response = None
    for i in range(retry):
        response = session.put(uri, data=request_body, timeout=timeout)
        response_code = response.status_code
        response_text = response.text
        check_status_code = check_request_status_code(response, code=response_code, display_error=False)
        if check_status_code == 200:
            logger.debug(f"{req_resource_name} uploaded successfully")
            return
        elif ignore_status_codes and check_status_code in ignore_status_codes:
            logger.debug(f"{req_resource_name} response ignored with status code '{response_code}' and response '{response_text}'")
            return
        elif check_status_code in (400, 409):
            logger.error(f"Error uploading '{req_resource_name}' to '{uri}' with status code '{response_code}' and response '{response_text}'")
        else:
            logger.error(f"Error uploading. '{req_resource_name}' to '{uri}' with status code '{response_code}' and response '{response_text}'")

def get_elasticsearch_connection_config():
    """Return a baseURI and session"""
    ignoreCertErrors = False
    use_https = False
    while True:
        baseURI = input("\nEnter the Elasticsearch host including whether http or https and the port (ie: the full URL, http://somedomain:9200 or https://someip:9200 or https://somedomain:9200)\n: ")
        if not baseURI:
            logger.warning("Cannot be empty. Please try again.")
            continue
        parsed_baseURI = urlparse( baseURI )
        # Catch common errors
        if not (baseURI.startswith("http://") or baseURI.startswith("https://") ):
            logger.warning("Must include http:// or https://. Please try again.")
            continue
        # Determine if a port was entered
        if not parsed_baseURI.port:
            logger.warning("No port was entered, please try again and specify the port even if port 443 or 80")
            continue
        break

    s = requests.Session()
    s.headers={'Content-Type': 'application/json'}

    # Prompt if user wants to ignore certificate errors if https
    if baseURI.startswith( "https://" ):
        use_https = True
        ignore_cert_errors = prompt_for_es_ignore_certificate_errors(try_again=False)
        if ignore_cert_errors:
            s.verify = False
            # Suprress SSL Warnings if not verifying SSL
            urllib3.disable_warnings(category=InsecureRequestWarning)
    else:
        #proto = "http"
        pass

    # Prompt for user and password authentication
    auth = prompt_for_es_user_and_password(try_again=False)
    if auth and auth[0] and auth[1]:
        s.auth = (auth[0], auth[1])
    else:
        pass

    # Test the connection, so can reprompt if it fails
    while True:
        reprompt = test_connection( s, baseURI )
        if reprompt == "prompt_ignore_cert":
            ignore_cert_errors = prompt_for_es_ignore_certificate_errors(try_again=True)
            if ignore_cert_errors:
                s.verify = False
                # Suprress SSL Warnings if not verifying SSL
                urllib3.disable_warnings(category=InsecureRequestWarning)
            else:
                logger.error(f"Failed to verify SSL connectivity to Elasticsearch: {baseURI}")
                sys.exit(1)
        elif reprompt == "prompt_auth":
            auth = prompt_for_es_user_and_password(try_again=True)
            if auth and auth[ 0 ] and auth[ 1 ]:
                s.auth = (auth[ 0 ], auth[ 1 ])
            else:
                logger.error(f"Failed to authenticate to Elasticsearch: {baseURI}")
                sys.exit(1)
        else:
            break

    #baseURI = f"{proto}://{ipHost}:{port}"
    logger.info(f"Successfully connected to Elasticsearch: {baseURI}")
    return baseURI, s

def prompt_for_es_ignore_certificate_errors(try_again=False):
    if not try_again:
        ignore_cert_errors = input_bool("Do you want to ignore certificate errors?", default=True)
    else:
        ignore_cert_errors = input_bool(f"{LOG_COLORS['WARNING']}SSL Certificate ERROR ocurred. Do you want to try again and ignore certificate errors? {COLORS['ENDC']}", default=True)
    return ignore_cert_errors

def prompt_for_es_user_and_password(try_again=False):
    if not try_again:
        auth = input_bool("Do you want to use user and password authentication?", default=True)
    else:
        auth = input_bool(f"{LOG_COLORS['WARNING']}Authentication failed. Do you want to try to enter the username and password again? {COLORS['ENDC']}", default=True)
    if auth:
        user = input("Enter the username: ")
        password = getpass.getpass("Enter the password: ")
        return [user, password]
    else:
        return None

def unzip_git(filename):
    try:
        fname = os.path.basename(filename)
        git_unzip_dir_name = os.path.join( Temp_Output_Dir, os.path.splitext(fname)[0] )
        with zipfile.ZipFile( filename, 'r' ) as zip_ref:
            unzip_name = zip_ref.namelist()[ 0 ]
            zip_ref.extractall( Temp_Output_Dir )
            shutil.move( os.path.join( Temp_Output_Dir, unzip_name ), os.path.join( git_unzip_dir_name ) )
            os.remove( filename )
            logger.debug(f"Successfully unzipped and removed Git file {fname} to: {git_unzip_dir_name}")
            return git_unzip_dir_name
    except zipfile.BadZipFile as e:
        logger.error(f"Error occurred while unzipping Git file: {e}")
        raise ValueError(f"Error occurred while unzipping Git file: {e}")
    except Exception as e:
        logger.error(f"Error occurred while unzipping Git file: {e}")
        raise ValueError(f"Error occurred while unzipping Git file: {e}")

def source_repository(name, repo_type, proxy=None, ssl_verify=None):
    # URL
    if name.startswith("http"):
        if proxy:
            proxies = {
                "http": proxy,
                "https": proxy
            }
        else:
            proxies = None
        randomNum = random.randint(0, 100)
        timestamp = int(time.time())
        filename = os.path.join(Temp_Output_Dir, f"{repo_type}_repo_{timestamp}_{randomNum}.zip")
        # Download the repository (zip file)
        try:
            with requests.get(name, proxies=proxies, stream=True, verify=ssl_verify) as r:
                with open(filename, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
            logger.info(f"Successfully downloaded repository: {name}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error occurred while downloading repository: {e}")
            raise ValueError(f"Error occurred while downloading repository: {e}")
        # Unzip the repository
        name = unzip_git(filename)
        return name
    # Zip
    elif name.endswith(".zip") and os.path.isfile(name):
        name = unzip_git(name)
        return name
    # Path
    elif os.path.exists(name):
        return name
    else:
        logger.error(f"Invalid repository name or path for {name}")
        raise ValueError(f"Invalid repository name or path for {name}")


def copy_configs(src=None, dest=None, sub_dir=None, error_on_overwrites=False, ignore_file_extensions=None):
    final_src_dir = src
    if sub_dir and not final_src_dir.endswith(sub_dir):
        final_src_dir = os.path.join(final_src_dir, sub_dir)
    try:
        if os.path.exists(dest):
            if os.path.exists(final_src_dir) and error_on_overwrites:
                logger.error(f"The path {final_src_dir} already exists. Please select the update operation.")
                raise ValueError(f"The path {final_src_dir} already exists. Please select the update operation.")
            else:
                # Check if the source directory exists
                if not os.path.exists( src ):
                    logger.error( f"The source directory {src} does not exist." )
                    return
                # Create the destination directory if it doesn't exist
                if not os.path.exists( dest ):
                    os.makedirs( dest )
                # Walk the source directory
                for dirpath, dirnames, filenames in os.walk( src ):
                    # Create the corresponding directory in the destination
                    dest_dir = os.path.join( dest, os.path.relpath( dirpath, src ) )
                    if not os.path.exists( dest_dir ):
                        os.mkdir( dest_dir )
                    # Copy each file to the destination directory
                    for filename in filenames:
                        fname = os.path.splitext( filename )[ 0 ]
                        fextension = os.path.splitext( filename )[ 1 ]
                        if not ignore_file_extensions:
                            src_file = os.path.join( dirpath, filename )
                            dest_file = os.path.join( dest_dir, filename )
                            shutil.copy2( src_file, dest_file )  # copy
                        if ignore_file_extensions and not fextension in ignore_file_extensions:
                            src_file = os.path.join( dirpath, filename )
                            dest_file = os.path.join( dest_dir, filename )
                            shutil.copy2( src_file, dest_file )  # copy
                logger.debug(f"Files sucessfully copied to {dest}")
        else:
            create_dir = input_bool(f"{LOG_COLORS['WARNING']}The path {dest} does not exist. Would you like to create it?", default=True)
            if create_dir:
                os.makedirs(dest)
                copy_configs(src=src,dest=final_src_dir, sub_dir=sub_dir, error_on_overwrites=error_on_overwrites, ignore_file_extensions=ignore_file_extensions)
            else:
                logger.error(f"Installation aborted. The path {dest} does not exist." % dest)
                raise ValueError(f"Installation aborted. The path {dest} does not exist." % dest)
    except Exception as e:
        logger.error(f"Error occurred while copying files: {e}")
        raise ValueError(f"Error occurred while copying files: {e}")

def enable_ls_input(source_dir=None, ingest_type=None, raw=None, destination_dir=None, sub_dir=None):
    if sub_dir and not destination_dir.endswith(sub_dir):
        destination_dir = os.path.join(destination_dir, sub_dir)
    file_names = {
        "tcp": "0002-corelight-ecs-tcp-input",
        "tcp_ssl": "0002-corelight-ecs-tcp-ssl_tls-input",
        "hec": "0002-corelight-ecs-http-for_splunk_hec",
        "kafka": "0002-corelight-ecs-kafka-input",
        "udp": "0002-corelight-ecs-udp-input"
    }
    codec_disabled_suffix = "-codec_disabled_to_keep_raw_message"
    source_file_extension = ".conf.disabled"
    dest_file_extension = ".conf"
    source_file_name = file_names[ingest_type] + codec_disabled_suffix + source_file_extension if raw else file_names[ingest_type] + source_file_extension
    dest_file_name = file_names[ingest_type] + codec_disabled_suffix + dest_file_extension if raw else file_names[ingest_type] + dest_file_extension
    source = os.path.join(source_dir, source_file_name)
    dest = os.path.join(destination_dir, dest_file_name)
    try:
        shutil.copy(source, dest)
        logger.info(f"Successfully enabled {ingest_type} at {dest}")
        return dest
    except Exception as e:
        logger.error(f"Error occurred while enabling {ingest_type} {e}")
        raise ValueError(f"Error occurred while enabling {ingest_type} {e}")

def replace_var_in_directory(directory, replace_var="", replace_var_with=None):
    replaced_var_count = 0
    replaced_var_files = []
    if replace_var_with:
        for root, dirs, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)
                # Read the file
                with open(file_path, 'r', encoding='utf-8') as file:
                    file_contents = file.read()
                if replace_var in file_contents:
                    replaced_var_count += 1
                    replaced_var_files.append(file_path)
                    # Replace variables in the file
                    updated_contents = re.sub( r'\b' + re.escape( replace_var ) + r'\b', replace_var_with, file_contents )
                    # Write the modified content back to the file
                    with open(file_path, 'w', encoding='utf-8') as file:
                        file.write(updated_contents)
        if replaced_var_count == 0:
            logger.warning(f"Did not find {replace_var} in {directory}")
        else:
            logger.debug(f"Successfully replaced {replace_var} with {replace_var_with} {replaced_var_count} times in {sorted(set(replaced_var_files))}")

def es_export_upload_file(session, baseURI, uri_path, source_dir=None, human_path_name=None, retry=es_default_retry,timeout=es_default_timeout):
    """Upload files to Elasticsearch. Removes the file extension (only if '.json') from the filename and uses the remaining as the name in Elasticsearch."""
    if source_dir and os.path.isdir(source_dir):
        file_count = sum(1 for _, _, files in os.walk(source_dir) for _ in files)
        logger.info(f"Uploading {file_count} {human_path_name} files from {source_dir}")
        success_count = 0
        for root, dirs, files in os.walk( source_dir ):
            for filename in files:
                # Set the full path variable
                file_path = os.path.join( root, filename )
                extension = os.path.splitext( filename )[ 1 ]
                if extension == ".json":
                    req_resource_name = os.path.splitext( filename )[ 0 ]
                else:
                    req_resource_name = filename
                try:
                    with open( file_path ) as f:
                        request_data = f.read()
                except FileNotFoundError:
                    logger.error( f"Error: File {file_path} not found" )
                    return
                es_export_to_elastic( session, baseURI, req_uri=f'{uri_path}{req_resource_name}', req_resource_name=req_resource_name, request_body=request_data, retry=es_default_retry, timeout=es_default_timeout )
    else:
        logger.error( f"'{source_dir}' is not specified or is not a directory")

def make_modifications(session=None, baseURI=None, pipeline_type=None, final_templates_dir=None, final_pipelines_dir=None, VAR_CORELIGHT_INDEX_STRATEGY=None, use_templates=False):
    """Use modified files and upload"""
    # Templates
    if use_templates:
        if VAR_CORELIGHT_INDEX_STRATEGY == "datastream":
            # Component Templates
            source_dir = os.path.join( final_templates_dir, "component_template" )
            human_path_name = "component template"
            es_export_upload_file( session, baseURI, "/_component_template/", source_dir=source_dir, human_path_name=human_path_name, retry=es_default_retry, timeout=es_default_timeout )
            # ILM Policies
            source_dir = os.path.join( final_templates_dir, "ilm_policy" )
            es_export_upload_file( session, baseURI, "/_ilm/policy/", source_dir=source_dir, human_path_name=human_path_name,  retry=es_default_retry, timeout=es_default_timeout )
            human_path_name = "ilm policy"
            # Index Templates
            source_dir = os.path.join( final_templates_dir, "index_template" )
            es_export_upload_file( session, baseURI, "/_index_template/", source_dir=source_dir, human_path_name=human_path_name,  retry=es_default_retry, timeout=es_default_timeout )
            human_path_name = "index template"
            # Create the custom component templates if they don't exist
            custom_component_templates = set(gather_custom_component_templates(final_templates_dir))
            if custom_component_templates:
                for req_resource_name in custom_component_templates:
                    # Add query parameter '?create=true'. which means, this request cannot replace or update existing component templates"
                    # https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-component-template.html#put-component-template-api-query-params
                    es_export_to_elastic(session, baseURI, req_uri=f'/_component_template/{req_resource_name}?create=true', req_resource_name=req_resource_name, request_body='{"template": {}}', retry=es_default_retry, timeout=es_default_timeout, ignore_status_codes=[400])

        else: # Unsupported index strategy
            logger.error(f"Unsupported index strategy: {VAR_CORELIGHT_INDEX_STRATEGY}")
    # Ingest Pipelines
    if pipeline_type == 'ingest':
        source_dir = final_pipelines_dir
        human_path_name = "ingest pipeline"
        es_export_upload_file( session, baseURI, "/_ingest/pipeline/", source_dir=source_dir,  human_path_name=human_path_name,  retry=es_default_retry, timeout=es_default_timeout )

def categorize_ls_files(directory):
    input_files = []
    filter_files = []
    output_files = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith('-input.conf'):
                input_files.append(file_path)
            if file.endswith('-filter.conf'):
                filter_files.append(file_path)
            if file.endswith('-output.conf'):
                output_files.append(file_path)
    # Sort the lists in alphanumeric order
    input_files = sorted(input_files)
    filter_files = sorted(filter_files)
    output_files = sorted(output_files)
    return input_files, filter_files, output_files

def clean_ls_content(content, start_pattern, file_name):
    # Remove the specified pattern at the start and the last closing brace
    content = re.sub(start_pattern, f'', content, count=1)
    #content = re.sub(r'(?m)^(?!.*\s*#).*\}\s*$', f'', content, count=1)
    content = re.sub(r'(?m)^\}(?![\s\S]*^\})', f'######## End "{file_name}" ########', content)

    # Add two spaces to comments at beginning of each line
    content = re.sub(r'(?m)^(\S)', r'  \1', content)

    return content

def concat_ls_files(ls_input_files, ls_filter_files, ls_output_files, output_file):
    with open(output_file, 'w') as outfile:
        # Process input files
        for i, file_path in enumerate(ls_input_files):
            file_name = os.path.basename(file_path)
            with open(file_path, 'r') as infile:
                content = infile.read()
                cleaned_content = clean_ls_content(content, r'(?m)^(?!.*\s*#).*\s*input\s*\{', file_name)
                if i == 0:  # First input file
                    outfile.write("\n\ninput {\n")
                outfile.write(f'\n  ######## Begin "{file_name}" ########\n{cleaned_content}')
                if i == len(ls_input_files) - 1:  # Last input file
                    outfile.write("\n}")
        # Process filter files
        for i, file_path in enumerate(ls_filter_files):
            file_name = os.path.basename(file_path)
            with open(file_path, 'r') as infile:
                content = infile.read()
                cleaned_content = clean_ls_content(content, r'(?m)^(?!.*\s*#).*\s*filter\s*\{', file_name)
                if i == 0:  # First filter file
                    outfile.write("\n\nfilter {\n")
                outfile.write(f'\n  ######## Begin "{file_name}" ########\n{cleaned_content}')
                if i == len(ls_filter_files) - 1:  # Last filter file
                    outfile.write("\n}")
        # Process output files
        for i, file_path in enumerate(ls_output_files):
            file_name = os.path.basename(file_path)
            with open(file_path, 'r') as infile:
                content = infile.read()
                cleaned_content = clean_ls_content(content, r'(?m)^(?!.*\s*#).*\s*output\s*\{', file_name)
                if i == 0:  # First output file
                    outfile.write("\n\noutput {\n")
                outfile.write(f'\n  ######## Begin "{file_name}" ########\n{cleaned_content}')
                if i == len(ls_output_files) - 1:  # Last output file
                    outfile.write("\n}")

def gather_custom_component_templates(directory):
    """
    Custom component templates are designated by meeting all the requirements:
    1. Value within ignore_missing_component_templates
    2. Value begins with 'corelight-ecs-component-'
    3. Value ends with '@custom'
    """
    collected_templates = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.json'):
                try:
                    with open(os.path.join(root, file), 'r') as f:
                        data = json.load(f)
                        if "ignore_missing_component_templates" in data and data["ignore_missing_component_templates"]:
                            collected_templates.extend(data["ignore_missing_component_templates"])
                except Exception as e:
                    logger.warning(f"Unable to gather custom component templates from index template '{os.path.join(root,file)}'. Error: {e}")
    return collected_templates

def setup_logger(no_color, debug):
    # Set up logging
    class ColoredFormatter(logging.Formatter):
        def format(self, record, *args, **kwargs):
            if no_color:
                log_message = super().format(record) #super().format( record, *args, **kwargs )
                return log_message
            else:
                log_message = super().format( record) #super().format( record, *args, **kwargs )
                return LOG_COLORS.get(record.levelname, '') + log_message + COLORS['ENDC']
    #logging.basicConfig(level=logging.INFO)
    #logger.setLevel(logging.DEBUG)
    if debug:
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
    formatter = ColoredFormatter("%(levelname)s: %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger

def var_replace_prompt(use_templates=False, use_pipelines=False, Final_Pipelines_Dir=None, Final_Templates_Dir=None):

    # Protocol Logs / Main Logs / Known Logs / Known Protocol Logs
    VAR_CL_DS_TYPE_PROTOCOL_LOG = "logs"
    VAR_CL_DS_PREFIX_PROTOCOL_LOG = "corelight"
    VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict = {
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_CONN": "conn",
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_DNS": "dns",
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_FILES": "files",
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_HTTP": "http",
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SMB": "smb",
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SMTP": "smtp",
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SSL": "ssl",
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SURICATA_CORELIGHT": "suricata_corelight",
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SYSLOG": "syslog",
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_VARIOUS": "various",
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_WEIRD": "weird",
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_X509": "x509"
    }
    VAR_CL_DS_NAMESPACE_PROTOCOL_LOG = "default"
    VAR_CL_DS_INDEX_PRIORITY_PROTOCOL_LOG = f'901'
    # Unknown Logs
    VAR_CL_DS_TYPE_UNKNOWN_LOG = "logs"
    VAR_CL_DS_PREFIX_UNKNOWN_LOG = "corelight"
    VAR_CL_DS_SUFFIX_UNKNOWN_LOG = "unknown"
    VAR_CL_DS_NAMESPACE_UNKNOWN_LOG = "default"
    VAR_CL_DS_INDEX_PRIORITY_UNKNOWN_LOG = f'901'
    # Metrics Logs / Non Protocol Log Metrics (Metrics and Stats)
    VAR_CL_DS_TYPE_METRIC_LOG = "zeek"
    VAR_CL_DS_PREFIX_METRIC_LOG = "corelight"
    VAR_CL_DS_SUFFIX_METRIC_LOG = "metric"
    VAR_CL_DS_NAMESPACE_METRIC_LOG = "default"
    VAR_CL_DS_INDEX_PRIORITY_METRIC_LOG = f'901'
    # System Logs / Non Protocol Log System (System, IAM, Netcontrol, and Audit)
    VAR_CL_DS_TYPE_SYSTEM_LOG = "zeek"
    VAR_CL_DS_PREFIX_SYSTEM_LOG = "corelight"
    VAR_CL_DS_SUFFIX_SYSTEM_LOG = "system"
    VAR_CL_DS_NAMESPACE_SYSTEM_LOG = "default"
    VAR_CL_DS_INDEX_PRIORITY_SYSTEM_LOG = f'901'
    # Parse Failures / Failed Logs / pipeline_error
    VAR_CL_DS_TYPE_PARSE_FAILURES_LOG = "parse_failures"
    VAR_CL_DS_PREFIX_PARSE_FAILURES_LOG = "corelight"
    VAR_CL_DS_SUFFIX_PARSE_FAILURES_LOG = "pipeline_error"
    VAR_CL_DS_NAMESPACE_PARSE_FAILURES_LOG = "default"
    VAR_CL_DS_INDEX_PRIORITY_PARSE_FAILURES_LOG = f'901'

    USE_CUSTOM_INDEX_NAMES = input_bool( f"\nDo you want to use custom index names?", default=False )
    if USE_CUSTOM_INDEX_NAMES:
        # Protocol Logs / Main Logs / Known Logs / Known Protocol Logs
        VAR_CL_DS_TYPE_PROTOCOL_LOG = input_string( question=f"Enter the Datastream 'type' for Protocol Logs", default=f"{VAR_CL_DS_TYPE_PROTOCOL_LOG}" )
        VAR_CL_DS_PREFIX_PROTOCOL_LOG = input_string( question=f"Enter the Datastream 'prefix' for Protocol Logs", default=f"{VAR_CL_DS_PREFIX_PROTOCOL_LOG}" )
        VAR_CL_DS_NAMESPACE_PROTOCOL_LOG = input_string( question=f"Enter the Datastream 'namespace' for Protocol Logs", default=f"{VAR_CL_DS_NAMESPACE_PROTOCOL_LOG}" )
        # Unknown Logs
        VAR_CL_DS_TYPE_UNKNOWN_LOG = input_string( question=f"Enter the Datastream 'type' for Unknown Protocol Logs", default=f"{VAR_CL_DS_TYPE_UNKNOWN_LOG}" )
        VAR_CL_DS_PREFIX_UNKNOWN_LOG = input_string( question=f"Enter the Datastream 'prefix' for Unknown Protocol Logs", default=f"{VAR_CL_DS_PREFIX_UNKNOWN_LOG}" )
        VAR_CL_DS_SUFFIX_UNKNOWN_LOG = input_string( question=f"Enter the Datastream 'suffix' for Unknown Protocol Logs", default=f"{VAR_CL_DS_SUFFIX_UNKNOWN_LOG}" )
        VAR_CL_DS_NAMESPACE_UNKNOWN_LOG = input_string( question=f"Enter the Datastream 'namespace' for Protocol Logs Unknown", default=f"{VAR_CL_DS_NAMESPACE_UNKNOWN_LOG}" )
        # Metrics Logs / Non Protocol Log Metrics (Metrics and Stats)
        VAR_CL_DS_TYPE_METRIC_LOG = input_string( question=f"Enter the Datastream 'type' for Metric Logs", default=f"{VAR_CL_DS_TYPE_METRIC_LOG}" )
        VAR_CL_DS_PREFIX_METRIC_LOG = input_string( question=f"Enter the Datastream 'prefix' for Metric Logs", default=f"{VAR_CL_DS_PREFIX_METRIC_LOG}" )
        VAR_CL_DS_SUFFIX_METRIC_LOG = input_string( question=f"Enter the Datastream 'suffix' for Metric Logs", default=f"{VAR_CL_DS_SUFFIX_METRIC_LOG}" )
        VAR_CL_DS_NAMESPACE_METRIC_LOG = input_string( question=f"Enter the Datastream 'namespace' for Metric Logs", default=f"{VAR_CL_DS_NAMESPACE_METRIC_LOG}" )
        # System Logs / Non Protocol Log System (System, IAM, Netcontrol, and Audit)
        VAR_CL_DS_TYPE_SYSTEM_LOG = input_string( question=f"Enter the Datastream 'type' for System Logs", default=f"{VAR_CL_DS_TYPE_SYSTEM_LOG}" )
        VAR_CL_DS_PREFIX_SYSTEM_LOG = input_string( question=f"Enter the Datastream 'prefix' for System Logs", default=f"{VAR_CL_DS_PREFIX_SYSTEM_LOG}" )
        VAR_CL_DS_SUFFIX_SYSTEM_LOG = input_string( question=f"Enter the Datastream 'suffix' for System Logs", default=f"{VAR_CL_DS_SUFFIX_SYSTEM_LOG}" )
        VAR_CL_DS_NAMESPACE_SYSTEM_LOG = input_string( question=f"Enter the Datastream 'namespace' for System Logs", default=f"{VAR_CL_DS_NAMESPACE_SYSTEM_LOG}" )
        # Parse Failures / Failed Logs / pipeline_error
        VAR_CL_DS_TYPE_PARSE_FAILURES_LOG = input_string( question=f"Enter the Datastream 'type' for Parse Failures", default=f"{VAR_CL_DS_TYPE_PARSE_FAILURES_LOG}" )
        VAR_CL_DS_PREFIX_PARSE_FAILURES_LOG = input_string( question=f"Enter the Datastream 'prefix' for Parse Failures", default=f"{VAR_CL_DS_PREFIX_PARSE_FAILURES_LOG}" )
        VAR_CL_DS_SUFFIX_PARSE_FAILURES_LOG = input_string( question=f"Enter the Datastream 'suffix' for Parse Failures", default=f"{VAR_CL_DS_SUFFIX_PARSE_FAILURES_LOG}" )
        VAR_CL_DS_NAMESPACE_PARSE_FAILURES_LOG = input_string( question=f"Enter the Datastream 'namespace' for Parse Failures", default=f"{VAR_CL_DS_NAMESPACE_PARSE_FAILURES_LOG}" )

    # Set Index Patterns after choice to use custom index names
    VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_dict = {
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_CONN": f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}.{VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.get("VAR_CL_DS_SUFFIX_PROTOCOL_LOG_CONN")}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_DNS": f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}.{VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.get("VAR_CL_DS_SUFFIX_PROTOCOL_LOG_DNS")}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_FILES": f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}.{VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.get("VAR_CL_DS_SUFFIX_PROTOCOL_LOG_FILES")}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_HTTP": f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}.{VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.get("VAR_CL_DS_SUFFIX_PROTOCOL_LOG_HTTP")}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_SMB": f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}.{VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.get("VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SMB")}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_SMTP": f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}.{VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.get("VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SMTP")}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_SSL": f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}.{VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.get("VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SSL")}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_SURICATA_CORELIGHT": f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}.{VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.get("VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SURICATA_CORELIGHT")}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_SYSLOG": f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}.{VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.get("VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SYSLOG")}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_VARIOUS": f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}.{VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.get("VAR_CL_DS_SUFFIX_PROTOCOL_LOG_VARIOUS")}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_WEIRD": f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}.{VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.get("VAR_CL_DS_SUFFIX_PROTOCOL_LOG_WEIRD")}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_X509": f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}.{VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.get("VAR_CL_DS_SUFFIX_PROTOCOL_LOG_X509")}-*',
    }
    VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG = f'{VAR_CL_DS_TYPE_PROTOCOL_LOG}-{VAR_CL_DS_PREFIX_PROTOCOL_LOG}'
    VAR_CL_DS_INDEX_PATTERN_UNKNOWN_LOG = f'{VAR_CL_DS_TYPE_UNKNOWN_LOG}-{VAR_CL_DS_PREFIX_UNKNOWN_LOG}.{VAR_CL_DS_SUFFIX_UNKNOWN_LOG}-*'
    VAR_CL_DS_INDEX_PATTERN_METRIC_LOG = f'{VAR_CL_DS_TYPE_METRIC_LOG}-{VAR_CL_DS_PREFIX_METRIC_LOG}.{VAR_CL_DS_SUFFIX_METRIC_LOG}-*'
    VAR_CL_DS_INDEX_PATTERN_SYSTEM_LOG = f'{VAR_CL_DS_TYPE_SYSTEM_LOG}-{VAR_CL_DS_PREFIX_SYSTEM_LOG}.{VAR_CL_DS_SUFFIX_SYSTEM_LOG}-*'
    VAR_CL_DS_INDEX_PATTERN_PARSE_FAILURES_LOG = f'{VAR_CL_DS_TYPE_PARSE_FAILURES_LOG}-{VAR_CL_DS_PREFIX_PARSE_FAILURES_LOG}.{VAR_CL_DS_SUFFIX_PARSE_FAILURES_LOG}-*'

    if use_pipelines:
        # Protocol Logs / Main Logs / Known Logs / Known Protocol Logs
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_TYPE_PROTOCOL_LOG", replace_var_with=VAR_CL_DS_TYPE_PROTOCOL_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_PREFIX_PROTOCOL_LOG", replace_var_with=VAR_CL_DS_PREFIX_PROTOCOL_LOG )
        for key, value in VAR_CL_DS_SUFFIX_PROTOCOL_LOG_dict.items():
            replace_var_in_directory( Final_Pipelines_Dir, replace_var=f"{key}", replace_var_with=f"{value}" )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_NAMESPACE_PROTOCOL_LOG", replace_var_with=VAR_CL_DS_NAMESPACE_PROTOCOL_LOG )
        # Unknown Logs
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_TYPE_UNKNOWN_LOG", replace_var_with=VAR_CL_DS_TYPE_UNKNOWN_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_PREFIX_UNKNOWN_LOG", replace_var_with=VAR_CL_DS_PREFIX_UNKNOWN_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_SUFFIX_UNKNOWN_LOG", replace_var_with=VAR_CL_DS_SUFFIX_UNKNOWN_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_NAMESPACE_UNKNOWN_LOG", replace_var_with=VAR_CL_DS_NAMESPACE_UNKNOWN_LOG )
        # Metrics Logs / Non Protocol Log Metrics (Metrics and Stats)
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_TYPE_METRIC_LOG", replace_var_with=VAR_CL_DS_TYPE_METRIC_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_PREFIX_METRIC_LOG", replace_var_with=VAR_CL_DS_PREFIX_METRIC_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_SUFFIX_METRIC_LOG", replace_var_with=VAR_CL_DS_SUFFIX_METRIC_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_NAMESPACE_METRIC_LOG", replace_var_with=VAR_CL_DS_NAMESPACE_METRIC_LOG )
        # System Logs / Non Protocol Log System (System, IAM, Netcontrol, and Audit)
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_TYPE_SYSTEM_LOG", replace_var_with=VAR_CL_DS_TYPE_SYSTEM_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_PREFIX_SYSTEM_LOG", replace_var_with=VAR_CL_DS_PREFIX_SYSTEM_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_SUFFIX_SYSTEM_LOG", replace_var_with=VAR_CL_DS_SUFFIX_SYSTEM_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_NAMESPACE_SYSTEM_LOG", replace_var_with=VAR_CL_DS_NAMESPACE_SYSTEM_LOG )
        # Parse Failures / Failed Logs / pipeline_error
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_TYPE_PARSE_FAILURES_LOG", replace_var_with=VAR_CL_DS_TYPE_PARSE_FAILURES_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_PREFIX_PARSE_FAILURES_LOG", replace_var_with=VAR_CL_DS_PREFIX_PARSE_FAILURES_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_SUFFIX_PARSE_FAILURES_LOG", replace_var_with=VAR_CL_DS_SUFFIX_PARSE_FAILURES_LOG )
        replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CL_DS_NAMESPACE_PARSE_FAILURES_LOG", replace_var_with=VAR_CL_DS_NAMESPACE_PARSE_FAILURES_LOG )

    if use_templates:
        USE_CUSTOM_INDEX_PRIORITIES = input_bool( f"\nDo you want to use custom index priorities?", default=False )
        if USE_CUSTOM_INDEX_PRIORITIES:
            # Protocol Logs / Main Logs / Known Logs / Known Protocol Logs
            VAR_CL_DS_INDEX_PRIORITY_PROTOCOL_LOG = input_int( question=f"Enter the Index Priority for Protocol Logs", default=f"{VAR_CL_DS_INDEX_PRIORITY_PROTOCOL_LOG}" )
            VAR_CL_DS_INDEX_PRIORITY_UNKNOWN_LOG = input_int( question=f"Enter the Index Priority for Unknown Logs", default=f"{VAR_CL_DS_INDEX_PRIORITY_UNKNOWN_LOG}" )
            VAR_CL_DS_INDEX_PRIORITY_METRIC_LOG = input_int( question=f"Enter the Index Priority for Metric Logs", default=f"{VAR_CL_DS_INDEX_PRIORITY_METRIC_LOG}" )
            VAR_CL_DS_INDEX_PRIORITY_SYSTEM_LOG = input_int( question=f"Enter the Index Priority for System Logs", default=f"{VAR_CL_DS_INDEX_PRIORITY_SYSTEM_LOG}" )
            VAR_CL_DS_INDEX_PRIORITY_PARSE_FAILURES_LOG = input_int( question=f"Enter the Index Priority for Parse Failures", default=f"{VAR_CL_DS_INDEX_PRIORITY_PARSE_FAILURES_LOG}" )


        # Protocol Logs / Main Logs / Known Logs / Known Protocol Logs
        for key, value in VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_dict.items():
            replace_var_in_directory( Final_Templates_Dir, replace_var=f"{key}", replace_var_with=f"{value}" )
        replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CL_DS_INDEX_PRIORITY_PROTOCOL_LOG", replace_var_with=VAR_CL_DS_INDEX_PRIORITY_PROTOCOL_LOG )
        # Unknown Logsa
        replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CL_DS_INDEX_PATTERN_UNKNOWN_LOG", replace_var_with=VAR_CL_DS_INDEX_PATTERN_UNKNOWN_LOG )
        replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CL_DS_INDEX_PRIORITY_UNKNOWN_LOG", replace_var_with=VAR_CL_DS_INDEX_PRIORITY_UNKNOWN_LOG )
        # System Logs / Non Protocol Log System (System, IAM, Netcontrol, and Audit)
        replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CL_DS_INDEX_PATTERN_METRIC_LOG", replace_var_with=VAR_CL_DS_INDEX_PATTERN_METRIC_LOG )
        replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CL_DS_INDEX_PRIORITY_METRIC_LOG", replace_var_with=VAR_CL_DS_INDEX_PRIORITY_METRIC_LOG )
        # Parse Failures / Failed Logs / pipeline_error
        replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CL_DS_INDEX_PATTERN_SYSTEM_LOG", replace_var_with=VAR_CL_DS_INDEX_PATTERN_SYSTEM_LOG )
        replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CL_DS_INDEX_PRIORITY_SYSTEM_LOG", replace_var_with=VAR_CL_DS_INDEX_PRIORITY_SYSTEM_LOG )

        replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CL_DS_INDEX_PATTERN_PARSE_FAILURES_LOG", replace_var_with=VAR_CL_DS_INDEX_PATTERN_PARSE_FAILURES_LOG )
        replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CL_DS_INDEX_PRIORITY_PARSE_FAILURES_LOG", replace_var_with=VAR_CL_DS_INDEX_PRIORITY_PARSE_FAILURES_LOG )

def main():
    # Gather args
    args = parse_args()
    # Setup logging
    setup_logger(args.no_color, args.debug)

    create_es_connection = False
    dry_run = False

    # Final config directory
    Final_Config_Dir = os.path.join( Config_Dir, "last_run" )
    Final_Pipelines_Dir = os.path.join( Final_Config_Dir,  "pipelines" )
    Final_Templates_Dir = os.path.join( Final_Config_Dir, "templates" )
    Previous_Config_Dir = os.path.join( Config_Dir, "previous", dir_time )
    # List of files to tell user to modify at the end
    ls_files_to_modify = list()

    # Situations to short circuit the rest of script of prompts
    if args.final_config_dir and args.build_logstash_xpack_mgmt:
        Final_Config_Dir = args.final_config_dir
        use_last_run = False
        print(f"Using logstash configs from: {Final_Config_Dir}")
        ls_input_files, ls_filter_files, ls_output_files = categorize_ls_files( Final_Config_Dir )
        ls_xpack_mgmt_out_file = os.path.join( Final_Config_Dir, "all_logstash_config_for_xpack_mgmt.conf" )
        concat_ls_files( ls_input_files, ls_filter_files, ls_output_files, ls_xpack_mgmt_out_file )
        sys.exit(1)

    # Prompt user if they want to use configs from last run, if they exist
    use_last_run = input_bool(f"Would you like to use configs from a previous run?", default=False)
    # Prompt user for the directory of the last run
    if use_last_run:
        Final_Config_Dir = input_string(f"Enter the directory of the last run",default=Final_Config_Dir)
        Final_Pipelines_Dir = os.path.join( Final_Config_Dir, "pipelines" )
        Final_Templates_Dir = os.path.join( Final_Config_Dir, "templates" )
        if os.path.exists(Final_Config_Dir):
            logger.info(f"Using configs from last run: {Final_Config_Dir}")
        else:
            logger.error(f"Unable to find last run directory: '{Final_Config_Dir}'")
            raise ValueError(f"Unable to find last run directory: '{Final_Config_Dir}'")
    else:
        # Recreate final config directory before use
        try:
            shutil.rmtree(Final_Config_Dir) # Delete the directory
        except FileNotFoundError:
            pass
        try:
            os.makedirs( Final_Config_Dir )
        except OSError as e:
            logger.error( f"Unable to create necessary directories: {e}" )
            sys.exit( 1 )
        # Create the output directories if they don't exist
        try:
            os.makedirs( Final_Pipelines_Dir )
        except OSError as e:
            logger.error( f"Unable to create necessary directories: {e}" )
            sys.exit( 1 )
        try:
            os.makedirs( Final_Templates_Dir )
        except OSError as e:
            logger.error( f"Unable to create necessary directories: {e}" )
            sys.exit( 1 )
        try:
            os.makedirs( Previous_Config_Dir )
        except OSError as e:
            logger.error( f"Unable to create necessary directories: {e}" )
            sys.exit( 1 )
        dry_run = input_bool(f"Is this a dry run? All configurations and files will be prepared and stored, however no changes will be installed/uploaded.", default=True)
        install_templates = input_bool(f"Will you be installing Elasticsearch templates, mappings, and settings? Recommended with any updates.", default=True)
        pipeline_type = input(f"\nWill you be installing Pipelines? Ingest Pipelines, Logstash Pipelines, or no (Enter 'ingest'/'i', 'logstash'/'l', or 'no'/'n'/'none'): ").strip("'").strip().lower()
        while pipeline_type.lower() not in ['ingest', 'i', 'logstash', 'l', 'no', 'n']:
            pipeline_type = input(f"{LOG_COLORS['WARNING']}Invalid input. Please enter one of:"
                                  f"\n'ingest' or 'i' for Ingest Pipelines"
                                  f"\n'logstash' or 'l' for Logstash Pipelines"
                                  f"\n'no' or 'n' for skipping installation of pipelines"
                                  f"\n: {COLORS['ENDC']}")
        if pipeline_type == 'i':
            create_es_connection = True
            pipeline_type = 'ingest'
        elif pipeline_type == 'l':
            pipeline_type = 'logstash'
        elif pipeline_type == 'n':
            pipeline_type = 'no'
        VAR_CORELIGHT_INDEX_STRATEGY = "datastream"
        #VAR_CORELIGHT_INDEX_STRATEGY = input(f"\nWhat index strategy will you be using? (Enter 'datastream'/'d'): ").strip().lower() #, 'legacy'/'l'): ").strip().lower()
        #while VAR_CORELIGHT_INDEX_STRATEGY.strip("'").strip().lower() not in ['datastream', 'd']:#, 'legacy', 'l']:
        #    VAR_CORELIGHT_INDEX_STRATEGY = input(f"{LOG_COLORS['WARNING']}Invalid input. Please enter one of:"
        #                                         f"\n'datastream' or 'd' for datastream index strategy"
        #                                         #f"\n'legacacy' or 'l' for legacy index strategy"
        #                                         f"\n: {COLORS['ENDC']}")
        #if VAR_CORELIGHT_INDEX_STRATEGY == "datastream" or "d":
        #    VAR_CORELIGHT_INDEX_STRATEGY = "datastream"
        #elif VAR_CORELIGHT_INDEX_STRATEGY == "legacy" or "l":
        #    VAR_CORELIGHT_INDEX_STRATEGY = "legacy"

        use_pipeline = False if pipeline_type == 'no' else True
        use_templates = install_templates

        if use_templates:
            create_es_connection = True
            # Source templates
            # Get source from user
            templates_source = input(f"\nHow will you source the templates?"
                                    f"\n  - Download git zip of repository. Requires the full URL. ({git_templates_repo})"
                                    f"\n  - Local zip path of a repistory. Requires the full path ending in .zip"
                                    f"\n  - Local path or git clone. Requires the full path (default {script_dir})"
                                    f"\nEnter the url, path, or press enter for '{script_dir}': ")
            # Use default if no input
            if not templates_source:
                templates_source = script_dir
            if templates_source.startswith('http'):
                proxy = input( f"\nEnter proxy URL if desired (leave empty or 'n'/'no' if not using a proxy): " )
                if proxy and not proxy in ["n", "no"]:
                    ignore_proxy_cert_errors = input_bool( f"Do you want to ignore proxy certificate errors?", default=True )
                else:
                    ignore_proxy_cert_errors = None
                    proxy = None
            else:
                ignore_proxy_cert_errors = None
                proxy = None
            if ignore_proxy_cert_errors:
                ssl_verify = False
                urllib3.disable_warnings( category=InsecureRequestWarning )
            else:
                ssl_verify = None
            # Set source
            templates_source_directory =  source_repository(templates_source, repo_type="templates", proxy=proxy, ssl_verify=ssl_verify)
            templates_source_directory = os.path.join(templates_source_directory, git_templates_sub_dir)
            if VAR_CORELIGHT_INDEX_STRATEGY == "datastream":
                templates_sub_dir = "component"
            elif VAR_CORELIGHT_INDEX_STRATEGY == "legacy":
                templates_sub_dir = "legacy"
            else:
                templates_sub_dir = ""
            templates_source_directory = os.path.join(templates_source_directory, "component")
            logger.debug(f"Using {templates_source_directory} as the source for the templates.")

            # Copy all sourced files to temporary directory
            copy_configs(src=templates_source_directory, dest=Final_Templates_Dir)
            logger.info(f"Using {Final_Templates_Dir} as the temporary directory for the templates.")

        if use_pipeline:
            # Logstash Pipelines
            if pipeline_type == 'logstash':
                git_pipeline_repo = git_logstash_repo
                pipeline_sub_dir = git_logstash_sub_dir
                pipeline_destination_directory = None
            elif pipeline_type == 'ingest':
                git_pipeline_repo = git_ingest_repo
                pipeline_sub_dir = git_ingest_sub_dir
                pipeline_destination_directory = None
            else:
                logger.error(f"Invalid pipeline type: {pipeline_type}")
                raise ValueError(f"Invalid pipeline type: {pipeline_type}")

            # Source Pipeline
            # Get source from user
            pipeline_source = input(f"\nHow will you source the {pipeline_type} pipelines?"
                                    f"\n  - Download git zip of repository. Requires the full URL. ({git_pipeline_repo})"
                                    f"\n  - Local zip path of a repistory. Requires the full path ending in .zip"
                                    f"\n  - Local path or git clone. Requires the full path"
                                    f"\nEnter the url, path, or press enter for '{git_pipeline_repo}': ")
            # Use default if no input
            if not pipeline_source:
                pipeline_source = git_pipeline_repo
            if pipeline_source.startswith('http'):
                proxy = input( f"\nEnter proxy URL if desired (leave empty, press enter, if not using a proxy): " )
                if proxy:
                    ignore_proxy_cert_errors = input_bool( f"Do you want to ignore proxy certificate errors?", default=True )
                else:
                    ignore_proxy_cert_errors = None
                    proxy = None
            else:
                ignore_proxy_cert_errors = None
                proxy = None
            if ignore_proxy_cert_errors:
                ssl_verify = False
                urllib3.disable_warnings( category=InsecureRequestWarning )
            else:
                ssl_verify = None
            # Set source
            pipeline_source_directory =  source_repository(pipeline_source, repo_type=pipeline_type, proxy=proxy, ssl_verify=ssl_verify)
            pipeline_source_directory = os.path.join(pipeline_source_directory, pipeline_sub_dir)
            logger.debug(f"Using {pipeline_source_directory} as the source for the {pipeline_type} pipelines.")

            # Copy all sourced files to temporary directory
            copy_configs(src=pipeline_source_directory, dest=Final_Pipelines_Dir, ignore_file_extensions=['.disabled'])
            logger.info(f"Using {Final_Pipelines_Dir} as the temporary directory for the {pipeline_type} pipelines.")

            # Logstash Pipelines Specifics
            if pipeline_type == 'logstash':

                # Get specifics and change variables
                input_type = input(f"\nHow will send data to Logstash?"
                                   f"\n  tcp        - JSON over TCP"
                                   f"\n  tcp_ssl    - JSON over TCP with SSL/TLS enabled"
                                   f"\n  hec        - HTTP Event Collector"
                                   f"\n  kafka      - Kafka"
                                   f"\n  udp        - UDP"
                                   f"\n Enter one of {logstash_input_choices}: ")
                while input_type.strip().lower() not in logstash_input_choices:
                    input_type = input(f"{LOG_COLORS['WARNING']}Invalid input. Please enter one of {logstash_input_choices}: {COLORS['ENDC']}")
                keep_raw = input_bool( "Do you want to keep the raw message? (This will increase storage space but is useful in certain environments for data integrity or troubleshooting)", default=False )
                ls_files_to_modify.append(enable_ls_input( source_dir=pipeline_source_directory, ingest_type=input_type, raw=keep_raw, destination_dir=Final_Pipelines_Dir))
                ls_files_to_modify.append(os.path.join(Final_Pipelines_Dir, ls_output_filename))

            # Ingest Pipelines Specifics
            elif pipeline_type == 'ingest':
                pass

        var_replace_prompt(use_templates=use_templates, use_pipelines=use_pipeline, Final_Pipelines_Dir=Final_Pipelines_Dir, Final_Templates_Dir=Final_Templates_Dir)

        # Save parameters to file
        param_path = None
        try:
            param_path = f"{Final_Config_Dir}/param_pipeline_type.var"
            with open(f"{param_path}", "w") as f:
                f.write(str(pipeline_type))
            param_path = f"{Final_Config_Dir}/param_create_es_connection.var"
            with open(f"{param_path}", "w") as f:
                f.write(str(create_es_connection))
            param_path = f"{Final_Config_Dir}/param_VAR_CORELIGHT_INDEX_STRATEGY.var"
            with open(f"{param_path}", "w") as f:
                f.write(str(VAR_CORELIGHT_INDEX_STRATEGY))
            param_path = f"{Final_Config_Dir}/param_use_templates.var"
            with open(f"{param_path}", "w") as f:
                f.write(str(use_templates))
        except Exception as e:
            logger.error(f"Error occurred while saving parameters to file: {e}")
            raise ValueError(f"Error occurred while saving parameters to file: {e}")

        # Copy all files to Previous_Config_Dir
        copy_configs(src=Final_Config_Dir, dest=Previous_Config_Dir)
        logger.info(f"Configurations for this specific time of run has been saved in {Previous_Config_Dir}")

    if use_last_run or not dry_run:
        if use_last_run: # Set parameters from file if using last run
            param_path = None
            try:
                param_path = f"{Final_Config_Dir}/param_create_es_connection.var"
                with open(f"{param_path}", "r") as f:
                    create_es_connection = f.read().strip()
                param_path = f"{Final_Config_Dir}/param_pipeline_type.var"
                with open(f"{param_path}", "r") as f:
                    pipeline_type = f.read().strip()
                param_path = f"{Final_Config_Dir}/param_VAR_CORELIGHT_INDEX_STRATEGY.var"
                with open(f"{param_path}", "r") as f:
                    VAR_CORELIGHT_INDEX_STRATEGY = f.read().strip()
                param_path = f"{Final_Config_Dir}/param_use_templates.var"
                with open(f"{param_path}", "r") as f:
                    use_templates = f.read().strip()
            except:
                logger.error(f"Unable to read parameters from {param_path}")
                raise ValueError(f"Unable to read parameters from {param_path}")
        if create_es_connection:
            baseURI, session = get_elasticsearch_connection_config()
            make_modifications(
                session=session,
                baseURI=baseURI,
                pipeline_type=pipeline_type,
                final_templates_dir=Final_Templates_Dir,
                final_pipelines_dir=Final_Pipelines_Dir,
                use_templates=use_templates,
                VAR_CORELIGHT_INDEX_STRATEGY=VAR_CORELIGHT_INDEX_STRATEGY
            )

    # Final config placement
    logger.info(f"Script has finished. You can review the final configurations in {Final_Config_Dir}")
    if pipeline_type == 'logstash':
        formatted_filenames = "\n".join( [ f'- "{file}"' for file in ls_files_to_modify ] )
        logger.info(f"Please review the following logstash files, for input and output, that you will need to modify for your environment:\n{formatted_filenames}")

def script_usage():
    ran_script_name = sys.argv[0]
    usage = f'''Usage Examples:
    # Run the script
    {ran_script_name}
    # Build logstash config directory as a single configuration that can be used in Logstash X-Pack Central Management from within Kibana.
    # saves the generated configuration into the directory with the file name 'all_logstash_config_for_xpack_mgmt.conf'
    {ran_script_name} --build-logstash-xpack-mgmt -f "/path/to_last_run_directory"
    # Change the default git repostiory
    {ran_script_name} --git-repository=brasitech"
    # Change the default git repostiory and branch
    {ran_script_name} --git-repository=brasitech --git-branch=main"
    '''
    return usage

def parse_args():
    # Parse command line arguments

    parser = argparse.ArgumentParser( description=script_description, formatter_class=argparse.RawTextHelpFormatter, epilog=script_usage() )
    parser.add_argument(
        '-v', '--version', action='version', version='%(prog)s {version}'.format(version=script_version)
    )
    parser.add_argument( '--no-color', action='store_true', help='Disable colors for output/logging.' )
    parser.add_argument( '--debug', action='store_true', help='Enable debug level logging.' )
    parser.add_argument(
        '--es-default-timeout=', dest='es_default_timeout', type=int, required=False, default=es_default_timeout,
        help='Timeout waiting for the connection to the elasticsearch.\ndefault: %(default)s'
    )
    parser.add_argument(
        '--es-default-retry=', dest='es_default_retry', type=int, required=False, default=es_default_retry,
        help='Number of times to retry a connection to the elasticsearch.\ndefault: %(default)s'
    )
    parser.add_argument(
        '--git-repository', dest='git_repository', type=str, required=False, default=git_repository,
        help='Github Repository.\ndefault: %(default)s'
    )
    parser.add_argument(
        '--git-branch', dest='git_branch', type=str, required=False, default=git_branch,
        help='Github Branch.\ndefault: %(default)s'
    )
    parser.add_argument(
        '--build-logstash-xpack-mgmt', dest='build_logstash_xpack_mgmt', action='store_true', required=False,
        help='Build logstash config directory as a single configuration that can be used in Logstash X-Pack Central Management from within Kibana.'
    )
    parser.add_argument(
        '-f', '--final-config-dir', dest='final_config_dir', type=arg_path_and_exists, required=False,
        help='Build logstash config directory as a single configuration that can be used in Logstash X-Pack Central Management from within Kibana.'
    )
    return parser.parse_args()

if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nInstallation aborted.")
        sys.exit(1)
else:
    main()
