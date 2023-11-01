# #TODO: Few things left
- [ ] tell user files to modify at the end (logstash input and output)
- [ ] remove brasitech references/defaults before finalizing
- [ ] concat all the logstash files into one file for upload for central pipeline management. basically no matter what, always save a central_pipeline_management.conf file
- [ ] option/choice to output metrics/non protocol logs to a seperate cluster . like an else statement or just seperate file, using input choice 1 or 2 (single output or metrics go somewhere else and then use 9940 and 9941 or something)


# Corelight ECS Elasticsearch Templates
This repository contains the necessary Elasticsearch index templates, mappings, and ilm policies to support the Corelight ECS pipeline.
Also, it contains the functionality to install the necessary pipelines to parse the logs via either ingest pipelines or logstash.

**Please read all the necessary requirements before using this repository.**

## Custom Options

### Mappings
Each index template is specified to call a component template that you can use to override mappings. Create the component template in elasticsearch and supply whichever settings fit your environment. The name of the component template needs to be:
- `corelight-ecs-main_logs-mappings@custom`
- `corelight-ecs-metrics_and_stats-mappings@custom`
- `corelight-ecs-parse_failures-mappings@custom`

### Aliases
Each index template is specified to call a component template that you can use to override index settings. Create the component template in elasticsearch and supply whichever settings fit your environment. The name of the component template needs to be:
- `corelight-ecs-main_logs-base-aliases@custom`
- `corelight-ecs-metrics_and_stats-base-aliases@custom`
- `corelight-ecs-parse_failures-base-aliases@custom`

### Index Settings (Shards, Replicas, etc)
Each index template is specified to call a component template that you can use to override index settings. Create the component template in elasticsearch and supply whichever settings fit your environment. The name of the component template needs to be:
- `corelight-ecs-main_logs-base-settings@custom`
- `corelight-ecs-metrics_and_stats-base-settings@custom`
- `corelight-ecs-parse_failures-base-settings@custom`

### Index Lifecycle Management (ILM) Policies
Each index template is specified to call a component template that contains the ILM policy. That are supplied last so they will override any ilm from this repository. Therefore you do not need to modify the index templates to use your own ILM policies. You just need to create component template and whichever ilm you want to call from it. The name of the component template needs to be:
- `corelight-ecs-main_logs-ilm-settings@custom`
- `corelight-ecs-metrics_and_stats-ilm-settings@custom`
- `corelight-ecs-parse_failures-ilm-settings@custom`

### Index Patterns
In the installer script there is an option to set your own dataset, prefix, suffix, etc for the main `logs`, `metrics`, and `parse_failures`. 

### Catch All Ingest Pipeline
At the **beginning** of the ingest pipelines, before any Corelight pipelines are called, there is a function to use the pipeline named `corelight-ecs-custom-common-pipeline`. 
You can create an ingest pipeline with that name if there are things you want to do before the Corelight pipelines are called.
If you do not create the pipeline the function silently passes it, therefore it is optional.

### Final Ingest Pipeline
At the **end** of the ingest pipelines, after all Corelight pipelines are called, there is a function to use the pipeline named `corelight-ecs-custom-final-pipeline`.
You can create an ingest pipeline with that name if there are things you want to do before the Corelight pipelines are called.
If you do not create the pipeline the function silently passes it, therefore it is optional.

## 

# Usage
```shell
git clone $ThisRepositoryURL
cd ecs-templates
python3 installer.py
```

# Requirements
1. Python 3.6 or higher
2. Elasticsearch 7.17 or higher
3. Logstash 7.17 or higher
4. Datastream indexing strategy
5. Using the script. It is not recommended to manually install the templates and pipelines because there are many variables throughout the files that get replaced with the installer input.

## Post-install steps for logstash
Certain values may need changed post install, such as parameters for input and output.
This would include whether using a custom certificate for elasticsearch, various topics for kafka, and so on.
Because there are over 20 options in the elasticsearch output and over 60 options across 5 different inputs, the installer does not provide,prompt, and check validity of all of them
However, each file contains an environment variable that can be used automate the process of changing the values in the files after install. You will just need to uncomment the lines after the install.



# Examples
See the directory [examples](./examples) for examples of how to use the templates and pipelines.




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
