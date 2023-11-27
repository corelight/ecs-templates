# Version 20231201
- Minimum requirements for all software (elasticsearch, logstash, kibana) is 7.17

    - for many reasons, but 1 of many great reasons is Ingest pipeline => 7.11 supports the set processor function "copy\_from"

    - tag\_with\_exception\_message for ruby filter block

        - requires version => 7.17
        - requires version => 8.x

    - ingest pipelines finally performant in => 8.8

    - logstash more performant in 8.x

    - many many other reasons

- \[@metadata]\[corelight\_env\_vars]\[disable\_legacy\_md5\_fingerprint\_hash] if set to true will disable legacy md5 fingerprint hashes else will call 8811-corelight-ecs-network\_fingerprints-enrich-legacy\_md5-filter.conf and add an array w/ md5 to the existing sha1

- changed values for `labels.corelight.ecs_method`. values are now `logstash_pipeline` or `ingest_pipeline` previously were `logstash` or `ingest_pipeline`
- added `labels.corelight.ecs_pipeline_method`
- replaced text analyzer with es\_stk\_analyzer
- removed stats index, replaced with metrics. event.category is diagnostics same as the other metrics (previously was 'stats') these were the logs:
    - capture_loss
    - corelight_cloud_stats
    - corelight_overall_capture_loss
    - corelight_profiling
    - corelight_weird_stats
    - namecache
    - packet_filter
    - reporter
    - stats
    - suricata_stats
    - weird_stats
- removed netcontrol and iam index, replaced with system. these were the logs:
    - netcontrol
    - netcontrol_drop
    - netcontrol_shunt
    - corelight_audit_log
    - audit
    - auditlog
- changed suricata_corelight dataset back to suricata_corelight from suricata
- parse-failures is now parse\_failures & parse-failure is parse\_failure

- change intel log event.category from intrustion_detection to threat

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

    - before starting corelight ingest pipelines use 'corelight-ecs-main-pipeline@custom'
    - after completing corelight ingest pipelines use 'corelight-ecs-postprocess-final-main-pipeline@custom'

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
- for `corelight_weird_stats.log` and `weird_stats.log`
    - changed `name` from `labels.weird_name` to `name`
      - removed config in ingest pipeline, was not in logstash pipeline
    - changed `num_seen` from `labels.weird_number_seen` to `num_seen`
      - removed config in ingest pipeline, was not in logstash pipeline
- for `conn_doctor.log`
    - changed `bad` from `conn_doctor.bad` to `bad`
      - removed config in logstash pipeline, was not in ingest pipeline 
    - changed `check` from `conn_doctor.check` to `check`
      - removed config in logstash pipeline, was not in ingest pipeline
    - changed `percent` from `conn_doctor.percent` to `percent`
      - removed config in logstash pipeline, was not in ingest pipeline
- removed `labels.dns.query_length` from mappings, which was just an alias to `dns.question.name_length`
- spcap fields for `conn.log`
    - ingest pipeline:
        - added varations for underscore fields (ie: `spcap_rule`, `spcap_trigger`, `spcap_url`)
        - `spcap_rule` from `labels.corelight.spcap.rule` to `conn.spcap_rule`
        - `spcap_trigger` from `labels.corelight.spcap_trigger` to `conn.spcap_trigger`
        - `spcap_url` from `labels.corelight.spcap_url` to `conn.spcap_url`
    - logstash pipeline:
        - `spcap_rule` from `labels.corelight.spcap.rule` to `conn.spcap_rule`
        - `spcap_trigger` from `labels.corelight.spcap.trigger` to `conn.spcap_trigger`
        - `spcap_url` from `labels.corelight.spcap.url` to `conn.spcap_url`
- removed `labels.etl.elasticsearch_index_*` fields
    - `labels.etl.elasticsearch_index_name_prefix`
    - `labels.etl.elasticsearch_index_name_suffix`
    - `labels.etl.elasticsearch_index_strategy`
- suricata_corelight log
  - append the value from  `suricata.alert.action` to `event.type`. previously `alert.action` was renamed to `event.type` 
- for metric and system logs, perform '.' fields to '_' for ingest pipeline the same as is done in logstash pipelines
