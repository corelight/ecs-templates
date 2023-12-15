Note: We have a new release train for now under the new Release. This requires 8.10 and datastreams. This is a breaking change. It will use a new index and some new and optimized field types.

Also, the new pipeline will be stored in Main and the older index style will be stored in Dev
What's new
1. New install script - THis gives clearer questions and better error handling.
2. You can change the index name
3.  you can add custom templates
4.  You will now have a tryout mode where the script will create all the templates and pipeline but not upload them
5.  You can also rerun the script with data from the last run this will allow you to easily upload to different clusters or update with new templates
6.  Password is now masked when running the script

To run the new system, follow the txt document in the New Release folder called install.txt



# Corelight ECS Elasticsearch Templates
This repository contains the necessary Elasticsearch templates or component templates for your ECS deployment of Corelight/Zeek.

ECS install

Note: to limit the number of indices Corelight/Zeek create, we use a strategy that only the  following indices  types will be created

Conn
Dns
Files
Http
Smb
Ssl
Suricata
x509
Stats
System
Various - This is the location for all logs that are not stated above 

First, clone or download the Corelight ECS-templates repository and run the python script install.py and answer the following questions:

* Will you be using a Logstash pipeline?  Answer yes if you want to run the Corelight ECS pipeline in logstash and not the ingest pipeline.
* Will you only be installing templates? If using ingest pipeline, answer No. This will allow you to install only templates, no Logstash pipelines or ingest pipelines will be installed.
* Is this an update to the existing template? If so, ILM will not be installed. This will apply all new Corelight templates to the unit and not update ILM policies.
* If you answered yes to the above, you will get the following questions:
    
    * This script needs to be run on the Logstash box. Does this box have Logstash running, and is Logstash ingesting? At this time the script will only install the pipeline on the local host.
    * The script will now access Corelight git hub repro ecs-logstash-mapping and download the latest pipelines.
    * You will then be asked how you want to ingest the data. 
        * Do you want to keep the raw message, this will increase storage space - This will put the Zeek output in the original format in a field so you can see both ECS and raw Zeek.
        * Are you sending the data to Logstash over JSON over TCP - this will set up a listener on TCP port 8515 to listen for Corelight/Zeek logs.
        * Will you enabeing SSL? - Will it be JSON over TLS? if so, the TCP port will be 8615.
        * Are you sending Data to Logstash via Kafka - This will tell Logstash to use Kafka ingest - you will need to set up Kafka and update the config file to point to the Kafka topic and server.
        * Are you sending data to Logstash over HTTP Event Collector? - This will enable Logstash to use the HEC and strip off the HTTP headers from the event.
    * The Script will now start asking about how to get data into Elastic
        * Will you be using Datastreams - This is Elastic Time series data. This will push templates to the server to support Datastreams.
        * Will you be using Component Templates - This will push component templates to elastic. If you are running 8.x and above and not Datastreams you need to use this
        * Will you be using legacy Templates - this will be used in 7.x but will not work in 8.x
    * The script will now install the correct templates to the Elastic Servers
    * If you did not pick Logstash the system will download the Corelight Git repo ecs-mappings and upload ingest pipelines to the server


Post-install steps for logstash 

* If you are using Datastreams you need to do the following
  * Edit the file 9939-elasticsearch-corelight_zeek-output.conf.disable and add how to connect to the elastic server and then rename the file to 9939-elasticsearch-corelight_zeek-output.conf
 
*  There is a new output file 9939-elasticsearch-corelight_zeek-output_with_metrics_cluster.conf.disabled this will let you send Corelight metrics to another cluster. You configure it like the other 9939 just add the config to connect to the Security cluster and the metrics cluster and change the name from .disable to .conf

Last step would be to edit you pipeline.yaml file to load the pipeline in the CorelightPipelines directory 

Example as follows

 pipeline.id: main
  path.config: "/etc/logstash/CorelightPipelines/*.conf"




## Github Repository Definitions

### Elasticsearch templates (This Repository)
Index templates, component templates, settings, mappings
https://github.com/corelight/ecs-templates

### Logstash Pipeline 
Logstash pipeline configurations
https://github.com/corelight/ecs-logstash-mappings 

### Ingest Pipeline
Ingest pipeline configurations
https://github.com/corelight/ecs-mapping
