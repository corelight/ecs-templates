#!/usr/bin/env python3

import logging
from datetime import datetime
import shutil
import requests
from urllib3.exceptions import InsecureRequestWarning
import time
import sys
import zipfile
import os
import random
import subprocess
import getpass
import errno
import re
from urllib.parse import urlparse
import urllib3
from urllib3.exceptions import InsecureRequestWarning, HTTPError

git_fork = "brasitech"

# Script Version
script_version = '2023102201'
# Default Variables
git_logstash_repo = f"https://github.com/{git_fork}/ecs-logstash-mappings/archive/refs/heads/Dev.zip"
git_logstash_sub_dir = "pipeline"
git_ingest_repo = f"https://github.com/{git_fork}/ecs-mapping/archive/refs/heads/dev.zip"
git_ingest_sub_dir = "automatic_install"
git_templates_repo = f"https://github.com/{git_fork}/ecs-templates/archive/refs/heads/dev.zip"
git_templates_sub_dir = "templates"
git_example_logstash_pipeline_root_dir = "/etc/logstash/conf.d"
git_example_logstash_pipeline_sub_dir = "CorelightPipelines"
git_example_logstsh_pipeline_dir = os.path.join(git_example_logstash_pipeline_root_dir, git_example_logstash_pipeline_sub_dir)
logstash_input_choices = [ 'tcp', 'tcp_ssl', 'kafka', 'hec', 'udp' ]
logstash_elasticsearch_output_file = "9940-elasticsearch-corelight_zeek-datastream-output.conf.disabled"
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

# Set up logging
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
    'DEBUG': COLORS['OKCYAN'],
    'INFO': COLORS['OKGREEN'],
    'WARNING': COLORS['WARNING'],
    'ERROR': COLORS['FAIL'],
    'CRITICAL': COLORS['BOLD'] + COLORS['FAIL']
}
class ColoredFormatter(logging.Formatter):
    def format(self, record, *args, **kwargs):
        log_message = super().format(record, *args, **kwargs)
        return LOG_COLORS.get(record.levelname, '') + log_message + COLORS['ENDC']
#logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = ColoredFormatter("%(levelname)s: %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)



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
        print("Invalid response")

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
            val = int(input(f"\n{question}. Default: '{default}': "))
            if not val:
                return default
            else:
                return val
        except ValueError:
            print("Invalid response, please enter a number")

def check_request_status_code(responseObj, code=None):
    if not code:
        code = responseObj.status_code
    if code == 200:
        pass
    elif 400 <= code <= 599:
        logger.error(responseObj.json())
    else:
        code = None
        logger.error(f"No status code found for {responseObj}")
    return code

def test_connection(session, baseURI):
    testUri = "/"
    uri = f'{baseURI}{testUri}'
    try:
        response = session.get(uri, timeout=5)
        check_status_code = check_request_status_code(response)
        response.raise_for_status()
    except requests.exceptions.SSLError as e:
        if "SSL: CERTIFICATE_VERIFY_FAILED" in str(e):
            logger.warning(f"SSL Error: {e}")
            return "prompt_ignore_cert"
        else:
            raise
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logger.warning(f"Authentication Error: {e}")
            return "prompt_auth"
        else:
            logger.error(f"HTTP Error: {e}")
            raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Request Error: {e}")
        raise

def es_export_to_elastic(session, baseURI, filepath, filename, path, retry=2, timeout=10):
    try:
        with open(filepath) as f:
            postData = f.read()
    except FileNotFoundError:
        logger.error(f"Error: File {filepath} not found")
        return

    uri = f'{baseURI}{path}{filename}'
    response = None
    for i in range(retry):
        response = session.put(uri, data=postData, timeout=timeout)
        response_code = response.status_code
        response_text = response.text
        check_status_code = check_request_status_code(response, code=response_code)
        if check_status_code == 200:
            logger.info(f"{filename} uploaded successfully")
            return
        elif check_status_code in (400, 409):
            logger.error(f"Error uploading '{filename}' to '{uri}' with status code '{response_code}' and response '{response_text}'")
        else:
            logger.error(f"Error uploading. '{filename}' to '{uri}' with status code '{response_code}' and response '{response_text}'")

def get_elasticsearch_connection_config():
    """Return a baseURI and session"""
    ignoreCertErrors = False
    use_https = False
    while True:
        baseURI = input("\nEnter the Elasticsearch host including whether http or https and the port (ie: the full URL, http://somedomain:9200 or https://someip:9200 or https://somedomain:9200)\n: ")
        if not baseURI:
            print("Cannot be empty. Please try again.")
            continue
        parsed_baseURI = urlparse( baseURI )
        # Catch common errors
        if not (baseURI.startswith("http://") or baseURI.startswith("https://") ):
            print("Must include http:// or https://. Please try again.")
            continue
        # Determine if a port was entered
        if not parsed_baseURI.port:
            print("No port was entered, please try again and specify the port even if port 443 or 80")
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
                logger.error(f"Failed to verify SSL to the Elasticsearch connection with baseURI: {baseURI}")
                sys.exit(1)
        elif reprompt == "prompt_auth":
            auth = prompt_for_es_user_and_password(try_again=True)
            if auth and auth[ 0 ] and auth[ 1 ]:
                s.auth = (auth[ 0 ], auth[ 1 ])
            else:
                logger.error(f"Failed to authenticate the Elasticsearch connection with baseURI: {baseURI}")
                sys.exit(1)
        else:
            break

    #baseURI = f"{proto}://{ipHost}:{port}"
    logger.info(f"Successfully configured Elasticsearch connection with baseURI: {baseURI}")
    return baseURI, s

def prompt_for_es_ignore_certificate_errors(try_again=False):
    if not try_again:
        ignore_cert_errors = input_bool("Do you want to ignore certificate errors?", default=True)
    else:
        ignore_cert_errors = input_bool("SSL Certificate ERROR ocurred. Do you want to try again and ignore certificate errors?", default=None)
    return ignore_cert_errors

def prompt_for_es_user_and_password(try_again=False):
    if not try_again:
        auth = input_bool("Do you want to use user and password authentication?", default=None)
    else:
        auth = input_bool("Authentication failed. Do you want to try to enter the username and password again?", default=None)
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
            logger.info(f"Successfully unzipped and removed Git file {fname} to: {git_unzip_dir_name}")
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
    final_dir = src
    if sub_dir and not final_dir.endswith(sub_dir):
        final_dir = os.path.join(final_dir, sub_dir)
    try:
        if os.path.exists(dest):
            if os.path.exists(final_dir) and error_on_overwrites:
                logger.error(f"The path {final_dir} already exists. Please select the update operation.")
                raise ValueError(f"The path {final_dir} already exists. Please select the update operation.")
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
                logger.info(f"Files sucessfully copied to {final_dir}.")
        else:
            create_dir = input_bool(f"The path {dest} does not exist. Would you like to create it?", default=True)
            if create_dir:
                os.makedirs(dest)
                copy_configs(src,final_dir, sub_dir=sub_dir, error_on_overwrites=error_on_overwrites, ignore_file_extensions=ignore_file_extensions)
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
    except Exception as e:
        logger.error(f"Error occurred while enabling {ingest_type} {e}")
        raise ValueError(f"Error occurred while enabling {ingest_type} {e}")

def replace_var_in_directory(directory, replace_var="VAR_CORELIGHT_INDEX_STRATEGY", replace_var_with=None):
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
            logger.debug(f"Did not find {replace_var} in {directory}")
        else:
            logger.debug(f"Successfully replaced {replace_var} with {replace_var_with} {replaced_var_count} times in {sorted(set(replaced_var_files))}")

def es_export_upload_file(session, baseURI, uri_path, source_dir=None, human_path_name=None, retry=2,timeout=10):
    """Upload files to Elasticsearch. Removes the file extension (only if '.json') from the filename and uses the remaining as the name in Elasticsearch."""
    if source_dir and os.path.isdir(source_dir):
        logger.info(f"Uploading {human_path_name} files from {source_dir}")
        for root, dirs, files in os.walk( source_dir ):
            for filename in files:
                # Set the full path variable
                filePath = os.path.join( root, filename )
                filename_without_extension = os.path.splitext( filename )[ 0 ]
                extension = os.path.splitext( filename )[ 1 ]
                es_export_to_elastic( session, baseURI, filePath, filename_without_extension, uri_path, retry=2, timeout=10 )
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
            es_export_upload_file( session, baseURI, "/_component_template/", source_dir=source_dir, human_path_name=human_path_name, retry=2, timeout=10 )
            # ILM Policies
            source_dir = os.path.join( final_templates_dir, "ilm_policy" )
            es_export_upload_file( session, baseURI, "/_ilm/policy/", source_dir=source_dir, human_path_name=human_path_name,  retry=2, timeout=10 )
            human_path_name = "ilm policy"
            # Index Templates
            source_dir = os.path.join( final_templates_dir, "index_template" )
            es_export_upload_file( session, baseURI, "/_index_template/", source_dir=source_dir, human_path_name=human_path_name,  retry=2, timeout=10 )
            human_path_name = "index template"

        else: # Unsupported index strategy
            logger.error(f"Unsupported index strategy: {VAR_CORELIGHT_INDEX_STRATEGY}")
    # Ingest Pipelines
    if pipeline_type == 'ingest':
        source_dir = final_pipelines_dir
        human_path_name = "ingest pipeline"
        es_export_upload_file( session, baseURI, "/_ingest/pipeline/", source_dir=source_dir,  human_path_name=human_path_name,  retry=2, timeout=10 )

def elasticDel(session, baseURI, pipeline, retry=2): #TODO: Keep Or Not
    """
    Delete an Elasticsearch ingest pipeline or enrich policy.

    Args:
        session: requests.Session object
        baseURI: str, Elasticsearch base URI
        pipeline: str, name of the pipeline or policy to delete
        retry: int, number of times to retry the request if it fails

    Returns:
        int, HTTP status code of the response
    """
    uri = baseURI + "/_ingest/pipeline/" + pipeline
    if pipeline.endswith("-policy"):
        uri = baseURI + "/_enrich/policy/" + pipeline

    print("Deleting URI = %s" % uri)

    for i in range(retry):
        response = session.delete(uri, timeout=5)
        check_status_code = check_request_status_code(response)
        if check_status_code == 200:
            logger.info(f"{pipeline} deleted successfully")
            return check_status_code
        elif check_status_code in (400, 404):
            logger.warning(f"Error deleting {pipeline} status code {check_status_code}")
        else:
            logger.error(f"Error deleting {pipeline} status code {check_status_code}")
            logger.error(f"URI = {uri}")
            #sys.exit(1)

    logger.error(f"Failed to delete {pipeline} after {retry} attempts")
    #sys.exit(1)
    #END# #TODO: Keep Or Not #END#

def main():
    create_es_connection = False
    dry_run = False
    # Final config directory
    Final_Config_Dir = os.path.join( Config_Dir, "last_run" )
    Final_Pipelines_Dir = os.path.join( Final_Config_Dir,  "pipelines" )
    Final_Templates_Dir = os.path.join( Final_Config_Dir, "templates" )
    Previous_Config_Dir = os.path.join( Config_Dir, "previous", dir_time )

    # Prompt user if they want to use configs from last run, if they exist
    use_last_run = input_bool(f"Would you like to use the configs from the last run?", default=False)
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
        dry_run = input_bool(f"Is this a dry run? No changes will be installed/uploaded.", default=False)
        install_templates = input_bool(f"Will you be installing Elasticsearch templates, mappings, and settings? Recommended with any updates.", default=True)
        pipeline_type = input(f"\nWill you be installing Pipelines? Ingest Pipelines, Logstash Pipelines, or no (Enter 'ingest'/'i', 'logstash'/'l', or 'no'/'n'/'none'): ").strip("'").strip().lower()
        while pipeline_type.lower() not in ['ingest', 'i', 'logstash', 'l', 'no', 'n']:
            pipeline_type = input(f"Invalid input. Please enter one of:"
                                  f"\n'ingest' or 'i' for Ingest Pipelines"
                                  f"\n'logstash' or 'l' for Logstash Pipelines"
                                  f"\n'no' or 'n' for skipping installation of pipelines"
                                  f"\n: ")
        if pipeline_type == 'i':
            create_es_connection = True
            pipeline_type = 'ingest'
        elif pipeline_type == 'l':
            pipeline_type = 'logstash'
        elif pipeline_type == 'n':
            pipeline_type = 'no'
        VAR_CORELIGHT_INDEX_STRATEGY = input(f"\nWhat index strategy will you be using? (Enter 'datastream'/'d', 'legacy'/'l'): ").strip().lower()
        while VAR_CORELIGHT_INDEX_STRATEGY.strip("'").strip().lower() not in ['datastream', 'd']:#, 'legacy', 'l']:
            VAR_CORELIGHT_INDEX_STRATEGY = input(f"Invalid input. Please enter one of:"
                                                 f"\n'datastream' or 'd' for datastream index strategy"
                                                 #f"\n'legacacy' or 'l' for legacy index strategy"
                                                 f"\n: ")
        if VAR_CORELIGHT_INDEX_STRATEGY == "datastream" or "d":
            VAR_CORELIGHT_INDEX_STRATEGY = "datastream"
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
            #elif VAR_CORELIGHT_INDEX_STRATEGY == "legacy":
            #    templates_sub_dir = "legacy"
            else:
                templates_sub_dir = ""
            templates_source_directory = os.path.join(templates_source_directory, templates_sub_dir)
            logger.info(f"Using {templates_source_directory} as the source for the templates.")

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
            logger.info(f"Using {pipeline_source_directory} as the source for the {pipeline_type} pipelines.")

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
                    input_type = input(f"Invalid input. Please enter one of {logstash_input_choices}: ")
                keep_raw = input_bool( "Do you want to keep the raw message? (This will increase storage space but is useful in certain environments for data integrity or troubleshooting)", default=False )
                enable_ls_input( source_dir=pipeline_source_directory, ingest_type=input_type, raw=keep_raw, destination_dir=Final_Pipelines_Dir)

            # Ingest Pipelines Specifics
            elif pipeline_type == 'ingest':
                pass

            # For everything
            USE_CUSTOM_INDEX_NAMES = input_bool( f"\nDo you want to use custom index names?",default=False )
            if USE_CUSTOM_INDEX_NAMES:
                # Protocol Log
                VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG = input_string(question=f"Enter the Index Name Type for Protocol Logs", default=f"logs")
                VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG = input_string(question=f"Enter the Index Dataset for Protocol Logs", default=f"corelight")
                VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG = input_string(question=f"Enter the Index Namespace for Protocol Logs", default=f"default")
                # Unknown Protocol Log
                VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG_UNKNOWN = input_string(question=f"Enter the Index Name Type for Protocol Logs Unknown", default=f"logs")
                VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG_UNKNOWN = input_string(question=f"Enter the Index Dataset for Protocol Logs Unknown", default=f"corelight")
                VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PROTOCOL_LOG_UNKNOWN = input_string(question=f"Enter the Index Dataset suffix for Protocol Logs Unknown", default=f"unknown")
                VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG_UNKNOWN = input_string(question=f"Enter the Index Namespace for Protocol Logs Unknown", default=f"default")
                # Metrics and Stats
                VAR_CORELIGHT_INDEX_NAME_TYPE_NON_PROTOCOL_LOG = input_string(question=f"Enter the Index Name Type for Metrics and Stats Logs", default=f"zeek")
                VAR_CORELIGHT_INDEX_DATASET_PREFIX_NON_PROTOCOL_LOG = input_string(question=f"Enter the Index Dataset for Metrics and Stats Logs", default=f"corelight")
                VAR_CORELIGHT_INDEX_NAMESPACE_NON_PROTOCOL_LOG = input_string(question=f"Enter the Index Namespace for Metrics and Stats Logs", default=f"default")
                # Parse_Failures
                VAR_CORELIGHT_INDEX_NAME_TYPE_PARSE_FAILURES = input_string(question=f"Enter the Index Name Type for Parse Failures", default=f"parse_failures")
                VAR_CORELIGHT_INDEX_DATASET_PREFIX_PARSE_FAILURES = input_string(question=f"Enter the Index Dataset for Parse Failures", default=f"corelight")
                VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PARSE_FAILURES = input_string(question=f"Enter the Index Dataset suffix for Parse Failures", default=f"failed")
                VAR_CORELIGHT_INDEX_NAMESPACE_PARSE_FAILURES = input_string(question=f"Enter the Index Namespace for Parse Failures", default=f"default")
            else:
                # Protocol Log
                VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG = "logs"
                VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG = "corelight"
                VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG = "default"
                # Unknown Protocol Log
                VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG_UNKNOWN = "logs"
                VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG_UNKNOWN = "corelight"
                VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PROTOCOL_LOG_UNKNOWN = "unknown"
                VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG_UNKNOWN = "default"
                # Metrics and Stats
                VAR_CORELIGHT_INDEX_NAME_TYPE_NON_PROTOCOL_LOG = "zeek"
                VAR_CORELIGHT_INDEX_DATASET_PREFIX_NON_PROTOCOL_LOG = "corelight"
                VAR_CORELIGHT_INDEX_NAMESPACE_NON_PROTOCOL_LOG = "default"
                # Parse_Failures
                VAR_CORELIGHT_INDEX_NAME_TYPE_PARSE_FAILURES = "parse_failures"
                VAR_CORELIGHT_INDEX_DATASET_PREFIX_PARSE_FAILURES = "corelight"
                VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PARSE_FAILURES = "failed"
                VAR_CORELIGHT_INDEX_NAMESPACE_PARSE_FAILURES = "default"


            # Replace variables
            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_STRATEGY", replace_var_with=VAR_CORELIGHT_INDEX_STRATEGY )

            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG", replace_var_with=VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG)
            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG", replace_var_with=VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG)
            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG", replace_var_with=VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG)

            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG_UNKNOWN", replace_var_with=VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG_UNKNOWN)
            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG_UNKNOWN", replace_var_with=VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG_UNKNOWN)
            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PROTOCOL_LOG_UNKNOWN", replace_var_with=VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PROTOCOL_LOG_UNKNOWN)
            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG_UNKNOWN", replace_var_with=VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG_UNKNOWN)

            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_NAME_TYPE_NON_PROTOCOL_LOG", replace_var_with=VAR_CORELIGHT_INDEX_NAME_TYPE_NON_PROTOCOL_LOG)
            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_DATASET_PREFIX_NON_PROTOCOL_LOG", replace_var_with=VAR_CORELIGHT_INDEX_DATASET_PREFIX_NON_PROTOCOL_LOG)
            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_NAMESPACE_NON_PROTOCOL_LOG", replace_var_with=VAR_CORELIGHT_INDEX_NAMESPACE_NON_PROTOCOL_LOG)

            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_NAME_TYPE_PARSE_FAILURES", replace_var_with=VAR_CORELIGHT_INDEX_NAME_TYPE_PARSE_FAILURES)
            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_DATASET_PREFIX_PARSE_FAILURES", replace_var_with=VAR_CORELIGHT_INDEX_DATASET_PREFIX_PARSE_FAILURES)
            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PARSE_FAILURES", replace_var_with=VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PARSE_FAILURES)
            replace_var_in_directory( Final_Pipelines_Dir, replace_var="VAR_CORELIGHT_INDEX_NAMESPACE_PARSE_FAILURES", replace_var_with=VAR_CORELIGHT_INDEX_NAMESPACE_PARSE_FAILURES)

        if use_templates:
            if not 'USE_CUSTOM_INDEX_NAMES' in locals():
                USE_CUSTOM_INDEX_NAMES = input_bool( f"\nDo you want to use custom index template settings?",default=False )
            if USE_CUSTOM_INDEX_NAMES:
                VAR_CORELIGHT_INDEX_PATTERN_MAIN_LOGS = input_string(question=f"Enter the Index Template Pattern for Main Logs. Qoute input, seperate list with commas", default=f'"logs-corelight.*"')
                VAR_CORELIGHT_INDEX_PRIORITY_MAIN_LOGS = input_string(question=f"Enter the Index Template Priority for Main Logs", default=f"901")
                VAR_CORELIGHT_INDEX_PATTERN_METRICS_AND_STATS_LOGS = input_string(question=f"Enter the Index Template Pattern for Metrics and Stats Logs. Qoute input, seperate list with commas", default=f'"zeek-corelight.metrics-*", "zeek-corelight.netcontrol-*", "zeek-corelight.stats-*", "zeek-corelight.system-*"')
                VAR_CORELIGHT_INDEX_PRIORITY_METRICS_AND_STATS_LOGS = input_string(question=f"Enter the Index Template Priority for Metrics and Stats Logs", default=f"901")
                VAR_CORELIGHT_INDEX_PATTERN_PARSE_FAILURES_LOGS  = input_string(question=f"Enter the Index Template Pattern for Parse Failures Logs. Qoute input, seperate list with commas", default=f'"parse_failures-corelight.*"')
                VAR_CORELIGHT_INDEX_PRIORITY_PARSE_FAILURES_LOGS = input_string(question=f"Enter the Index Template Priority for Parse Failures Logs", default=f"901")
            else:
                VAR_CORELIGHT_INDEX_PATTERN_MAIN_LOGS = '"logs-corelight.*"'
                VAR_CORELIGHT_INDEX_PRIORITY_MAIN_LOGS = '901'
                VAR_CORELIGHT_INDEX_PATTERN_METRICS_AND_STATS_LOGS = '"zeek-corelight.metrics-*", "zeek-corelight.netcontrol-*", "zeek-corelight.stats-*", "zeek-corelight.system-*"'
                VAR_CORELIGHT_INDEX_PRIORITY_METRICS_AND_STATS_LOGS = '901'
                VAR_CORELIGHT_INDEX_PATTERN_PARSE_FAILURES_LOGS = '"parse_failures-corelight.*"'
                VAR_CORELIGHT_INDEX_PRIORITY_PARSE_FAILURES_LOGS = '901'

            # Replace variables
            replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CORELIGHT_INDEX_PATTERN_MAIN_LOGS", replace_var_with=VAR_CORELIGHT_INDEX_PATTERN_MAIN_LOGS )
            replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CORELIGHT_INDEX_PRIORITY_MAIN_LOGS", replace_var_with=VAR_CORELIGHT_INDEX_PRIORITY_MAIN_LOGS )
            replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CORELIGHT_INDEX_PATTERN_METRICS_AND_STATS_LOGS", replace_var_with=VAR_CORELIGHT_INDEX_PATTERN_METRICS_AND_STATS_LOGS )
            replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CORELIGHT_INDEX_PRIORITY_METRICS_AND_STATS_LOGS", replace_var_with=VAR_CORELIGHT_INDEX_PRIORITY_METRICS_AND_STATS_LOGS )
            replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CORELIGHT_INDEX_PATTERN_PARSE_FAILURES_LOGS", replace_var_with=VAR_CORELIGHT_INDEX_PATTERN_PARSE_FAILURES_LOGS )
            replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CORELIGHT_INDEX_PRIORITY_PARSE_FAILURES_LOGS", replace_var_with=VAR_CORELIGHT_INDEX_PRIORITY_PARSE_FAILURES_LOGS )

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
        logger.info(f"A copy has been saved to {Previous_Config_Dir}")

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

if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nInstallation aborted.")
        sys.exit(1)
else:
    main()
