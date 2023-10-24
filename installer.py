#!/usr/bin/env python3

import logging
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
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Script Version
script_version = '2023102201'
# Default Variables
git_logstash_repo = "https://github.com/corelight/ecs-logstash-mappings/archive/refs/heads/Dev.zip"
git_logstash_sub_dir = "pipeline"
git_ingest_repo = "https://github.com/corelight/ecs-mapping/archive/refs/heads/dev.zip"
git_ingest_sub_dir = "automatic_install"
git_templates_repo = "https://github.com/corelight/ecs-templates/archive/refs/heads/dev.zip"
git_templates_sub_dir = "templates"
git_example_logstash_pipeline_root_dir = "/etc/logstash/conf.d"
git_example_logstash_pipeline_sub_dir = "CorelightPipelines"
git_example_logstsh_pipeline_dir = os.path.join(git_example_logstash_pipeline_root_dir, git_example_logstash_pipeline_sub_dir)
logstash_input_choices = [ 'tcp', 'tcp_ssl', 'kafka', 'hec', 'udp' ]
logstash_elasticsearch_output_file = "9940-elasticsearch-corelight_zeek-datastream-output.conf.disabled"
# General
#version = script_version
script_name = os.path.basename( __file__ )
script_dir = os.path.realpath( os.path.join( __file__, '..' ) )
Script_UID = str( random.randint( 1000000000, 9999999999 ) )  # Random 10 digit number for correlating a specific run of the script to the logs.
# Main Output Directory
Script_Output_Dir = os.path.realpath( os.path.join( script_dir, "z_installer" ) )
# Temp Output Directory
Temp_Output_Dir = os.path.realpath( os.path.join( Script_Output_Dir, "temp" ) )
# Final config directory
Final_Config_Dir = os.path.realpath( os.path.join( Script_Output_Dir, "final_config" ) )
Final_Pipeline_Dir = os.path.realpath( os.path.join( Final_Config_Dir, "pipelines" ) )
Final_Templates_Dir = os.path.realpath( os.path.join( Final_Config_Dir, "templates" ) )

# Create the output directories if they don't exist
try:
    os.makedirs(Script_Output_Dir)
except OSError as e:
    if e.errno != errno.EEXIST:
        raise
try:
    os.makedirs(Temp_Output_Dir)
except OSError as e:
    if e.errno != errno.EEXIST:
        raise
# Clean final config directory before use
try:
    shutil.rmtree(Final_Config_Dir) # Delete the directory
except FileNotFoundError:
    pass
# Recreate the directories
try:
    os.makedirs(Final_Config_Dir)
    os.makedirs(Final_Pipeline_Dir)
    os.makedirs(Final_Templates_Dir)
except OSError as e:
    print(f"Unable to create necessary directories: {e}")

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



def checkRequest(responseObj):
    code = responseObj.status_code
    if code == 200:
        return 200

    if 400 <= code <= 500:
        print(responseObj.json())
        time.sleep(5)
        return code
    return code


def input_int(question):
    while True:
        try:
            return int(input(question + ": "))
        except ValueError:
            print("Invalid response")

def testConnection(session, baseURI):
    testUri = "/_cat/indices?v&pretty"
    uri = baseURI + testUri
    response = session.get(uri, timeout=5)
    checkRequest(response)
    response.raise_for_status()

def updateLogstash(directory):
    source = "./ecs-logstash-mappings-Dev/pipeline/"
    tcp = ""
    path = directory + "/CorelightPipelines"
    if os.path.exists(directory):
        fileList=os.listdir(source)
        for filename in fileList:
            shutil.copy2(os.path.join(source,filename), path)

def postPorcessing(logstashLocation, datastream, logstashVersion):
    ls_pipeline_install_dir = logstashLocation + "/CorelightPipelines/"
    if logstashVersion:
        sedCommand = 'sed -i "s/#ecs_compatibility =>/ecs_compatibility =>/" ' + ls_pipeline_install_dir + '/*.conf'
        subprocess.call([sedCommand],shell=True)
    if datastream:
        filename = ls_pipeline_install_dir + "0101-corelight-ecs-user_defined-set_indexing_strategy-filter.conf.disabled"
        f = open(filename)
        ds = f.read()
        if '=> "VAR_CORELIGHT_INDEX_STRATEGY"' in ds:
            dsEnabled = ds.replace('=> "VAR_CORELIGHT_INDEX_STRATEGY"', '=> "datastream"')
            f.close()
            dsOut = ls_pipeline_install_dir + "0101-corelight-ecs-user_defined-set_indexing_strategy-filter.conf"
            f = open(dsOut, "wt")
            f.write(dsEnabled)
            f.close()

def exportToElastic(session, baseURI, filePath, pipeline, path, retry=4):
    filename = filePath + pipeline
    if pipeline != "zeek-enrichment-conn-policy/_execute":
        try:
            with open(filename) as f:
                postData = f.read()
        except FileNotFoundError:
            logger.error(f"Error: File {filename} not found")
            return

    uri = baseURI + path + pipeline
    for i in range(retry):
        response = session.put(uri, data=postData, timeout=10)
        response = checkRequest(response)
        if response in (400, 409):
            logger.warning(f"Error uploading {pipeline} status code {response}")
        elif response == 200:
            logger.info(f"{pipeline} uploaded successfully")
            return
        else:
            logger.error(f"Error uploading {pipeline} status code {response}")
            logger.error(f"URI = {uri}")
            sys.exit(1)


def elasticDel(session, baseURI, pipeline, retry=4):
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
        result = checkRequest(response)
        if result == 200:
            logger.info(f"{pipeline} deleted successfully")
            return result
        elif result in (400, 404):
            logger.warning(f"Error deleting {pipeline} status code {result}")
        else:
            logger.error(f"Error deleting {pipeline} status code {result}")
            logger.error(f"URI = {uri}")
            #sys.exit(1)

    logger.error(f"Failed to delete {pipeline} after {retry} attempts")
    #sys.exit(1)

def get_config():
    """Return a baseURI and session"""

    while True:
        ipHost = input("Enter the hostname or IP of your Elasticsearch cluster: ")
        if not ipHost:
            print("Hostname or IP cannot be empty. Please try again.")
            continue
        break

    while True:
        try:
            port = int(input("Enter the port number of your Elasticsearch cluster: "))
            if not (0 <= port <= 65535):
                print("Invalid port number. Please enter a valid integer between 0 and 65535.")
                continue
            break
        except ValueError:
            print("Invalid port number. Please enter a valid integer.")

    s = requests.Session()
    s.headers={'Content-Type': 'application/json'}

    while True:
        auth = input_bool("Do you want to use user and password authentication?", default=None)
        if auth:
            user = input("Enter the username: ")
            password = getpass.getpass("Enter the password: ")
            s.auth = (user, password)
            break
        else:
            break

    while True:
        secure = input_bool("Do you want to use https?", default=None)
        if secure:
            proto = "https"
            ignoreCertErrors = input_bool("Do you want to ignore certificate errors? (y/n): ", default=True)
            if ignoreCertErrors:
                s.verify = False
            break
        else:
            proto = "http"
            break

    baseURI = f"{proto}://{ipHost}:{port}"
    logger.info(f"Successfully configured Elasticsearch connection with baseURI: {baseURI}")
    return baseURI, s

def export_templates(session, baseURI, source, path, retry=4):
    """Export templates to ElasticSearch"""
    fileList = os.listdir(source)
    for filename in fileList:
        filepath = os.path.join(source, filename)
        if os.path.isfile(filepath):
            exportToElastic(session, baseURI, source, filename, path, retry=retry)
        else:
            logger.warning(f"{filepath} is not a file. Skipping export.")

def datastreams(session, baseURI, updateTemplates=False):
    """Export data stream templates to ElasticSearch"""
    source = "./templates-component/data_stream/"
    component_templates = source + "components_template/"
    ilm_templates = source + "ilm_policy/"
    index_templates = source + "index_template/"

    # Export component templates
    export_templates(session, baseURI, component_templates, "/_component_template/", retry=4)

    # Export ILM policies if updateTemplates is False
    if not updateTemplates:
        export_templates(session, baseURI, ilm_templates, "/_ilm/policy/", retry=4)

    # Export index templates
    export_templates(session, baseURI, index_templates, "/_index_template/", retry=4)

def component( session, baseURI, updateTemplates ):
    source = "./templates-component/non_data_stream/"
    component = source + "component_template/"
    ilm = source + "ilm_policy/"
    index = source + "index_template/"
    fileList=os.listdir(component)
    for filename in fileList:
         exportToElastic(session, baseURI, component,filename, "/_component_template/", retry=4)
    if not updateTemplates:
        fileList=os.listdir(ilm)
        for filename in fileList:
            exportToElastic(session, baseURI, ilm, filename, "/_ilm/policy/", retry=4)
    fileList=os.listdir(index)
    for filename in fileList:
        exportToElastic(session, baseURI, index, filename, "/_index_template/", retry=4)

def index(session, baseURI, logstash,updateTemplates):
    source = "./templates-component/templates-legacy/"
    fileList=os.listdir(source)
    for filename in fileList:
        exportToElastic(session, baseURI, source, filename, "/_template/", retry=4)

    if not logstash:
        fileList=os.listdir(ingest)
        for filename in fileList:
                exportToElastic(session, baseURI, ingest, filename, "/_template/", retry=4)

def uploadIngestPipelines(session,baseURI):
    source = "./ecs-mapping-master/automatic_install/"
    fileList=os.listdir(source)
    for filename in fileList:
        if "deprecated" not in filename:
            exportToElastic(session, baseURI, source, filename, "/_ingest/pipeline/", retry=4)


def input_bool(question, default=None):
    prompt = " [Y/n]:" if default else " [y/N]:"
    while True:
        val = input(f"\n{question} {prompt}").strip().lower()
        if not val:
            return default
        if val in ('y', 'yes'):
            return True
        if val in ('n', 'no'):
            return False
        print("Invalid response")

def unzipGit(filename):
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

def source_repository(name, repo_type, proxy=None, verify=None):
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
            with requests.get(name, proxies=proxies, stream=True, verify=verify) as r:
                with open(filename, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
            logger.info(f"Successfully downloaded repository: {name}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error occurred while downloading repository: {e}")
            raise ValueError(f"Error occurred while downloading repository: {e}")
        # Unzip the repository
        name = unzipGit(filename)
        return name
    # Zip
    elif name.endswith(".zip") and os.path.isfile(name):
        name = unzipGit(name)
        return name
    # Path
    elif os.path.exists(name):
        return name
    else:
        logger.error(f"Invalid repository name or path for {name}")
        raise ValueError(f"Invalid repository name or path for {name}")


def copy_configs(source_dir=None, dest_dir=None, sub_dir=None, error_on_overwrites=False, ignore_file_extensions=None):
    final_dir = dest_dir
    if sub_dir and not final_dir.endswith(sub_dir):
        final_dir = os.path.join(final_dir, sub_dir)
    try:
        if os.path.exists(dest_dir):
            if os.path.exists(final_dir) and error_on_overwrites:
                logger.error(f"The path {final_dir} already exists. Please select the update operation.")
                raise ValueError(f"The path {final_dir} already exists. Please select the update operation.")
            else:
                # Check if directory already exists
                # If it does then copy the contents within the source_dir into final_dir
                if os.path.exists( final_dir ):
                    for root, dirs, files in os.walk(source_dir):
                        for filename in files:
                            fname = os.path.splitext(filename)[0]
                            fextension = os.path.splitext(filename)[1]
                            if not ignore_file_extensions:
                                file_path = os.path.join(root, filename)
                                shutil.copy(file_path, final_dir)
                            if ignore_file_extensions and not fextension in ignore_file_extensions:
                                file_path = os.path.join(root, filename)
                                shutil.copy(file_path, final_dir)
                else:
                    shutil.copytree(source_dir, final_dir)
                logger.info(f"Files sucessfully copied to {final_dir}.")
        else:
            create_dir = input_bool(f"The path {dest_dir} does not exist. Would you like to create it?", default=True)
            if create_dir:
                os.makedirs(dest_dir)
                copy_configs(source_dir,final_dir)
            else:
                logger.error(f"Installation aborted. The path {dest_dir} does not exist." % dest_dir)
                raise ValueError(f"Installation aborted. The path {dest_dir} does not exist." % dest_dir)
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
        logger.info(f"Successfully enabled {ingest_type} at {dest}") #TODO: tell user to modify at the end
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

        logger.info(f"Successfully replaced {replace_var} with {replace_var_with} {replaced_var_count} times in {sorted(set(replaced_var_files))}")
def main():
    install_templates = input_bool(f"Will you be installing Elasticsearch templates, mappings, and settings? Recommended with any updates.", default=True)
    pipeline_type = input(f"\nWill you be using Ingest Pipelines or Logstash Pipelines? (Enter 'ingest'/'i', 'logstash'/'l', or 'no'/'n'): ").strip().lower()
    while pipeline_type.lower() not in ['ingest', 'i', 'logstash', 'l', 'no', 'n']:
        pipeline_type = input(f"Invalid input. Please enter 'ingest'/'i', 'logstash'/'l', or 'no'/'n': ")
    if pipeline_type == 'i':
        pipeline_type = 'ingest'
    elif pipeline_type == 'l':
        pipeline_type = 'logstash'
    elif pipeline_type == 'n':
        pipeline_type = 'no'
    VAR_CORELIGHT_INDEX_STRATEGY = input(f"\nWhat index strategy will you be using? (Enter 'datastream'/'d', 'legacy'/'l'): ").strip().lower()
    while VAR_CORELIGHT_INDEX_STRATEGY.lower() not in ['datastream', 'd', 'legacy', 'l']:
        VAR_CORELIGHT_INDEX_STRATEGY = input(f"Invalid input. Please enter 'datastream'/'d', 'legacacy'/'l': ")

    use_pipeline = False if pipeline_type == 'no' else True
    use_templates = install_templates

    # - [x] Use proxy ?
    # Templates only ?
    # Logstash or Ingest Pipelines ?
    #
    #  - [ ] finish index variables for ingest pipelines same as logstash
    # a) logstash pipelines
    #  - [x] download or use local
    #  - [x] input config logstash pipelines
    #  - [x] replace variables / input
    #    - [x] input type
    #    - [x] VAR_CORELIGHT_INDEX_STRATEGY
    #  - [ ] config creator for central pipeline management
    # b) ingest pipelines
    #  - [x] download or use local
    #  - [x] var replacement, done since made function universal
    #  - [ ] upload ingest pipelines
    # Elasticsearch templates, mappings, and settings
    #   - [ ] upload templates
    #   - [ ] upload mappings
    #   - [ ] upload settings
    #   - [ ] variable replacements
    #     - [ ] priority
    #     - [ ] index_patterns
    #     - [ ] aliases (maybe)

    if use_templates:
        # Source templates
        # Get source from user
        templates_source = input(f"\nHow will you source the templates?"
                                f"\n  - Download git zip of repository. Requires the full URL. ({git_templates_repo})"
                                f"\n  - Local zip path of a repistory. Requires the full path ending in .zip"
                                f"\n  - Local path or git clone. Requires the full path (default {script_dir})"
                                f"\nEnter the url, path, or press enter for default {script_dir}: ")
        # Use default if no input
        if not templates_source:
            templates_source = script_dir
        if templates_source.startswith('http'):
            proxy = input( f"\nEnter proxy URL if desired (leave empty, press enter, if not using a proxy): " )
            if proxy:
                ignore_proxy_cert_errors = input_bool( f"Do you want to ignore proxy certificate errors?", default=True )
            else:
                ignore_proxy_cert_errors = None
                proxy = None
        else:
            ignore_proxy_cert_errors = None
            proxy = None
        # Set source
        templates_source_directory =  source_repository(templates_source, repo_type="templates", proxy=proxy, verify=not ignore_proxy_cert_errors if ignore_proxy_cert_errors else None)
        templates_source_directory = os.path.join(templates_source_directory, git_templates_sub_dir)
        if VAR_CORELIGHT_INDEX_STRATEGY == "datastream" or "d":
            templates_sub_dir = "component"
        elif VAR_CORELIGHT_INDEX_STRATEGY == "legacy" or "l":
            templates_sub_dir = "legacy"
        else:
            templates_sub_dir = ""
        templates_source_directory = os.path.join(templates_source_directory, templates_sub_dir)
        logger.info(f"Using {templates_source_directory} as the source for the templates.")

        # Copy all sourced files to temporary directory
        copy_configs( source_dir=templates_source_directory, dest_dir=Final_Templates_Dir )
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
                                f"\nEnter the url, path, or press enter for default {git_pipeline_repo}: ")
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
        # Set source
        pipeline_source_directory =  source_repository(pipeline_source, repo_type=pipeline_type, proxy=proxy, verify=not ignore_proxy_cert_errors if ignore_proxy_cert_errors else None)
        pipeline_source_directory = os.path.join(pipeline_source_directory, pipeline_sub_dir)
        logger.info(f"Using {pipeline_source_directory} as the source for the {pipeline_type} pipelines.")

        # Copy all sourced files to temporary directory
        copy_configs( source_dir=pipeline_source_directory, dest_dir=Final_Pipeline_Dir, ignore_file_extensions=['.disabled'] )
        logger.info(f"Using {Final_Pipeline_Dir} as the temporary directory for the {pipeline_type} pipelines.")

        # Logstash Pipelines Specifics
        if pipeline_type == 'logstash':

            # Get specifics and change variables
            #logstashVersion = input_bool( f"\nAre you running Logstash version 8.x or higher?", default=True ) #TODO:keep or not
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
            enable_ls_input( source_dir=pipeline_source_directory, ingest_type=input_type, raw=keep_raw, destination_dir=Final_Pipeline_Dir)

        # Ingest Pipelines Specifics
        elif pipeline_type == 'ingest':
            pass

        # For everything
        USE_CUSTOM_INDEX_NAMES = input_bool( f"\nDo you want to use custom index names?",default=False )
        if USE_CUSTOM_INDEX_NAMES:
            VAR_CORELIGHT_INDEX_PATTERN_MAIN_LOGS = input(f'\nIndex Template Pattern for Main Logs. Qoute input, seperate list with comma ("logs-corelight.*"): ')
            VAR_CORELIGHT_INDEX_PATTERN_METRICS_AND_STATS_LOGS = input(f'\nIndex Template Pattern for Metrics and Stats Logs. ("zeek-corelight.metrics-*", "zeek-corelight.netcontrol-*", "zeek-corelight.stats-*", "zeek-corelight.system-*"): ')
            # Protocol Log
            VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG = input(f"\nIndex Name Type for Protocol Logs. (logs): ")
            VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG = input(f"\nIndex Dataset for Protocol Logs. (corelight): ")
            VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG = input(f"\nIndex Namespace for Protocol Logs. (default): ")
            # Unknown Protocol Log
            VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG_UNKNOWN = input(f"\nIndex Name Type for Protocol Logs Unknown (logs): ")
            VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG_UNKNOWN = input(f"\nIndex Dataset for Protocol Logs Unknown (corelight): ")
            VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PROTOCOL_LOG_UNKNOWN = input(f"\nIndex Dataset suffix for Protocol Logs Unknown (unknown): ")
            VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG_UNKNOWN = input(f"\nIndex Namespace for Protocol Logs Unknown (default): ")
            # Metrics and Stats
            VAR_CORELIGHT_INDEX_NAME_TYPE_NON_PROTOCOL_LOG = input(f"\nIndex Name Type for Metrics and Stats Logs (zeek): ")
            VAR_CORELIGHT_INDEX_DATASET_PREFIX_NON_PROTOCOL_LOG = input(f"\nIndex Dataset for Metrics and Stats Logs(corelight): ")
            VAR_CORELIGHT_INDEX_NAMESPACE_NON_PROTOCOL_LOG = input(f"\nIndex Namespace for Metrics and Stats Logs(default): ")
            # Parse_Failures
            VAR_CORELIGHT_INDEX_NAME_TYPE_PARSE_FAILURES = input(f"\nIndex Name Type for Parse Failures (parse_failures): ")
            VAR_CORELIGHT_INDEX_DATASET_PREFIX_PARSE_FAILURES = input(f"\nIndex Dataset for Parse Failures (corelight): ")
            VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PARSE_FAILURES = input(f"\nIndex Dataset suffix for Parse Failures (failed): ")
            VAR_CORELIGHT_INDEX_NAMESPACE_PARSE_FAILURES = input(f"\nIndex Namespace for Parse Failures (default): ")
        else:
            VAR_CORELIGHT_INDEX_PATTERN_MAIN_LOGS = '"logs-corelight.*"'
            VAR_CORELIGHT_INDEX_PATTERN_METRICS_AND_STATS_LOGS = '"zeek-corelight.metrics-*", "zeek-corelight.netcontrol-*", "zeek-corelight.stats-*", "zeek-corelight.system-*"'
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
        replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CORELIGHT_INDEX_PATTERN_MAIN_LOGS", replace_var_with=VAR_CORELIGHT_INDEX_PATTERN_MAIN_LOGS )
        replace_var_in_directory( Final_Templates_Dir, replace_var="VAR_CORELIGHT_INDEX_PATTERN_METRICS_AND_STATS_LOGS", replace_var_with=VAR_CORELIGHT_INDEX_PATTERN_METRICS_AND_STATS_LOGS )

        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_STRATEGY", replace_var_with=VAR_CORELIGHT_INDEX_STRATEGY )

        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG", replace_var_with=VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG)
        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG", replace_var_with=VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG)
        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG", replace_var_with=VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG)

        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG_UNKNOWN", replace_var_with=VAR_CORELIGHT_INDEX_NAME_TYPE_PROTOCOL_LOG_UNKNOWN)
        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG_UNKNOWN", replace_var_with=VAR_CORELIGHT_INDEX_DATASET_PREFIX_PROTOCOL_LOG_UNKNOWN)
        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PROTOCOL_LOG_UNKNOWN", replace_var_with=VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PROTOCOL_LOG_UNKNOWN)
        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG_UNKNOWN", replace_var_with=VAR_CORELIGHT_INDEX_NAMESPACE_PROTOCOL_LOG_UNKNOWN)

        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_NAME_TYPE_NON_PROTOCOL_LOG", replace_var_with=VAR_CORELIGHT_INDEX_NAME_TYPE_NON_PROTOCOL_LOG)
        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_DATASET_PREFIX_NON_PROTOCOL_LOG", replace_var_with=VAR_CORELIGHT_INDEX_DATASET_PREFIX_NON_PROTOCOL_LOG)
        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_NAMESPACE_NON_PROTOCOL_LOG", replace_var_with=VAR_CORELIGHT_INDEX_NAMESPACE_NON_PROTOCOL_LOG)

        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_NAME_TYPE_PARSE_FAILURES", replace_var_with=VAR_CORELIGHT_INDEX_NAME_TYPE_PARSE_FAILURES)
        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_DATASET_PREFIX_PARSE_FAILURES", replace_var_with=VAR_CORELIGHT_INDEX_DATASET_PREFIX_PARSE_FAILURES)
        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PARSE_FAILURES", replace_var_with=VAR_CORELIGHT_INDEX_DATASET_SUFFIX_PARSE_FAILURES)
        replace_var_in_directory( Final_Pipeline_Dir, replace_var="VAR_CORELIGHT_INDEX_NAMESPACE_PARSE_FAILURES", replace_var_with=VAR_CORELIGHT_INDEX_NAMESPACE_PARSE_FAILURES)

        # Final config placement or upload
        if pipeline_type == 'logstash':
            # Get destination from user
            pipeline_destination_directory = input( f"\nEnter the path to store the Logstash pipeline files in (ie: {git_example_logstsh_pipeline_dir}). Leave blank to skip: " )
            if not pipeline_destination_directory:
                pipeline_destination_directory = Final_Pipeline_Dir
            else:
                copy_configs(source_dir=Final_Pipeline_Dir, dest_dir=pipeline_destination_directory, error_on_overwrites=True )
        elif pipeline_type == 'ingest':
            pass
            #TODO: upload files use Final_Pipeline_Dir


    sys.exit(1)
    #TODO:finish rest of templates and upload

    baseURI, session = get_config()
    testConnection(session, baseURI)

    templateDS = input_bool(f"Will you be using Datastreams?", default=True)
    if templateDS:
        datastreams(session,baseURI)
        if logstash and not updateLogstash:
            postPorcessing(logstash_destination_directory, templateDS, logstashVersion)
    else:
        templateComponent = input_bool(f"Will you be using Component Templates?", default=True)
        if templateComponent:
            component( session, baseURI )
            if logstash and not updateLogstash:
                postPorcessing(logstash_destination_directory, templateDS, logstashVersion)
        else:
            templateLegcy = input_bool(f"Will you be using Legcy Templates? This is not supported on version 8.x and above?", default=False)
            if templateLegcy:
                index(session,baseURI,logstash)
                if logstash and not updateLogstash:
                    postPorcessing(logstash_destination_directory, templateDS, logstashVersion)

if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nInstallation aborted.")
        sys.exit(1)
else:
    main()
