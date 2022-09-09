#!/usr/bin/env python3

from asyncore import file_wrapper
from distutils import filelist
import shutil
from this import d, s
import requests
from urllib3.exceptions import InsecureRequestWarning
import glob
import time
import sys
import zipfile
import os
import random

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

def download_repostory(name):
    randomNum = random.randint(0,100)
    filename = "output" + str(randomNum) + ".zip"
    host = "https://github.com/"
    organization = "corelight/"
    url = host + organization + name 
    with requests.get(url, stream=True) as r:
        with open(filename, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
    return filename

def unzipGit(file):
    with zipfile.ZipFile(file, 'r') as zip_ref:
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
            print("the path %s exists have if you are updateing the please select the update operation" % path)
            sys.exit(1)
    else:
        print("The path you entered does not exist")
        sys.exit(1)    
    
def updateLogstash(directory):
    source = "./ecs-logstash-mappings-dev/pipeline/"
    tcp = ""
    path = directory + "/pipelines"
    if os.path.exists(directory):
        fileList=os.listdir(source)
        for file in fileList:
            shutil.copy2(os.path.join(source,file), path)

def enableIngest(type,raw, logstashLocation):
    dir = logstashLocation + "/CorelightPipelines/"
    tcp = "0002-corelight-ecs-tcp-input.conf"
    ssl = "0002-corelight-ecs-tcp-ssl_tls-input.conf"
    hec = "0002-corelight-ecs-http-for_splunk_hec.conf"
    kafka = "0002-corelight-ecs-kafka-input.config"
    tcpRaw = "0002-corelight-ecs-tcp-input-codec_disable_to_keep_raw_message.conf"
    sslRaw = "0002-corelight-ecs-tcp-ssl_tls-input-codec_disable_to_keep_raw_message.conf"
    hecRaw = "0002-corelight-ecs-http-for_splunk_hec-codec_disable_to_keep_raw_message.conf"
    kafkaRaw = "0002-corelight-ecs-kafka-input-codec_disable_to_keep_raw_message.config"

    if raw:
        if type == "tcp":
            source = dir + tcpRaw + ".disabled"
            dest = dir + tcpRaw 
        if type == "ssl":
            source = dir + sslRaw + ".disabled"
            dest = dir + sslRaw 
        if type == "hec":
            source = dir + hecRaw + ".disabled"
            dest = dir + hecRaw 
        if type == "kafka":
            source = dir + kafkaRaw + ".disabled"
            dest = dir + kafkaRaw 
    else:
        if type == "tcp":
            source = dir + tcp + ".disabled"
            dest = dir + tcp
        if type == "ssl":
            source = dir + ssl + ".disabled"
            dest = dir + ssl
        if type == "hec":
            source = dir + hec + ".disabled"
            dest = dir + hec
        if type == "kafka":
            source = dir + kafka + ".disabled"
            dest = dir + kafka 
    shutil.copy(source, dest)

def exportToElastic(session, baseURI, filePath, pipeline, path,  retry=4):
    print("Trying to upload pipeline: %s" % pipeline)
    file = filePath + pipeline
    if pipeline != "zeek-enrichment-conn-policy/_execute":
        with open(file) as f:
            postData = f.read()
    else:
        postData = ""
    run = 1
    uri = baseURI + path + pipeline
    
    print("URI = %s" % uri)   
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
    for file in fileList:
        exportToElastic(session, baseURI, component, file, "/_component_template/", retry=4)
    if not updateTemplates:
        fileList=os.listdir(ilm)
        for file in fileList:
            exportToElastic(session, baseURI, ilm,file, "/_ilm/policy/", retry=4)
    
    fileList=os.listdir(index)
    for file in fileList:
        exportToElastic(session, baseURI, index,file, "/_index_template/", retry=4)
    if not logstash:
        fileList=os.listdir(ingest)
        for file in fileList:
            exportToElastic(session, baseURI, ingest,file, "/_index_template/", retry=4)

def componet(session, baseURI, logstash,updateTemplates):
    source = "./templates-component/non_data_stream/"
    component = source + "component_template/"
    ilm = source + "ilm_policy/"
    index = source + "index_template/"
    ingest = source + "use_ingest_pipeline/"
    fileList=os.listdir(component)
    for file in fileList:
         exportToElastic(session, baseURI, component,file, "/_component_template/", retry=4)
    if not updateTemplates:
        fileList=os.listdir(ilm)
        for file in fileList:
            exportToElastic(session, baseURI, ilm, file, "/_ilm/policy/", retry=4)
    fileList=os.listdir(index)
    for file in fileList:
        exportToElastic(session, baseURI, index, file, "/_index_template/", retry=4)
    if not logstash:
        fileList=os.listdir(ingest)
        for file in fileList:
            exportToElastic(session, baseURI, ingest, file, "/_component_template/", retry=4)

def index(session, baseURI, logstash,updateTemplates):
    source = "./templates-component/templates-legcay/"
    ingest = source + "use_ingest_pipeline/"
    fileList=os.listdir(source)
    for file in fileList:
        exportToElastic(session, baseURI, source, file, "/_template/", retry=4)
    
    if not logstash:
        fileList=os.listdir(ingest)
        for file in fileList:
                exportToElastic(session, baseURI, ingest, file, "/_template/", retry=4)

def uploadIngestPipelines(session,baseURI):
    source = "./ecs-mapping-master/automatic_install/"
    fileList=os.listdir(source)
    for file in fileList:
        exportToElastic(session, baseURI, source, file, "/_ingest/pipeline/", retry=4)


def main():

    updateTemplates = False
    logstashRepo="ecs-logstash-mappings/archive/refs/heads/Dev.zip"
    ingestRepo="ecs-mapping/archive/refs/heads/master.zip"
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    baseURI, session = get_config()
    testConnection(session, baseURI)
    logstash = input_bool("Will you be useing Logstash pipelines?", default=True)
    templatesOnly = input_bool("Will you only be install Templates, if useing ingest Pipeline enter No?", default=False)
    if templatesOnly:
        updateTemplates = input_bool("Is this a update to existing template? If so ILM will not be installed", default=False)
    if not updateTemplates:
        if logstash:
            cont = input_bool("This script need to be run on the logstash box. Does this box have logstash running and is the Logstash ingest?", default=True)
            if cont:
                fileName=download_repostory(logstashRepo)
                unzipGit(fileName)
            
                logstashLocation = input("Enter the logstash location to put the file pieplines in: ")
                update=input_bool("Are you upgrading existing Corelight Logstsh Pipeline?", default=False)
                if not update:
                    installLogstash(logstashLocation)
                    raw = input_bool("Do you want to keep the raw message will incerease storage space?", default=False)
                    tcp = input_bool("Are sending doat to logstsh over JSON over TCP?:", default=False)
                    if tcp:
                        ssl = input_bool("Will you be enableing SSL?", default=False)
                        if ssl:
                            enableIngest("ssl", raw, logstashLocation)
                        else:
                            enableIngest("tcp", raw, logstashLocation)
                    else:
                        kafka = input_bool("Are sending doat to logstsh over Kafka?:", default=False)
                        if kafka:
                            enableIngest("kafka", raw, logstashLocation)
                        else:
                            hec = input_bool("Are sending doat to logstsh over HTTP Event Collector?:", default=False)
                            if hec:
                                enableIngest("hec", raw, logstashLocation)
                else:
                    updateLogstash(logstashLocation)
            else:
                print("Please run script again on Logstash server")
                print("Strange things are afoot at the Circle-K.")
                sys.exit(1)
        else:
            fileName=download_repostory(ingestRepo)
            unzipGit(fileName)
            uploadIngestPipelines(session,baseURI)
    templateDS = input_bool("Will you be useing Datastreams?", default=True)
    if templateDS:
        datastreams(session,baseURI,logstash,updateTemplates)
    else:
        templateComponent = input_bool("Will you be useing Component Templates?", default=True)
        if templateComponent:
            componet(session,baseURI,logstash,updateTemplates)
        else:
            templateLegcy = input_bool("Will you be useing Legcy Templates? This is not supported on version 8.x and above?", default=False)
            if templateLegcy:
                index(session,baseURI,logstash,updateTemplates)

main()




