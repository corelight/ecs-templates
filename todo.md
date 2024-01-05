# To Do

## Priority 1
- [ ] using last run option, still prints `INFO: Please review the following logstash files, for input and output, that you will need to modify for your environment:` 
- [ ] document in readme that the module `requests` is required.
  - [ ] in try/except print that can install via one of:  
sudo dnf install python3-requests # rhel8 or centos8  
sudo apt install python3-requests # ubuntu/debian  
sudo yum install python3-requests # rhel7 or centos7  
pip3 install requests # if not wanting to maintain requests via packager manager
- [ ] change intel log fields intel.X to threat.X where applicable
- [ ] finish smtp.X to email.X alias backward compatibility
- [ ] related.X fields see gdoc for all. having removed copy_to for related.X fields, finish logic for ingest pipelines and logstash pipelines
    - [x] logstash pipelines
        - [x] related.ip
        - [x] related.host
        - [x] related.user
        - [x] related.hash
        - [x] related.mac
    - [ ] ingest pipelines
        - [ ] related.ip
        - [ ] related.host
        - [ ] related.user
        - [ ] related.hash
        - [ ] related.mac
- [ ] pass cert for elaticsearch so if wanting to not ignore, can do so
  - [ ] if user says yes, then
    - [ ] prompt for cert path
    - [ ] check path exists
    - [ ] add to requests session for resuse
- [ ] final change log
  - [ ] remove brasitech references/defaults before finalizing
- [x] concat all the logstash files into one file for upload for central pipeline management. basically no matter what, always save a central_pipeline_management.conf file
    - [x] create functions and test
    - [x] add as an arg parse option to the script, where the prompts for directory and path for output file
- [x] automatically create all the custom component templates but only if they do not exist
- [x] index template matching an index pattern such as `temporary_corelight_routing_index` that all it does is call the default ingest pipeline
- [x] for all metric and system logs, perform '.' fields to '_' for ingest pipeline the same as is done in logstash pipelines
- [x] for suricata_corelight log alert.action/event.type for ingest pipeline (see if logstash does same)
- [x] option/choice to output metrics/non protocol logs to a seperate cluster . like an else statement or just seperate file, using input choice 1 or 2 (single output or metrics go somewhere else and then use 9940 and 9941 or something)
- [x] publicly available public version of list of logs and their categories, index pattern, etc..
- [x] remove or use VAR_CORELIGHT_INDEX_STRATEGY from script and all references in logstash/ingest/settings as only data stream is supported
- [x] tell user files to modify at the end (logstash input and output)
- [x] add ability to change master_timeout for certain requests/uri parameters, for huge clusters this sometimes can get in the way. ]

## Priority 2
- [ ] ja4 fields https://github.com/FoxIO-LLC/ja4/tree/main/zeek
- [ ] suricata logs
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
        - [ ] index templates for each

## Priority 3
- [ ] break out each ECS field set into its own file
- [ ] use `[@metadata][etl][logstash_pipelines]`
    - [ ] logstash pipelines
    - [ ] index mappings
- [ ] add `[@metadata][etl][ingest_pipelines]`
    - [ ] ingest pipelines
    - [ ] index mappings
- [ ] change how ecs_compatibility works for inputs, because can actually use this to advantage to not have to do host/forward ip/name check thing collision
- [ ] add a tuning note if using geoip in ingest node (useful for anybody using elasticsearch corelight logs or not) ingest.geoip.cache_size defaults to only 1,000 and can change in elasticsearch yml
