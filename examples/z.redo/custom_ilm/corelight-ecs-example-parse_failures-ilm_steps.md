# 1. Create the ILM Policy
```
PUT _ilm/policy/corelight-ecs-example-parse_failures-ilm_steps
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_age": "1d",
            "max_primary_shard_size": "30gb"
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
        "min_age": "2d",
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
        "min_age": "6d",
        "actions": {
          "delete": {
            "delete_searchable_snapshot": true
          }
        }
      }
    },
    "_meta": {
      "labels_corelight_ecs_version": "8.10.0.1",
      "description": "Corelight ECS Example ILM Policy"
    }
  }
}
```

# 2. Create the component template
```
PUT _component_template/corelight-ecs-parse_failures-ilm-settings@custom
{
  "version": 2023111601,
  "template": {
    "settings": {
      "index": {
        "lifecycle": {
          "name": "corelight-ecs-example-parse_failures-ilm_steps"
        }
      }
    }
  },
  "_meta": {
    "description": "Corelight ECS Example Component Template",
  }
}
```

