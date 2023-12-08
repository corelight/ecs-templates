# Overview
This repository contains everything necessary to convert Corelight Logs into the Elastic Common Schema (ECS) naming standard and store them into an Elastic Stack deployment. Originally released in 2019, the same year as Elastic Common Schema, this repository is stil actively maintained and updated.

It supports over [200 different logs and metrics](https://docs.google.com/spreadsheets/d/1HqRRfvf5vUG3zgI9KG64hAj5oLSae7YbLoTKh846FCc/edit?usp=sharing) and is designed to be able to support all environments while simulatenously being able to customize the required and desired options to support each unique environment.  
Significant effort has been invested in ensuring support across all environments, while simultaneously allowing for the customization of necessary and desired options to suit each unique and respective deployment. 


The repository is primiarly compromised of two things:
1. Elasticsearch index templates, component templates, ilm policies, settings, and mappings
2. Installer script for this repository and the corresponding [Ingest Pipelines](https://github.com/brasitech/ecs-mapping) OR [Logstash Pipelines](https://github.com/brasitech/ecs-logstash-mappings)

# License
The files and automation script are open-source under a BSD license. See ``COPYING``for details.

# Install Steps
**Please read all sections before running the script.**
1. [Requirements](#1-requirements)
2. [Pre Install](#2-pre-insall)
3. [Install](#3-install)
4. [Post Install](#4-post-install)

 
## 1. Requirements
- Using the [`corelight_ecs.py`](./corelight_ecs.py) script from this repository. It is not supported to manually install the templates and pipelines because there hundreds of variables throughout the files that get replaced by the script.
- Python 3.6 and higher
- Elasticsearch version 8.x and higher or if still on version 7.x than 7.17 and higher
- If using Logstash, than Logstash version 8.x and higher or if still on version 7.x than 7.17 and higher
- Elasticsearch Datastream indexing strategy


## 2. Pre Insall
The script is designed to be able to support the following customizations:
- Number of shards
- Number of replicas
- Custom ILM policy
- Override Elasticsearch index field mapping
- Override Elasticsearch index setting 
- Custom Index Aliases
- Choose your own index data stream name (ie: `logs-corelight.conn-default` OR `ecs-corelight.conn.default` OR `call_it_what_you_will.conn.default` )
  - Including the organization portion of the datastream (which is the `default` portion in the examples above). Useful for multi-tenant environments such as MSSPs/CSSPs or if you want to have different naming and retention policies for different networks or deployments.
- Ability to override ingest pipelines both before and after the Corelight pipelines are called

**At the very least, customize:**
- [Index Settings](#custom-index-settings-ie-shards-and-replicas)
- [ILM](#custom-ilm-policy-strategy)

### Custom Index Settings ie: Shards and Replicas
Each index template is specified to call a component template that you can use to override the Index Settings.  
**Therefore you do not need to modify the index templates to use your own Index Settings.**

Create the following component templates and modify the index settings as desired. The name of the component template needs to be:
- `corelight-ecs-main_logs-base-settings@custom` [see example](./examples/custom_index_settings/corelight-ecs-example-main_logs-index_settings_steps.md)
- `corelight-ecs-metrics_and_stats-base-settings@custom` [see example](./examples/custom_index_settings/corelight-ecs-example-metrics_and_stats-index_settings_steps.md)
- `corelight-ecs-parse_failures-base-settings@custom` [see example](./examples/custom_index_settings/corelight-ecs-example-parse_failures-index_settings_steps.md)

### Custom ILM Policy Strategy
Each index template is specified to call a component template that you can use to override the ILM Policy Strategy.  
**Therefore you do not need to modify the index templates to use your own ILM Policy Strategy.**

Create the following component templates and modify the ilm policy name to match your custom ILM policy. The name of the component template needs to be:
- `corelight-ecs-main_logs-ilm-settings@custom` [see example](./examples/custom_ilm/corelight-ecs-example-main_logs-ilm_steps.md)
- `corelight-ecs-metrics_and_stats-ilm-settings@custom` [see example](./examples/custom_ilm/corelight-ecs-example-metrics_and_stats-ilm_steps.md)
- `corelight-ecs-parse_failures-ilm-settings@custom`  [see example](./examples/custom_ilm/corelight-ecs-example-parse_failures-ilm_steps.md)

### Custom Index Patterns
In the installer script there is an option to set your own dataset, prefix, suffix, etc for the main `logs`, `metrics`, and `parse_failures`.

### Custom Elasticsearch Templates and Mappings
Each index template is specified to call a component template that you can use to override the Index Mappings.  
**Therefore you do not need to modify the index templates to use your own Index Mappings.**

Create the following component templates and modify the mappings as desired. The name of the component template needs to be:
- `corelight-ecs-main_logs-mappings@custom`
- `corelight-ecs-metrics_and_stats-mappings@custom`
- `corelight-ecs-parse_failures-mappings@custom`

### Custom Index Aliases
Each index template is specified to call a component template that you can use to override the Index Aliases.  
**Therefore you do not need to modify the index templates to use your own Index Aliases.**

Create the following component templates and modify the alias settings as desired. The name of the component template needs to be:
- `corelight-ecs-main_logs-base-aliases@custom`
- `corelight-ecs-metrics_and_stats-base-aliases@custom`
- `corelight-ecs-parse_failures-base-aliases@custom`

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
git clone https://github.com/brasitech/ecs-templates
cd ecs-templates
python3 corelight_ecs.py
```

#### Script arguments
- `--no-color`: Disable colors for logging.
- `--debug`: Enable debug level logging.


## 4. Post Install

### Logstash
Certain values may need changed post install, such as parameters for input and output.
This would include things such as a custom certificate authority for the elasticsearch connection, various topics for kafka, and so on.
Because there are over 20 options in the elasticsearch output and over 60 options across 5 different inputs, the installer does not provide, prompt, and check validity of all of them
However, each file contains an environment variable that can be used automate the process of changing the values in the files after install. You will just need to uncomment and modify the lines you need after the install.


# Examples WIP
See the directory [examples](./examples) for examples of how to use the templates and pipelines.

- to use an index pattern just to be able to hit the ingest pipelines, like for corelight appliance or testing. using the output index `temporary_corelight_routing_index`


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
https://github.com/brasitech/ecs-templates
- Elasticsearch index templates, component templates, ilm policies, settings, and mappings
- Install Script

## Logstash Pipelines
https://github.com/brasitech/ecs-logstash-mappings
- Logstash pipeline configurations

## Ingest Pipelines
https://github.com/brasitech/ecs-mapping
- Ingest pipeline configurations

## Kibana Dashboards and Visualizations
https://github.com/corelight/ecs-dashboards

## Kibana Security Rules and Alerts
https://github.com/corelight/Elasticsearch_rules

