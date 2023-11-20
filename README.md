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
At the **beginning** of the ingest pipelines, before any Corelight pipelines are called, there is a function to use the ingest pipeline named `corelight-ecs-custom-common-pipeline`.
You can create an ingest pipeline with that name if there are things you want to do before the Corelight pipelines are called.
If you do not create the pipeline the function silently passes it, therefore it is optional.

### Custom Final Ingest Pipeline Catchall
At the **end** of the ingest pipelines, after all Corelight pipelines are called, there is a function to use the ingest pipeline named `corelight-ecs-custom-final-pipeline`.
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


# Changelog WIP
- Minimum requirements for all software (elasticsearch, logstash, kibana) is 7.17

    - for many reasons, but 1 of many great reasons is Ingest pipeline => 7.11 supports the set processor function "copy\_from"

    - tag\_with\_exception\_message for ruby filter block

        - requires version => 7.17
        - requires version => 8.x

    - ingest pipelines finally performant in => 8.8

    - logstash more performant in 8.x

    - many many other reasons

- \[@metadata]\[corelight\_env\_vars]\[disable\_legacy\_md5\_fingerprint\_hash] if set to true will disable legacy md5 fingerprint hashes else will call 8811-corelight-ecs-network\_fingerprints-enrich-legacy\_md5-filter.conf and add an array w/ md5 to the existing sha1

- replaced text analyzer with es\_stk\_analyzer

- parse-failures is now parse\_failures & parse-failure is parse\_failure

- changed VAR\_$Corelight\_LS\_Index\_Strategy to VAR\_CORELIGHT\_INDEX\_STRATEGY

- logs that do not explicitly have a pipeline/parser (new or unknown) they get set to event.category tbd (previously used either temporary or event.dataset). not use event.dataset as do not want to autocreate datastreams that would live outside ILM patterns and other control/settings and permissions. can still search the logs as is despite the name in the index pattern. event.dataset still gets set.

- you can set \[@metadata]\[custom\_temporary\_metadata\_index\_name\_namespace] or \[data\_stream]\[namespace] to set a desired namespace for multiple tenants/clients data

    - if \[@metadata]\[custom\_temporary\_metadata\_index\_name\_namespace] is set then it overrides if \[data\_stream]\[namespace] already exists

- for custom mappings,settings,ilm,etc.. use

    - aliases

        - corelight-main\_logs-aliases\@custom
        - corelight-metrics\_and\_stats-aliases\@custom
        - corelight-parse\_failures-aliases\@custom

    - base settings

        - corelight-main\_logs-base-settings\@custom
        - corelight-metrics\_and\_stats-base-settings\@custom
        - corelight-parse\_failures-base-settings\@custom

    - ilm settings

        - corelight-main\_logs-ilm-settings\@custom
        - corelight-metrics\_and\_stats-ilm-settings\@custom
        - corelight-parse\_failures-ilm-settings\@custom

    - mappings

        - corelight-main\_logs-mappings\@custom
        - corelight-metrics\_and\_stats-mappings\@custom
        - corelight-parse\_failures-mappings\@custom

- ingest pipelines custom additions user controlled\
  if the pipelines do not exist, it just ignores them. so in other words, is optional for user

- names are

    - before starting corelight ingest pipelines use 'corelight-ecs-custom-final-pipeline'
    - after completing corelight ingest pipelines use 'corelight-ecs-custom-final-pipeline'

- date fields that are user/software/attacker controlled (smtp.date for example) or commonly could be invalid (like for x509 cert dates before/after epoch) are always kept now instead of removed. if valid date timestamp then it is copied as such to a new field

- logstash moved 0101-corelight-ecs-user\_defined-set\_indexing\_strategy-filter.conf into 3100-corelight-ecs-common-set\_index\_prefix\_and\_suffix-filter.conf ( no longer need to edit manually anyways)

- installer script, use last run

    - uses last run, allows directory to be specified
    - this can also be used to just use the script to upload things you generated elsewhere or if already have the files generated

- additional changelog

    - logstash network fingerprints have md5 and sha1, sha1 will be used for future so that ingest pipelines will be able to support to. and ingest pipelines do not have a builtin callable md5 from script processor. only fingerprint processor that unfortunately has a bug of copying a null byte that makes the hash unusuable with other things (like logstash in this case)

    - single quote invalid IPs in event.tag (previously was not quoted)

    - IPs beginning with "0" (ie: 0.0.0.0/8) changed

        - ip\_type from "reserved\_as\_a\_source\_address\_only" to "reserved\_local\_this\_network"
        - ip\_rfc from "RFC\_1700" to "RFC\_1122-3.2.1.3"

    - split out RFC info for all RFC6890, RFC2544, RFC5737 that were previously tagged together

    - 255.255.255.255 changed from RFC\_8190 to RFC\_919

    - added rfc for 240.0.0.0/4 RFC5735, no longer grouped under multicast

    - carrier grade nat 100.64.0.0-100.127.255.255 fixed type label

    - 0.0.0.0 set to type reserved\_any\_address

    - switched ingest pipeline's main\_pipeline to call pipeline name w/ the event.dataset

    - changed the "genera"/"common" corelight\_genenral\_pipeline to corelight\_common\_pipeline

    - renamed all pipelines (to match similar naming in logstash)

        - corelight\_ to corelight-ecs-
        - \_pipeline to -pipeline

    - renamed pipelines (to match similar naming in logstash)

        - metrics\_general to common-metrics
        - netcontrol\_general to common-netcontrol
        - system\_related\_info\_general to common-system
        - stats\_general to common-stats

    - extended time fields for pulling out x509 and smtp date fields

    - ECS email field set is GA. previously these were always copied. However, they are now renamed instead. as follows. Alias field mappings are provided for backwards compatibility.

        - smtp.cc > email.cc.address
        - smtp.from > email.from.address
        - smtp.mailfrom > email.sender.address
        - smtp.msg\_id > email.message\_id
        - smtp.reply\_to > email.reply\_to.address
        - smtp.subject > email.subject
        - smtp.to > email.to.address
        -
        - smtp.date > smtp.date\_non\_formatted\_date (always kept)
        - smtp.date\_non\_formatted\_date COPIED to email.origination\_timestamp (if valid date timestamp)
        -
        - smtp.subject\_has\_non\_ascii > email.subject\_has\_non\_ascii
        - smtp.subject\_length > email.subject\_length


# To Do List WIP

## Priority 1
- [ ] tell user files to modify at the end (logstash input and output)
- [ ] remove brasitech references/defaults before finalizing
- [ ] concat all the logstash files into one file for upload for central pipeline management. basically no matter what, always save a central_pipeline_management.conf file
- [ ] option/choice to output metrics/non protocol logs to a seperate cluster . like an else statement or just seperate file, using input choice 1 or 2 (single output or metrics go somewhere else and then use 9940 and 9941 or something)
- [ ] ja4 fields https://github.com/FoxIO-LLC/ja4/tree/main/zeek
- [x] publicly available public version of list of logs and their categories, index pattern, etc..
- [ ] having removed copy_to for related.X fields, finish logic for ingest pipelines and logstash pipelines
    - [ ] logstash pipelines
    - [x] ingest pipelines
- [ ] remove or use VAR_CORELIGHT_INDEX_STRATEGY from script and all references in logstash/ingest/settings as only data stream is supported
- [ ] finish smtp.X to email.X alias backward compatibility- [ ] suricata logs
- [ ] add payload field for suricata_corelight into logstash and the field to index/component template
  ```
    if [typeoflogsfield] {
      ruby {
        code => '
          hexval = event.get("[fieldcontaininghexval]")
          event.set("[new][fieldforbase64val]", [[base64val].pack("H*")].pack("m0"))
        '
      }
    }
  ```
  - [ ] ingest pipelines
    - [ ] alert
    - [ ] dns
    - [ ] fileinfo
    - [ ] flow
    - [ ] http
    - [ ] smb
    - [ ] ssh
    - [ ] tls
    - [ ] anomaly
    - [ ] bittorrent-dht
    - [ ] dhcp
    - [ ] ftp
    - [ ] ftp_data
    - [ ] http2
    - [ ] ike
    - [ ] modbus
    - [ ] mqtt
    - [ ] pgsql
    - [ ] quic
    - [ ] rdp
    - [ ] rfb
    - [ ] tftp
- [ ] logstash pipelines
    - [ ] alert
    - [ ] dns
    - [ ] fileinfo
    - [ ] flow
    - [ ] http
    - [ ] smb
    - [ ] ssh
    - [ ] tls
    - [ ] anomaly
    - [ ] bittorrent-dht
    - [ ] dhcp
    - [ ] ftp
    - [ ] ftp_data
    - [ ] http2
    - [ ] ike
    - [ ] modbus
    - [ ] mqtt
    - [ ] pgsql
    - [ ] quic
    - [ ] rdp
    - [ ] rfb
    - [ ] tftp
- [ ] index templates
- [ ] final change log

## Priority 2
- [ ] break out each ECS field set into its own file
- [ ] shouldn't etc_viz service file be net appl/service/protocol
- [ ] use `[@metadata][etl][logstash_pipelines]`
    - [ ] logstash pipelines
- [ ] index mappings
- [ ] add `[@metadata][etl][ingest_pipelines]`
    - [ ] ingest pipelines
    - [ ] index mappings

## Priority 3
- [ ] change how ecs_compatibility works for inputs, because can actually use this to advantage to not have to do host/forward ip/name check thing collision
- [ ] add a tuning note if using geoip in ingest node (useful for anybody using elasticsearch corelight logs or not) ingest.geoip.cache_size defaults to only 1,000 and can change in elasticsearch yml

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

