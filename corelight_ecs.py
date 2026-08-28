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
    import errno
    import re
    import json
    from urllib.parse import urlparse
    import urllib3
    from urllib3.exceptions import InsecureRequestWarning, HTTPError
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

logger = logging.getLogger(__name__)

def _ensure_output_dirs():
    os.makedirs(Script_Output_Dir, exist_ok=True)
    os.makedirs(Temp_Output_Dir, exist_ok=True)

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

def get_elasticsearch_connection_config(host, username=None, password=None,
                                         ssl_verify=True, timeout=es_default_timeout, retry=es_default_retry):
    """Pure function: validate host, build authenticated session, test connection.
    Returns (baseURI, session). No prompts.

    Raises ValueError if the host is malformed, SSL verification fails, or authentication fails.
    """
    parsed = urlparse(host)
    if not (host.startswith("http://") or host.startswith("https://")):
        raise ValueError("host must include http:// or https://")
    if not parsed.port:
        raise ValueError("host must include a port (e.g. https://elastic:9200)")

    s = requests.Session()
    s.headers = {'Content-Type': 'application/json'}

    if host.startswith("https://") and not ssl_verify:
        s.verify = False
        urllib3.disable_warnings(category=InsecureRequestWarning)

    if username and password:
        s.auth = (username, password)

    result = test_connection(s, host)
    if result == "prompt_ignore_cert":
        raise ValueError(f"SSL certificate verification failed for {host}. Pass ssl_verify=False to skip verification.")
    elif result == "prompt_auth":
        raise ValueError(f"Authentication failed for {host}. Check username and password.")

    logger.info(f"Successfully connected to Elasticsearch: {host}")
    return host, s


def unzip_git(filename, temp_dir=None):
    if temp_dir is None:
        temp_dir = Temp_Output_Dir
    try:
        fname = os.path.basename(filename)
        git_unzip_dir_name = os.path.join( temp_dir, os.path.splitext(fname)[0] )
        with zipfile.ZipFile( filename, 'r' ) as zip_ref:
            unzip_name = zip_ref.namelist()[ 0 ]
            zip_ref.extractall( temp_dir )
            shutil.move( os.path.join( temp_dir, unzip_name ), os.path.join( git_unzip_dir_name ) )
            os.remove( filename )
            logger.debug(f"Successfully unzipped and removed Git file {fname} to: {git_unzip_dir_name}")
            return git_unzip_dir_name
    except zipfile.BadZipFile as e:
        logger.error(f"Error occurred while unzipping Git file: {e}")
        raise ValueError(f"Error occurred while unzipping Git file: {e}")
    except Exception as e:
        logger.error(f"Error occurred while unzipping Git file: {e}")
        raise ValueError(f"Error occurred while unzipping Git file: {e}")

def source_repository(name, repo_type, proxy=None, ssl_verify=None, temp_dir=None):
    if temp_dir is None:
        temp_dir = Temp_Output_Dir
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
        filename = os.path.join(temp_dir, f"{repo_type}_repo_{timestamp}_{randomNum}.zip")
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
        name = unzip_git(filename, temp_dir=temp_dir)
        return name
    # Zip
    elif name.endswith(".zip") and os.path.isfile(name):
        name = unzip_git(name, temp_dir=temp_dir)
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
            os.makedirs(dest)
            copy_configs(src=src, dest=dest, sub_dir=sub_dir, error_on_overwrites=error_on_overwrites, ignore_file_extensions=ignore_file_extensions)
    except Exception as e:
        logger.error(f"Error occurred while copying files: {e}")
        raise ValueError(f"Error occurred while copying files: {e}")

def enable_ls_input(source_dir=None, ingest_type=None, raw=None, destination_dir=None, sub_dir=None):
    if sub_dir and not destination_dir.endswith(sub_dir):
        destination_dir = os.path.join(destination_dir, sub_dir)
    file_names = {
        "tcp": "0002-corelight-ecs-tcp-input",
        "tcp_ssl": "0002-corelight-ecs-tcp-ssl_tls-input",
        "hec": "0002-corelight-ecs-http-input-for_splunk_hec",
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

def apply_variables(
    templates_dir,
    pipelines_dir,
    # Protocol Logs / Main Logs / Known Logs / Known Protocol Logs
    protocol_log_type="logs",
    protocol_log_prefix="corelight",
    protocol_log_namespace="default",
    protocol_log_suffix_conn="conn",
    protocol_log_suffix_dns="dns",
    protocol_log_suffix_files="files",
    protocol_log_suffix_http="http",
    protocol_log_suffix_smb="smb",
    protocol_log_suffix_smtp="smtp",
    protocol_log_suffix_ssl="ssl",
    protocol_log_suffix_suricata_corelight="suricata_corelight",
    protocol_log_suffix_syslog="syslog",
    protocol_log_suffix_various="various",
    protocol_log_suffix_weird="weird",
    protocol_log_suffix_x509="x509",
    protocol_log_index_priority="901",
    # Unknown Logs
    unknown_log_type="logs",
    unknown_log_prefix="corelight",
    unknown_log_suffix="unknown",
    unknown_log_namespace="default",
    unknown_log_index_priority="901",
    # Metric Logs / Non Protocol Log Metrics (Metrics and Stats)
    metric_log_type="zeek",
    metric_log_prefix="corelight",
    metric_log_suffix="metric",
    metric_log_namespace="default",
    metric_log_index_priority="901",
    # System Logs / Non Protocol Log System (System, IAM, Netcontrol, and Audit)
    system_log_type="zeek",
    system_log_prefix="corelight",
    system_log_suffix="system",
    system_log_namespace="default",
    system_log_index_priority="901",
    # Parse Failures / Failed Logs / pipeline_error
    parse_failures_log_type="parse_failures",
    parse_failures_log_prefix="corelight",
    parse_failures_log_suffix="pipeline_error",
    parse_failures_log_namespace="default",
    parse_failures_log_index_priority="901",
):
    """Apply variable substitutions to templates and pipelines dirs (always together).

    templates_dir and pipelines_dir must be staging directories from fetch_templates /
    fetch_pipelines — not arbitrary existing paths.
    """
    suffix_dict = {
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_CONN": protocol_log_suffix_conn,
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_DNS": protocol_log_suffix_dns,
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_FILES": protocol_log_suffix_files,
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_HTTP": protocol_log_suffix_http,
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SMB": protocol_log_suffix_smb,
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SMTP": protocol_log_suffix_smtp,
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SSL": protocol_log_suffix_ssl,
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SURICATA_CORELIGHT": protocol_log_suffix_suricata_corelight,
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_SYSLOG": protocol_log_suffix_syslog,
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_VARIOUS": protocol_log_suffix_various,
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_WEIRD": protocol_log_suffix_weird,
        "VAR_CL_DS_SUFFIX_PROTOCOL_LOG_X509": protocol_log_suffix_x509,
    }
    index_pattern_dict = {
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_CONN":               f'{protocol_log_type}-{protocol_log_prefix}.{protocol_log_suffix_conn}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_DNS":                f'{protocol_log_type}-{protocol_log_prefix}.{protocol_log_suffix_dns}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_FILES":              f'{protocol_log_type}-{protocol_log_prefix}.{protocol_log_suffix_files}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_HTTP":               f'{protocol_log_type}-{protocol_log_prefix}.{protocol_log_suffix_http}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_SMB":                f'{protocol_log_type}-{protocol_log_prefix}.{protocol_log_suffix_smb}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_SMTP":               f'{protocol_log_type}-{protocol_log_prefix}.{protocol_log_suffix_smtp}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_SSL":                f'{protocol_log_type}-{protocol_log_prefix}.{protocol_log_suffix_ssl}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_SURICATA_CORELIGHT": f'{protocol_log_type}-{protocol_log_prefix}.{protocol_log_suffix_suricata_corelight}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_SYSLOG":             f'{protocol_log_type}-{protocol_log_prefix}.{protocol_log_suffix_syslog}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_VARIOUS":            f'{protocol_log_type}-{protocol_log_prefix}.{protocol_log_suffix_various}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_WEIRD":              f'{protocol_log_type}-{protocol_log_prefix}.{protocol_log_suffix_weird}-*',
        "VAR_CL_DS_INDEX_PATTERN_PROTOCOL_LOG_X509":               f'{protocol_log_type}-{protocol_log_prefix}.{protocol_log_suffix_x509}-*',
    }

    # --- Pipelines substitutions ---
    # Protocol Logs
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_TYPE_PROTOCOL_LOG",      replace_var_with=protocol_log_type )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_PREFIX_PROTOCOL_LOG",     replace_var_with=protocol_log_prefix )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_NAMESPACE_PROTOCOL_LOG",  replace_var_with=protocol_log_namespace )
    for key, value in suffix_dict.items():
        replace_var_in_directory( pipelines_dir, replace_var=key, replace_var_with=value )
    # Unknown Logs
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_TYPE_UNKNOWN_LOG",      replace_var_with=unknown_log_type )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_PREFIX_UNKNOWN_LOG",     replace_var_with=unknown_log_prefix )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_SUFFIX_UNKNOWN_LOG",     replace_var_with=unknown_log_suffix )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_NAMESPACE_UNKNOWN_LOG",  replace_var_with=unknown_log_namespace )
    # Metric Logs
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_TYPE_METRIC_LOG",      replace_var_with=metric_log_type )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_PREFIX_METRIC_LOG",     replace_var_with=metric_log_prefix )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_SUFFIX_METRIC_LOG",     replace_var_with=metric_log_suffix )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_NAMESPACE_METRIC_LOG",  replace_var_with=metric_log_namespace )
    # System Logs
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_TYPE_SYSTEM_LOG",      replace_var_with=system_log_type )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_PREFIX_SYSTEM_LOG",     replace_var_with=system_log_prefix )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_SUFFIX_SYSTEM_LOG",     replace_var_with=system_log_suffix )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_NAMESPACE_SYSTEM_LOG",  replace_var_with=system_log_namespace )
    # Parse Failures
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_TYPE_PARSE_FAILURES_LOG",      replace_var_with=parse_failures_log_type )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_PREFIX_PARSE_FAILURES_LOG",     replace_var_with=parse_failures_log_prefix )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_SUFFIX_PARSE_FAILURES_LOG",     replace_var_with=parse_failures_log_suffix )
    replace_var_in_directory( pipelines_dir, replace_var="VAR_CL_DS_NAMESPACE_PARSE_FAILURES_LOG",  replace_var_with=parse_failures_log_namespace )

    # --- Templates substitutions ---
    # Protocol Logs: per-log-type index patterns + priority
    for key, value in index_pattern_dict.items():
        replace_var_in_directory( templates_dir, replace_var=key, replace_var_with=value )
    replace_var_in_directory( templates_dir, replace_var="VAR_CL_DS_INDEX_PRIORITY_PROTOCOL_LOG",      replace_var_with=protocol_log_index_priority )
    # Unknown Logs
    replace_var_in_directory( templates_dir, replace_var="VAR_CL_DS_INDEX_PATTERN_UNKNOWN_LOG",        replace_var_with=f'{unknown_log_type}-{unknown_log_prefix}.{unknown_log_suffix}-*' )
    replace_var_in_directory( templates_dir, replace_var="VAR_CL_DS_INDEX_PRIORITY_UNKNOWN_LOG",        replace_var_with=unknown_log_index_priority )
    # Metric Logs
    replace_var_in_directory( templates_dir, replace_var="VAR_CL_DS_INDEX_PATTERN_METRIC_LOG",         replace_var_with=f'{metric_log_type}-{metric_log_prefix}.{metric_log_suffix}-*' )
    replace_var_in_directory( templates_dir, replace_var="VAR_CL_DS_INDEX_PRIORITY_METRIC_LOG",         replace_var_with=metric_log_index_priority )
    # System Logs
    replace_var_in_directory( templates_dir, replace_var="VAR_CL_DS_INDEX_PATTERN_SYSTEM_LOG",         replace_var_with=f'{system_log_type}-{system_log_prefix}.{system_log_suffix}-*' )
    replace_var_in_directory( templates_dir, replace_var="VAR_CL_DS_INDEX_PRIORITY_SYSTEM_LOG",         replace_var_with=system_log_index_priority )
    # Parse Failures
    replace_var_in_directory( templates_dir, replace_var="VAR_CL_DS_INDEX_PATTERN_PARSE_FAILURES_LOG", replace_var_with=f'{parse_failures_log_type}-{parse_failures_log_prefix}.{parse_failures_log_suffix}-*' )
    replace_var_in_directory( templates_dir, replace_var="VAR_CL_DS_INDEX_PRIORITY_PARSE_FAILURES_LOG", replace_var_with=parse_failures_log_index_priority )


def fetch_templates(source, dest_dir, proxy=None, ssl_verify=True):
    """Download or locate templates. Returns path to dest_dir.

    source: URL to git zip, local zip path, or local directory path.
    dest_dir: directory where templates will be staged.
    """
    _ensure_output_dirs()
    os.makedirs(dest_dir, exist_ok=True)
    ssl_verify_param = None if ssl_verify is True else ssl_verify
    if proxy and not ssl_verify:
        urllib3.disable_warnings(category=InsecureRequestWarning)
    source_dir = source_repository(source, repo_type="templates", proxy=proxy, ssl_verify=ssl_verify_param)
    source_dir = os.path.join(source_dir, git_templates_sub_dir, "component")
    copy_configs(src=source_dir, dest=dest_dir)
    logger.info(f"Templates staged to: {dest_dir}")
    return dest_dir


def fetch_pipelines(source, pipeline_type, dest_dir, proxy=None, ssl_verify=True):
    """Download or locate pipelines. Returns path to dest_dir.

    source: URL to git zip, local zip path, or local directory path.
    pipeline_type: 'ingest' or 'logstash'.
    dest_dir: directory where pipelines will be staged.
    """
    if pipeline_type == 'logstash':
        sub_dir = git_logstash_sub_dir
    elif pipeline_type == 'ingest':
        sub_dir = git_ingest_sub_dir
    else:
        raise ValueError(f"Invalid pipeline_type '{pipeline_type}'. Must be 'ingest' or 'logstash'.")
    _ensure_output_dirs()
    os.makedirs(dest_dir, exist_ok=True)
    ssl_verify_param = None if ssl_verify is True else ssl_verify
    if proxy and not ssl_verify:
        urllib3.disable_warnings(category=InsecureRequestWarning)
    source_dir = source_repository(source, repo_type=pipeline_type, proxy=proxy, ssl_verify=ssl_verify_param)
    source_dir = os.path.join(source_dir, sub_dir)
    copy_configs(src=source_dir, dest=dest_dir, ignore_file_extensions=['.disabled'])
    logger.info(f"Pipelines staged to: {dest_dir}")
    return dest_dir


def write_logstash_input(source_dir, input_type, dest_dir, keep_raw=False):
    """Write Logstash input config file into dest_dir. Returns path to the written file.

    source_dir: directory returned by fetch_pipelines.
    input_type: one of 'tcp', 'tcp_ssl', 'kafka', 'hec', 'udp'.
    dest_dir: destination directory (typically same as the pipelines dir).
    keep_raw: if True, enable the codec-disabled variant to preserve raw messages.
    """
    if input_type not in logstash_input_choices:
        raise ValueError(f"Invalid input_type '{input_type}'. Must be one of {logstash_input_choices}.")
    return enable_ls_input(source_dir=source_dir, ingest_type=input_type, raw=keep_raw, destination_dir=dest_dir)


def upload_to_elasticsearch(host, username=None, password=None,
                             templates_dir=None, pipelines_dir=None, pipeline_type=None,
                             ssl_verify=True, timeout=es_default_timeout, retry=es_default_retry):
    """Connect to Elasticsearch and upload templates and/or pipelines.

    host: full URL including scheme and port (e.g. 'https://elastic:9200').
    templates_dir: directory returned by fetch_templates, or None to skip template upload.
    pipelines_dir: directory returned by fetch_pipelines, or None to skip pipeline upload.
    pipeline_type: 'ingest' or 'logstash' (required when pipelines_dir is set).
    """
    baseURI, session = get_elasticsearch_connection_config(
        host, username=username, password=password, ssl_verify=ssl_verify,
        timeout=timeout, retry=retry,
    )
    make_modifications(
        session=session,
        baseURI=baseURI,
        pipeline_type=pipeline_type,
        final_templates_dir=templates_dir,
        final_pipelines_dir=pipelines_dir,
        use_templates=templates_dir is not None,
        VAR_CORELIGHT_INDEX_STRATEGY="datastream",
    )


if __name__ == "__main__":
    from corelight_ecs_cli import main
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nInstallation aborted.")
        sys.exit(1)
