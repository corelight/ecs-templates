# 1. Create the Component Template
```
PUT _component_template/corelight-ecs-parse_failures-base-settings@custom
{
  "version": 2023101701,
  "template": {
    "settings": {
      "index": {
        "refresh_interval": "50s",
        "number_of_shards": "3",
        "number_of_replicas": "1"
      }
    }
  },
  "_meta": {
    "description": "Corelight ECS Example Component Template",
  }
}
```
