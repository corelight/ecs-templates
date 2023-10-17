#!/usr/bin/env python3

#from asyncore import file_wrapper
#from distutils import filelist
#from this import d, s
#import glob
import shutil
import requests
from urllib3.exceptions import InsecureRequestWarning
import time
import sys
import zipfile
import os
import random
import subprocess

def checkRequest(responseObj):
    code = responseObj.status_code
    if code == 200:
        return 200

    if 400 <= code <= 500:
        print(responseObj.json())
        time.sleep(5)
        return code
    return code

def input_bool(question, default=None):

    prompt = " [yn]"

    if default is not None:
        prompt = " [Yn]:" if default else " [yN]:"

    while True:
        val = input(question + prompt)
        val = val.lower()
        if val  == '' and default is not None:
            return default
        if val in ('y', 'n'):
            return val == 'y'
        print("Invalid response")

def input_int(question):
    while True:
        val = input(question + ": ")
        try:
            return int(val)
        except ValueError as e:
            print("Invalid response", e)

def testConnection(session, baseURI):
    testUri = "/_cat/indices?v&pretty"
    uri = baseURI + testUri
    response = session.get(uri, timeout=5)
    checkRequest(response)
    response.raise_for_status()

def download_repository( name ):
    randomNum = random.randint(0,100)
    filename = "output" + str(randomNum) + ".zip"
    host = "https://github.com/"
    organization = "corelight/"
    url = host + organization + name 
    with requests.get(url, stream=True) as r:
        with open(filename, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
    return filename

def unzipGit(filename):
    with zipfile.ZipFile(filename, 'r') as zip_ref:
        zip_ref.extractall()

def installLogstash(directory):
    source = "./ecs-logstash-mappings-Dev/pipeline/"
    if directory.endswith('/'):
        path = directory + "CorelightPipelines"
    else:
        path = directory + "/CorelightPipelines"
    if os.path.exists(directory):
        if not os.path.exists(path):
            shutil.copytree(source, path)
        else:
            print("the path %s exists have if you are updating the please select the update operation" % path)
            sys.exit(1)
    else:
        print("The path you entered does not exist")
        sys.exit(1)    
    
def updateLogstash(directory):
    source = "./ecs-logstash-mappings-Dev/pipeline/"
    tcp = ""
    path = directory + "/CorelightPipelines"
    if os.path.exists(directory):
        fileList=os.listdir(source)
        for filename in fileList:
            shutil.copy2(os.path.join(source,filename), path)

def enableIngest(ingest_type, raw, logstashLocation):
    ls_pipeline_install_dir = logstashLocation + "/CorelightPipelines/"
    tcp = "0002-corelight-ecs-tcp-input.conf"
    ssl = "0002-corelight-ecs-tcp-ssl_tls-input.conf"
    hec = "0002-corelight-ecs-http-for_splunk_hec.conf"
    kafka = "0002-corelight-ecs-kafka-input.config"
    tcpRaw = "0002-corelight-ecs-tcp-input-codec_disabled_to_keep_raw_message.conf"
    sslRaw = "0002-corelight-ecs-tcp-ssl_tls-input-codec_disabled_to_keep_raw_message.conf"
    hecRaw = "0002-corelight-ecs-http-for_splunk_hec-codec_disabled_to_keep_raw_message.conf"
    kafkaRaw = "0002-corelight-ecs-kafka-input-codec_disabled_to_keep_raw_message.config"
    
    if raw:
        if ingest_type == "tcp":
            source = ls_pipeline_install_dir + tcpRaw + ".disabled"
            dest = ls_pipeline_install_dir + tcpRaw 
        if ingest_type == "ssl":
            source = ls_pipeline_install_dir + sslRaw + ".disabled"
            dest = ls_pipeline_install_dir + sslRaw 
        if ingest_type == "hec":
            source = ls_pipeline_install_dir + hecRaw + ".disabled"
            dest = ls_pipeline_install_dir + hecRaw 
        if ingest_type == "kafka":
            source = ls_pipeline_install_dir + kafkaRaw + ".disabled"
            dest = ls_pipeline_install_dir + kafkaRaw 
    else:
        if ingest_type == "tcp":
            source = ls_pipeline_install_dir + tcp + ".disabled"
            dest = ls_pipeline_install_dir + tcp
        if ingest_type == "ssl":
            source = ls_pipeline_install_dir + ssl + ".disabled"
            dest = ls_pipeline_install_dir + ssl
        if ingest_type == "hec":
            source = ls_pipeline_install_dir + hec + ".disabled"
            dest = ls_pipeline_install_dir + hec
        if ingest_type == "kafka":
            source = ls_pipeline_install_dir + kafka + ".disabled"
            dest = ls_pipeline_install_dir + kafka 
    shutil.copy(source, dest)

def postPorcessing(logstashLocation, datastream, logstashVersion):
    ls_pipeline_install_dir = logstashLocation + "/CorelightPipelines/"
    if logstashVersion:
        sedCommand = 'sed -i "s/#ecs_compatibility =>/ecs_compatibility =>/" ' + ls_pipeline_install_dir + '/*.conf'
        subprocess.call([sedCommand],shell=True)
    if datastream:
        filename = ls_pipeline_install_dir + "0101-corelight-ecs-user_defined-set_indexing_strategy-filter.conf.disabled"
        f = open(filename)
        ds = f.read()
        if '=> "VAR_CORELIGHT_INDEX_STRATEGY"' in ds:
            dsEnabled = ds.replace('=> "VAR_CORELIGHT_INDEX_STRATEGY"', '=> "datastream"')
            f.close()
            dsOut = ls_pipeline_install_dir + "0101-corelight-ecs-user_defined-set_indexing_strategy-filter.conf"
            f = open(dsOut, "wt")
            f.write(dsEnabled)
            f.close()

def exportToElastic(session, baseURI, filePath, pipeline, path,  retry=4):
    filename = filePath + pipeline
    if pipeline != "zeek-enrichment-conn-policy/_execute":
        with open(filename) as f:
            postData = f.read()
    else:
        postData = ""
    run = 1
    uri = baseURI + path + pipeline
    
    response = 0
    while run <= retry and response != 200:
        run = run + 1
        response = session.put(uri, data=postData, timeout=10)
        response = checkRequest(response)
        if response == 400 or response == 409:
            print(response)

    if response == 200:
        return 
    else:
        print("Error uploading %s status code %s" %(pipeline, response),file=sys.stderr)
        print("URI = %s" % uri)
        sys.exit(1)


def elasticDel(session, baseURI, pipeline,  retry):

    uri = baseURI + "/_ingest/pipeline/"  + pipeline
    if pipeline.endswith("-policy"):
        uri = baseURI + "/_enrich/policy/" + pipeline

    print("deleting uri = %s" % uri)
    response = session.delete(uri, timeout=5)
    result = checkRequest(response)
    return result

def get_config():
    """Return a baseURI and session"""

    s = requests.Session()
    s.headers={'Content-Type': 'application/json'}

    print("\nEnter the information to connect to your Elasticsearch cluster.\n")
    ipHost = input("Hostname or IP: ")
    port = input_int("Port")
    auth = input_bool("Use user and password authentication?", default=True)

    if auth:
        user = input("User: ")
        password = input("Password: ")
        s.auth = (user, password)
    secure = input_bool("Use https?")
    ignoreCertErrors = False
    if secure:
        ignoreCertErrors = input_bool("Would you like to ignore certificate errors?", default=False)
    s.verify = not ignoreCertErrors

    print("You have entered the following parameters to connect to your cluster: \n - Host/IP: %s \n - Port: %s \n - HTTP/HTTPS: %s" %(ipHost, port, secure))
    if auth:
        print(" -User: %s \n -Password: %s" %(user, password))
    if secure:
        print(" - Ignore Certificate Errors: %s" % ignoreCertErrors)

    proto = "https" if secure else "http"
    baseURI = proto + "://" + ipHost + ":" + str(port)
    return baseURI, s

def datastreams(session, baseURI, logstash,updateTemplates):
    source = "./templates-component/data_stream/"
    component = source + "component_template/"
    ilm = source + "ilm_policy/"
    index = source + "index_template/"
    ingest = source + "use_ingest_pipeline/"
    fileList=os.listdir(component)
    for filename in fileList:
        exportToElastic(session, baseURI, component, filename, "/_component_template/", retry=4)
    if not updateTemplates:
        fileList=os.listdir(ilm)
        for filename in fileList:
            exportToElastic(session, baseURI, ilm, filename, "/_ilm/policy/", retry=4)
    
    fileList=os.listdir(index)
    for filename in fileList:
        exportToElastic(session, baseURI, index, filename, "/_index_template/", retry=4)
    if not logstash:
        exportToElastic(session, baseURI, ingest, "corelight-ds-component_template-use_ingest_pipeline-settings", "/_component_template/", retry=4)
        # exportToElastic(session, baseURI, ingest, "corelight-ds-index_template-main_logs_use_ingest_pipeline", "/_index_template/", retry=4)
        exportToElastic(session, baseURI, ingest, "corelight-ds-index_template-metrics_and_stats", "/_index_template/", retry=4)
        exportToElastic(session, baseURI, ingest, "corelight_postprocess_index_naming_pipeline", "/_ingest/pipeline/", retry=4)

def component( session, baseURI, logstash, updateTemplates ):
    source = "./templates-component/non_data_stream/"
    component = source + "component_template/"
    ilm = source + "ilm_policy/"
    index = source + "index_template/"
    ingest = source + "use_ingest_pipeline/"
    fileList=os.listdir(component)
    for filename in fileList:
         exportToElastic(session, baseURI, component,filename, "/_component_template/", retry=4)
    if not updateTemplates:
        fileList=os.listdir(ilm)
        for filename in fileList:
            exportToElastic(session, baseURI, ilm, filename, "/_ilm/policy/", retry=4)
    fileList=os.listdir(index)
    for filename in fileList:
        exportToElastic(session, baseURI, index, filename, "/_index_template/", retry=4)
    if not logstash:
        exportToElastic(session, baseURI, ingest, "corelight-non-ds-component_template-use_ingest_pipeline-settings", "/_component_template/", retry=4)
        exportToElastic(session, baseURI, ingest, "corelight-non-ds-index_template-main_logs_use_ingest_pipeline", "/_index_template/", retry=4)
        exportToElastic(session, baseURI, ingest, "corelight-non-ds-index_template-metrics_and_stats", "/_index_template/", retry=4)

def index(session, baseURI, logstash,updateTemplates):
    source = "./templates-component/templates-legacy/"
    ingest = source + "use_ingest_pipeline/"
    fileList=os.listdir(source)
    for filename in fileList:
        exportToElastic(session, baseURI, source, filename, "/_template/", retry=4)
    
    if not logstash:
        fileList=os.listdir(ingest)
        for filename in fileList:
                exportToElastic(session, baseURI, ingest, filename, "/_template/", retry=4)

def uploadIngestPipelines(session,baseURI):
    source = "./ecs-mapping-master/automatic_install/"
    fileList=os.listdir(source)
    for filename in fileList:
        if "deprecated" not in filename:
            exportToElastic(session, baseURI, source, filename, "/_ingest/pipeline/", retry=4)


def main():

    updateTemplates = False
    logstashRepo="ecs-logstash-mappings/archive/refs/heads/Dev.zip"
    ingestRepo="ecs-mapping/archive/refs/heads/master.zip"
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    baseURI, session = get_config()
    testConnection(session, baseURI)
    logstash = input_bool("Will you be using a Logstash pipeline?", default=True)
    templatesOnly = input_bool("Will you only be installing Templates, if using ingest Pipeline enter No?", default=False)
    if templatesOnly:
        updateTemplates = input_bool("Is this a update to existing template? If so ILM will not be installed", default=False)
    if not updateTemplates:
        if logstash:
            cont = input_bool("This script needs to be run on the Logstash box. Does this box have Logstash running and is the Logstash ingesting?", default=True)
            if cont:
                #Answer Yes if you are in a offline or Airgaped enviorment 
                # Then give the filename and location and it will run
                download = input_bool("Have you downloaded logstash repo?", default=False)
                if download:
                    filename = input("Please enter the filename for the Zip file of the Logstash Pipeline repo? <note it need to be in the same directorey as installer>: ")
                else:   
                    fileName=download_repository( logstashRepo )
                unzipGit(fileName)
            
                logstashLocation = input("Enter the Logstash location to store the piepline files in: ")
                update=input_bool("Are you upgrading an existing Corelight Logstsh Pipeline?", default=False)
                if not update:
                    installLogstash(logstashLocation)
                    logstashVersion = input_bool("Are you running Logstash version 8.x or higher?", default=True)
                    raw = input_bool("Do you want to keep the raw message, this will incerease storage space?", default=False)
                    tcp = input_bool("Are you sending data to logstsh over JSON over TCP?:", default=False)
                    if tcp:
                        ssl = input_bool("Will you be enableing SSL?", default=False)
                        if ssl:
                            enableIngest("ssl", raw, logstashLocation)
                        else:
                            enableIngest("tcp", raw, logstashLocation)
                    else:
                        kafka = input_bool("Are sending data to Logstsh via Kafka?:", default=False)
                        if kafka:
                            enableIngest("kafka", raw, logstashLocation)
                        else:
                            hec = input_bool("Are sending data to logstsh over HTTP Event Collector?:", default=False)
                            if hec:
                                enableIngest("hec", raw, logstashLocation)
                else:
                    updateLogstash(logstashLocation)
            else:
                print("Please run script again on Logstash server")
                print("Strange things are afoot at the Circle-K.")
                sys.exit(1)
        else:
            #Answer Yes if you are in a offline or Airgaped enviorment 
            # Then give the filename and location and it will run
            download = input_bool("Have you downloaded Ingest repo?", default=False)
            if download:
                fileName = input("Please enter the filename for the Zip file of the Logstash Pipeline repo? <note it need to be in the same directorey as installer>: ")
            else: 
                fileName=download_repository( ingestRepo )
            unzipGit(fileName)
            uploadIngestPipelines(session,baseURI)
    templateDS = input_bool("Will you be useing Datastreams?", default=True)
    if templateDS:
        datastreams(session,baseURI,logstash,updateTemplates)
        if logstash and not updateLogstash:
            postPorcessing(logstashLocation, templateDS, logstashVersion)
    else:
        templateComponent = input_bool("Will you be useing Component Templates?", default=True)
        if templateComponent:
            component( session, baseURI, logstash, updateTemplates )
            if logstash and not updateLogstash:
                postPorcessing(logstashLocation, templateDS, logstashVersion)
        else:
            templateLegcy = input_bool("Will you be using Legcy Templates? This is not supported on version 8.x and above?", default=False)
            if templateLegcy:
                index(session,baseURI,logstash,updateTemplates)
                if logstash and not updateLogstash:
                    postPorcessing(logstashLocation, templateDS, logstashVersion)

if __name__ == "__main__":
    main()
else:
    main()
