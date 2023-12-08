# 1. Create the ILM Policy
```
PUT _ilm/policy/corelight-ecs-example-main_logs-ilm_steps
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_age": "4d",
            "max_primary_shard_size": "40gb"
          },
          "readonly": {},
          "set_priority": {
            "priority": 100
          }
        }
      },
      "warm": {
        "min_age": "12h",
        "actions": {
          "forcemerge": {
            "max_num_segments": 1,
            "index_codec": "best_compression"
          },
          "readonly": {},
          "set_priority": {
            "priority": 50
          },
          "migrate": {
            "enabled": false
          }
        }
      },
      "cold": {
        "min_age": "10d",
        "actions": {
          "readonly": {},
          "set_priority": {
            "priority": 0
          },
          "allocate": {
            "number_of_replicas": 1
          }
        }
      },
      "delete": {
        "min_age": "53d",
        "actions": {
          "delete": {
            "delete_searchable_snapshot": true
          }
        }
      }
    },
    "_meta": {
      "labels_corelight_ecs_version": "8.10.0.1",
      "description": "Corelight ECS Example ILM Policy for Main Logs"
    }
  }
}
```

# 2. Create the component template
```
PUT _component_template/corelight-ecs-main_logs-ilm-settings@custom
{
  "version": 2023111601,
  "template": {
    "settings": {
      "index": {
        "lifecycle": {
          "name": "corelight-ecs-example-main_logs-ilm_steps"
        }
      }
    }
  },
  "_meta": {
    "description": "Corelight ECS Example Component Template to Call a Custom ILM Policy for Main Logs",
  }
}
```
