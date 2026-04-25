#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive CLI layer for corelight_ecs.

This module owns all user-facing prompts, argument parsing, and the main()
orchestration loop.  Pure automation functions live in corelight_ecs.py.
"""
try:
    import sys
    import os
    import shutil
    import getpass
    import argparse
    import urllib3
    from pathlib import Path
    from urllib.parse import urlparse
    from urllib3.exceptions import InsecureRequestWarning
except IndexError as error:
    print(error)
    print('Unable to load python module... Exiting Script!')
    sys.exit(1)

import corelight_ecs
from corelight_ecs import (
    # constants / globals
    script_version, script_description, script_dir,
    Config_Dir, dir_time,
    git_templates_repo, git_logstash_repo, git_ingest_repo,
    git_templates_sub_dir, git_logstash_sub_dir, git_ingest_sub_dir,
    logstash_input_choices, ls_output_filename,
    es_default_timeout, es_default_retry,
    LOG_COLORS, COLORS,
    # functions
    logger,
    setup_logger,
    _ensure_output_dirs,
    get_elasticsearch_connection_config,
    source_repository,
    copy_configs,
    enable_ls_input,
    categorize_ls_files,
    concat_ls_files,
    make_modifications,
    apply_variables,
    fetch_templates,
    fetch_pipelines,
    write_logstash_input,
    upload_to_elasticsearch,
)


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Prompt wrappers
# ---------------------------------------------------------------------------

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

def prompt_elasticsearch_connection_config():
    """Interactive wrapper: prompts for ES connection details, returns (baseURI, session)."""
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

    ssl_verify = True
    username = None
    password = None

    # Prompt if user wants to ignore certificate errors if https
    if baseURI.startswith( "https://" ):
        if prompt_for_es_ignore_certificate_errors(try_again=False):
            ssl_verify = False

    # Prompt for user and password authentication
    auth = prompt_for_es_user_and_password(try_again=False)
    if auth:
        username, password = auth[0], auth[1]

    # Test the connection, so can reprompt if it fails
    while True:
        try:
            return get_elasticsearch_connection_config(baseURI, username=username, password=password, ssl_verify=ssl_verify)
        except ValueError as e:
            msg = str(e)
            if "SSL certificate" in msg:
                if prompt_for_es_ignore_certificate_errors(try_again=True):
                    ssl_verify = False
                else:
                    logger.error(f"Failed to verify SSL connectivity to Elasticsearch: {baseURI}")
                    sys.exit(1)
            elif "Authentication" in msg:
                auth = prompt_for_es_user_and_password(try_again=True)
                if auth:
                    username, password = auth[0], auth[1]
                else:
                    logger.error(f"Failed to authenticate to Elasticsearch: {baseURI}")
                    sys.exit(1)
            else:
                raise

def prompt_variables(templates_dir, pipelines_dir):
    """Interactive wrapper: prompts for variable overrides, then calls apply_variables()."""
    kwargs = {}

    use_custom_names = input_bool( f"\nDo you want to use custom index names?", default=False )
    if use_custom_names:
        kwargs['protocol_log_type']      = input_string( question="Enter the Datastream 'type' for Protocol Logs",      default="logs" )
        kwargs['protocol_log_prefix']    = input_string( question="Enter the Datastream 'prefix' for Protocol Logs",    default="corelight" )
        kwargs['protocol_log_namespace'] = input_string( question="Enter the Datastream 'namespace' for Protocol Logs", default="default" )
        kwargs['unknown_log_type']       = input_string( question="Enter the Datastream 'type' for Unknown Logs",       default="logs" )
        kwargs['unknown_log_prefix']     = input_string( question="Enter the Datastream 'prefix' for Unknown Logs",     default="corelight" )
        kwargs['unknown_log_suffix']     = input_string( question="Enter the Datastream 'suffix' for Unknown Logs",     default="unknown" )
        kwargs['unknown_log_namespace']  = input_string( question="Enter the Datastream 'namespace' for Unknown Logs",  default="default" )
        kwargs['metric_log_type']        = input_string( question="Enter the Datastream 'type' for Metric Logs",        default="zeek" )
        kwargs['metric_log_prefix']      = input_string( question="Enter the Datastream 'prefix' for Metric Logs",      default="corelight" )
        kwargs['metric_log_suffix']      = input_string( question="Enter the Datastream 'suffix' for Metric Logs",      default="metric" )
        kwargs['metric_log_namespace']   = input_string( question="Enter the Datastream 'namespace' for Metric Logs",   default="default" )
        kwargs['system_log_type']        = input_string( question="Enter the Datastream 'type' for System Logs",        default="zeek" )
        kwargs['system_log_prefix']      = input_string( question="Enter the Datastream 'prefix' for System Logs",      default="corelight" )
        kwargs['system_log_suffix']      = input_string( question="Enter the Datastream 'suffix' for System Logs",      default="system" )
        kwargs['system_log_namespace']   = input_string( question="Enter the Datastream 'namespace' for System Logs",   default="default" )
        kwargs['parse_failures_log_type']      = input_string( question="Enter the Datastream 'type' for Parse Failures",      default="parse_failures" )
        kwargs['parse_failures_log_prefix']    = input_string( question="Enter the Datastream 'prefix' for Parse Failures",    default="corelight" )
        kwargs['parse_failures_log_suffix']    = input_string( question="Enter the Datastream 'suffix' for Parse Failures",    default="pipeline_error" )
        kwargs['parse_failures_log_namespace'] = input_string( question="Enter the Datastream 'namespace' for Parse Failures", default="default" )

    use_custom_priorities = input_bool( f"\nDo you want to use custom index priorities?", default=False )
    if use_custom_priorities:
        kwargs['protocol_log_index_priority']      = input_int( question="Enter the Index Priority for Protocol Logs", default="901" )
        kwargs['unknown_log_index_priority']        = input_int( question="Enter the Index Priority for Unknown Logs",  default="901" )
        kwargs['metric_log_index_priority']         = input_int( question="Enter the Index Priority for Metric Logs",   default="901" )
        kwargs['system_log_index_priority']         = input_int( question="Enter the Index Priority for System Logs",   default="901" )
        kwargs['parse_failures_log_index_priority'] = input_int( question="Enter the Index Priority for Parse Failures", default="901" )

    apply_variables(templates_dir, pipelines_dir, **kwargs)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

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
        '--git-repository', dest='git_repository', type=str, required=False, default=corelight_ecs.git_repository,
        help='Github Repository.\ndefault: %(default)s'
    )
    parser.add_argument(
        '--git-branch', dest='git_branch', type=str, required=False, default=corelight_ecs.git_branch,
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

def main():
    # Gather args
    args = parse_args()
    # Setup logging
    setup_logger(args.no_color, args.debug)

    # Ensure base output directories exist (side-effect-free at import time)
    _ensure_output_dirs()

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

        prompt_variables(templates_dir=Final_Templates_Dir, pipelines_dir=Final_Pipelines_Dir)

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
            baseURI, session = prompt_elasticsearch_connection_config()
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


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nInstallation aborted.")
        sys.exit(1)
