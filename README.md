# Overview
This repository contains everything necessary to convert Corelight or Zeek Logs into the Elastic Common Schema (ECS) naming standard and store them into an Elastic Stack deployment. Originally released in 2019, the same year as Elastic Common Schema, this repository is stil actively maintained and updated.

It supports over [200 different logs and metrics](https://docs.google.com/spreadsheets/d/1HqRRfvf5vUG3zgI9KG64hAj5oLSae7YbLoTKh846FCc/edit?usp=sharing) and is designed to be able to support all environments while simulatenously being able to customize the required and desired options to support each unique environment.  
Significant effort has been invested in ensuring support across all environments, while simultaneously allowing for the customization of necessary and desired options to suit each unique and respective deployment. 


The repository is primiarly compromised of two things:
1. Elasticsearch index templates, component templates, ilm policies, settings, and mappings
2. Installer script for this repository and the corresponding [Ingest Pipelines](https://github.com/corelight/ecs-mapping) OR [Logstash Pipelines](https://github.com/corelight/ecs-logstash-mappings)

# License
The files and automation script are open-source under a BSD license. See ``COPYING``for details.

# Install Steps
**Please read all sections before running the script.**
1. [Requirements](#1-requirements)
2. [Customization](#2-customization)
3. [Install](#3-install)
4. [Post Install](#4-post-install)

 
# 1. Requirements
- Using the [`corelight_ecs.py`](./corelight_ecs.py) script from this repository. It is not supported to manually install the templates and pipelines because there hundreds of variables throughout the files that get replaced by the script.
- Python 3.6 and higher
- Elasticsearch version 8.x and higher or if still on version 7.x than 7.17 and higher
- If using Logstash, than Logstash version 8.x and higher or if still on version 7.x than 7.17 and higher
- Elasticsearch Datastream indexing strategy


# 2. Customization
Customizing Index Settings, Mappings, Aliases, and ILM Policies is encouraged. Therefore, the script is designed to be able to support many types of customizations (detailed below).  
Many customizations will not be needed, but it is better to have the option than have not.   It is always recommend to use your own number of shards/replicas and ILM policy, but beyond that you should not need to customize much else. However if you normally customize many things in the index templates, ingest pipelines, and logstash pipelines in all of your deployments then you will still have ability.
- [Custom Index Names](#custom-index-names)  
  the script will prompt you for this and automatically update any templates, logstash pipelines, and or ingest pipelines that need to be updated
- [Index Settings](#custom-index-settings-ie-shards-and-replicas)
  - Number of shards
  - Number of replicas
  - Override other index settings
  - Anything else you see fit in the component template for the settings portion
- [Index Mappings](#customizing-index-mappings-ie-fields)
    - Override Elasticsearch index field mapping
    - Anything else you can see fit in the component template for the mappings portion
- [ILM Policies](#custom-ilm-policy-strategy)
  - Custom ILM policy
- [Index Aliases](#custom-index-aliases)
  - Alaises for the index patterns, such as for backwards compatibility or to disable it
- [Custom Ingest Pipelines](#custom-ingest-pipelines)
    - The ability to call your own custom ingest pipeline before any Corelight ingest pipelines are called and without modifying the Corelight ingest pipelines at all
    - The ability to call your own custom ingest pipeline after all Corelight ingest pipelines are called and without modifying the Corelight ingest pipelines at all
- Custom logstash pipelines is just matter of creating a file with a lower alphanumeric order and loading in the same directory



See each section below for more details.

## Custom Index Options

### Custom Index Names
The script will prompt you if you would look to choose custom index names/patterns for your data streams. This, allows you to choose your own index naming convention. For example you could chose:
- `logs-corelight.conn-default`
- `ecs-corelight.conn-default`
- `call_it_what_you_will.conn-default`
- `logs-corelight.conn-remotesite1`

It will then update all the necessary index templates as well if you chose ingest pipelines or logstash pipelines.
It's not recommended to change the defaults, as the Corelight logs are now setup to work with all the other types of ECS data, and be able to be used from within a Kibana data view such as `logs-*`

For multi-tenant environments such as MSSPs/CSSPs or different networks, you can not only choose the organization portion of the data stream in the script prompts (which is the `default` portion in the 3 examples above), however if you set data_stream.namespace in filebeat or some other method or hook the pipelines, then the pipelines are set to respect if that variable is already set to not override it. Just make sure that your namespace is set to a value that Elasticsearch allows for an index name (common mistake that is not obvious sometimes).

You can see the index patterns that get used in the [Google Sheet](https://docs.google.com/spreadsheets/d/1HqRRfvf5vUG3zgI9KG64hAj5oLSae7YbLoTKh846FCc/edit?usp=sharing) and the default for each log. Also, lists some additional information such as event.category, event.kind, and etc for each log.

### Custom Index Settings ie: Shards and Replicas
Each index template is specified to call a component template that you can use to override the Index Settings.
**Therefore you do not need to modify the repository index templates in order to use your own Index Settings.**

Create the following component templates or modify them post install. The name of the component templates that you can modify are:

_to cover all logs (split in 5 categories):_
- `corelight-ecs-component-metric_log-base-settings@custom`
- `corelight-ecs-component-parse_failures-base-settings@custom`
- `corelight-ecs-component-protocol_log-base-settings@custom`
- `corelight-ecs-component-system_log-base-settings@custom`
- `corelight-ecs-component-unknown_log-base-settings@custom`  

_to cover individual logs beyond the above, that commonly need their own settings to be even more specific:_
- `corelight-ecs-component-protocol_log-conn-base-settings@custom`
- `corelight-ecs-component-protocol_log-dns-base-settings@custom`
- `corelight-ecs-component-protocol_log-files-base-settings@custom`
- `corelight-ecs-component-protocol_log-http-base-settings@custom`
- `corelight-ecs-component-protocol_log-smb-base-settings@custom`
- `corelight-ecs-component-protocol_log-smtp-base-settings@custom`
- `corelight-ecs-component-protocol_log-ssl-base-settings@custom`
- `corelight-ecs-component-protocol_log-suricata_corelight-base-settings@custom`
- `corelight-ecs-component-protocol_log-syslog-base-settings@custom`
- `corelight-ecs-component-protocol_log-various-base-settings@custom`
- `corelight-ecs-component-protocol_log-weird-base-settings@custom`
- `corelight-ecs-component-protocol_log-x509-base-settings@custom`

### Customizing Index Mappings ie: fields
Each index template is specified to call a component template that you can use to override the Index Mappings for things such as field types or names.
**Therefore you do not need to modify the repository index templates in order to use your own Index Mappings.**

Create the following component templates or modify them post install. The name of the component templates that you can modify are:

_to cover all logs (split in 5 categories):_
- `corelight-ecs-component-metric_log-mappings@custom`
- `corelight-ecs-component-parse_failures-mappings@custom`
- `corelight-ecs-component-protocol_log-mappings@custom`
- `corelight-ecs-component-system_log-mappings@custom`
- `corelight-ecs-component-unknown_log-mappings@custom`

_to cover individual logs beyond the above, that commonly need their own settings to be even more specific:_
- `corelight-ecs-component-protocol_log-conn-mappings@custom`
- `corelight-ecs-component-protocol_log-dns-mappings@custom`
- `corelight-ecs-component-protocol_log-files-mappings@custom`
- `corelight-ecs-component-protocol_log-http-mappings@custom`
- `corelight-ecs-component-protocol_log-smb-mappings@custom`
- `corelight-ecs-component-protocol_log-smtp-mappings@custom`
- `corelight-ecs-component-protocol_log-ssl-mappings@custom`
- `corelight-ecs-component-protocol_log-suricata_corelight-mappings@custom`
- `corelight-ecs-component-protocol_log-syslog-mappings@custom`
- `corelight-ecs-component-protocol_log-various-mappings@custom`
- `corelight-ecs-component-protocol_log-weird-mappings@custom`
- `corelight-ecs-component-protocol_log-x509-mappings@custom`


### Custom ILM Policy Strategy
Each index template is specified to call a component template that you can use to override the ILM Policy to set your own retention.
**Therefore you do not need to modify the repository index templates in order to use your own ILM Policy.**

Create the following component templates or modify them post install. The name of the component templates that you can modify are:

_to cover all logs (split in 5 categories):_
- `corelight-ecs-component-metric_log-ilm-settings@custom`
- `corelight-ecs-component-parse_failures-ilm-settings@custom`
- `corelight-ecs-component-protocol_log-ilm-settings@custom`
- `corelight-ecs-component-system_log-ilm-settings@custom`
- `corelight-ecs-component-unknown_log-ilm-settings@custom`

these will cover individual logs beyond the above, that commonly need their own settings to be even more specific:
- `corelight-ecs-component-protocol_log-conn-ilm-settings@custom`
- `corelight-ecs-component-protocol_log-dns-ilm-settings@custom`
- `corelight-ecs-component-protocol_log-files-ilm-settings@custom`
- `corelight-ecs-component-protocol_log-http-ilm-settings@custom`
- `corelight-ecs-component-protocol_log-smb-ilm-settings@custom`
- `corelight-ecs-component-protocol_log-smtp-ilm-settings@custom`
- `corelight-ecs-component-protocol_log-ssl-ilm-settings@custom`
- `corelight-ecs-component-protocol_log-suricata_corelight-ilm-settings@custom`
- `corelight-ecs-component-protocol_log-syslog-ilm-settings@custom`
- `corelight-ecs-component-protocol_log-various-ilm-settings@custom`
- `corelight-ecs-component-protocol_log-weird-ilm-settings@custom`
- `corelight-ecs-component-protocol_log-x509-ilm-settings@custom`



### Custom Index Aliases
Each index template is specified to call a component template that you can use to override the Index Alaises.
**Therefore you do not need to modify the repository index templates in order to use your own ILM Alaises.**

Create the following component templates or modify them post install. The name of the component templates that you can modify are:

_to cover all logs (split in 5 categories):_
- `corelight-ecs-component-metric_log-aliases@custom`
- `corelight-ecs-component-parse_failures-aliases@custom`
- `corelight-ecs-component-protocol_log-aliases@custom`
- `corelight-ecs-component-system_log-aliases@custom`
- `corelight-ecs-component-unknown_log-aliases@custom`

_these will cover individual logs beyond the above, that commonly need their own settings to be even more specific:_
- `corelight-ecs-component-protocol_log-conn-aliases@custom`
- `corelight-ecs-component-protocol_log-dns-aliases@custom`
- `corelight-ecs-component-protocol_log-files-aliases@custom`
- `corelight-ecs-component-protocol_log-http-aliases@custom`
- `corelight-ecs-component-protocol_log-smb-aliases@custom`
- `corelight-ecs-component-protocol_log-smtp-aliases@custom`
- `corelight-ecs-component-protocol_log-ssl-aliases@custom`
- `corelight-ecs-component-protocol_log-suricata_corelight-aliases@custom`
- `corelight-ecs-component-protocol_log-syslog-aliases@custom`
- `corelight-ecs-component-protocol_log-various-aliases@custom`
- `corelight-ecs-component-protocol_log-weird-aliases@custom`
- `corelight-ecs-component-protocol_log-x509-aliases@custom`

## Custom Ingest Pipelines

### Custom Beginning Ingest Pipeline Catchall
At the **beginning** of the ingest pipelines, before any Corelight pipelines are called, there is a function to use the ingest pipeline named `corelight-ecs-main-pipeline@custom`.
You can create an ingest pipeline with that name if there are things you want to do before the Corelight pipelines are called.
If you do not create the pipeline the function silently passes it, therefore it is optional.

### Custom Final Ingest Pipeline Catchall
At the **end** of the ingest pipelines, after all Corelight pipelines are called, there is a function to use the ingest pipeline named `corelight-ecs-postprocess-final-main-pipeline@custom`.
You can create an ingest pipeline with that name if there are things you want to do before the Corelight pipelines are called.
If you do not create the pipeline the function silently passes it, therefore it is optional.

### Custom Beginning Ingest Pipeline Parse Failure Catchall
At the **beginning** of the ingest pipelines on_failure catchall for ingest pipeline failures, before any Corelight pipelines are called, there is a function to use the ingest pipeline named `corelight-ecs-parse_failures-pipeline@custom`.
You can create an ingest pipeline with that name if there are things you want to do before the Corelight pipelines are called.
If you do not create the pipeline the function silently passes it, therefore it is optional.

### Custom Final Ingest Pipeline Parse Failure Catchall
At the **end** of the ingest pipelines, after all Corelight pipelines are called, there is a function to use the ingest pipeline named `corelight-ecs-postprocess-final-main-pipeline@custom`.
You can create an ingest pipeline with that name if there are things you want to do before the Corelight pipelines are called.
If you do not create the pipeline the function silently passes it, therefore it is optional.


## 3. Install
### Script Usage
```shell
git clone https://github.com/corelight/ecs-templates
cd ecs-templates
python3 corelight_ecs.py
```

#### Script arguments
- `--no-color`: Disable colors for logging.
- `--debug`: Enable debug level logging.
- `--es-default-timeout=10`: Change the default timeout waiting for the connection to the elasticsearch.
- `--es-default-retry=2`: Change the default number of times to retry a connection to the elasticsearch.
- `--git-repository=corelight`: Change the default number of times to retry a connection to the elasticsearch.
- `--git-branch=main`: Change the default number of times to retry a connection to the elasticsearch.


## 4. Post Install

### Logstash
Certain values may need changed post install, to suite your environment. This would include things such as a custom certificate authority for the elasticsearch connection, various topics for kafka, and so on.
Because there are over 20 options in the elasticsearch output and over 60 options across 5 different inputs, the installer does not provide, prompt, and check validity of all of them.
However, to help you, the script will tell you which files to modify.
Also, for those who use full automation of all the things, an [example script](examples/variable_substitution/corelight_envsubst_var_replace_logstash.sh) has been provided to show that it is possible to automate the process of changing the values in the files after install and simulatenously uncommenting out the lines for the variables that get used.

### Customize Your Templates
See the [Customization](#2-customization) section for more details.


# Corelight Sensor Setup
- to use an index pattern just to be able to hit the ingest pipelines, like for corelight appliance or testing. Set the prefix to `temporary_corelight_routing_index`


# Changelog WIP
see the file [changelog.md](./changelog.md) for a full changelog of the repository.

# To Do List WIP
see the file [todo.md](./todo.md) for a full list of things to do for the repository.

# Versioning
The versioning of this repository is based on the version of the Elastic Common Schema (ECS) that it supports.
Fields are added to the each log:  
- `labels.corelight.ecs_version`
- `labels.corelight.ecs_method`
- `labels.corelight.ecs_method_version`

# Github Repository Definitions

## Elasticsearch templates (This Repository)
https://github.com/corelight/ecs-templates
- Elasticsearch index templates, component templates, ilm policies, settings, and mappings
- Install Script

## Logstash Pipelines
https://github.com/corelight/ecs-logstash-mappings
- Logstash pipeline configurations

## Ingest Pipelines
https://github.com/corelight/ecs-mapping
- Ingest pipeline configurations

## Kibana Dashboards and Visualizations
https://github.com/corelight/ecs-dashboards

## Kibana Security Rules and Alerts
https://github.com/corelight/Elasticsearch_rules

