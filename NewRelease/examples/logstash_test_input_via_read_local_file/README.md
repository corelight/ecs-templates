Test the pipeline without outputting to your cluster.
1) create the directory to read the logs from and where to output the parsed logs
    ```bash
    mkdir /tmp/corelight_ecs/
    ```
2) copy the test log to path to read
    ```bash
    cp corelight_test.log /tmp/corelight_ecs/corelight_test.log
    ```
3) enable output, either use output to a file or stdout  
  a) file out  
    copy `9999-corelight-ecs-test-file-output.conf.disabled` to your pipelines directory and remove the appended `.disabled`
  b) stdout  
    copy `9999-corelight-ecs-test-stdout-output.conf.disabled` to your pipelines directory and remove the appended `.disabled`
4) view the output
  a) file out  
    ```bash
    cat /tmp/corelight_ecs/corelight_test.log.parsed
    ```
  b) stdout will show in your console or logstash logs
    ```bash
    tail -f /var/log/logstash/logstash-plain.log
    ```