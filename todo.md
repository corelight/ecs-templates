# To Do

## Priority 1
- [ ] for all metric and system logs, perform '.' fields to '_' for ingest pipeline the same as is done in logstash pipelines
```  
# Remove infinite dotted fields and replace with underscore
  ruby {
  code => '
  # Set keys/fields to delete
  keys_to_del = []

        # Get the original event
        orig_event = event.to_hash

        # Find each field with a "." then replace it and then mark the original field name for deletion
        orig_event.keys.each { |k| orig_event[k.gsub(".", "_")] = orig_event[k]; keys_to_del << k if k.include?(".") }

        # Delete the original fields that contained the "."
        keys_to_del.each { |field_to_del| orig_event.delete(field_to_del) }

        # Replace/overwrite event
        event.overwrite(LogStash::Event.new(orig_event))
      '
```
- [ ] related.X fields see gdoc for all. having removed copy_to for related.X fields, finish logic for ingest pipelines and logstash pipelines
    - [ ] logstash pipelines
        - [x] related.ip
        - [x] related.host
        - [ ] related.user
        - [x] related.hash
        - [x] related.mac
    - [ ] ingest pipelines
        - [ ] related.ip
        - [ ] related.host
        - [ ] related.user
        - [ ] related.hash
        - [ ] related.mac
- [ ] tell user files to modify at the end (logstash input and output)
- [ ] remove brasitech references/defaults before finalizing
- [ ] concat all the logstash files into one file for upload for central pipeline management. basically no matter what, always save a central_pipeline_management.conf file
- [ ] change intel log fields intel.X to threat.X where applicable
- [ ] finish smtp.X to email.X alias backward compatibility
- [ ] final change log
- [x] for suricata_corelight log for ingest pipeline (see if logstash does same)
- [x] option/choice to output metrics/non protocol logs to a seperate cluster . like an else statement or just seperate file, using input choice 1 or 2 (single output or metrics go somewhere else and then use 9940 and 9941 or something)
- [x] publicly available public version of list of logs and their categories, index pattern, etc..
- [x] remove or use VAR_CORELIGHT_INDEX_STRATEGY from script and all references in logstash/ingest/settings as only data stream is supported
```
    {
      ""rename"": {
        ""field"": ""alert.action"",
        ""target_field"": ""event.type"",
        ""ignore_missing"": true
      }
    },"
```

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
