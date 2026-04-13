gcloud pubsub topics create act-topic --project=demucs-lab
Created topic [projects/demucs-lab/topics/classify-topic].
Created topic [projects/demucs-lab/topics/act-topic].
varma@Mahendras-MacBook-Pro cloud-file-orchestrator % gcloud run deploy drbfo-inspect \
  --project demucs-lab \
  --region us-central1 \
  --source ./services/inspect_worker \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=demucs-lab,UPLOAD_BUCKET=drbfo-uploads,ORG_BUCKET=drbfo-organized,TOPIC_INGEST=ingest-topic,TOPIC_CLASSIFY=classify-topic,TOPIC_ACT=act-topic,FIRESTORE_COLLECTION=jobs

Deploying from source requires an Artifact Registry Docker repository to store built containers. A repository named [cloud-run-source-deploy] in region [us-central1] will be created.

Do you want to continue (Y/n)?  y

Building using Buildpacks and deploying container to Cloud Run service [drbfo-inspect] in project [demucs-lab] region [us-central1]
✓ Building and deploying new service... Done.                                                                                                                                                                                                       
  ✓ Creating Container Repository...                                                                                                                                                                                                                
  ✓ Uploading sources...                                                                                                                                                                                                                            
  ✓ Building Container... Logs are available at [https://console.cloud.google.com/cloud-build/builds;region=us-central1/46c5eacb-946e-4731-9347-30911c2bcb26?project=227780936315].                                                                 
  ✓ Creating Revision...                                                                                                                                                                                                                            
  ✓ Routing traffic...                                                                                                                                                                                                                              
  ✓ Setting IAM Policy...                                                                                                                                                                                                                           
Done.                                                                                                                                                                                                                                               
Service [drbfo-inspect] revision [drbfo-inspect-00001-6jf] has been deployed and is serving 100 percent of traffic.
Service URL: https://drbfo-inspect-227780936315.us-central1.run.app





varma@Mahendras-MacBook-Pro cloud-file-orchestrator % gcloud run deploy drbfo-api \
  --project demucs-lab \
  --region us-central1 \
  --source . \
  --allow-unauthenticated \
  --set-env-vars \
GCP_PROJECT_ID=demucs-lab,\
UPLOAD_BUCKET=drbfo-uploads,\
PROCESSED_BUCKET=drbfo-organized,\
INGEST_TOPIC=ingest-topic,\
CLASSIFY_TOPIC=drbfo-classify,\
ACT_TOPIC=drbfo-act,\
JOBS_COLLECTION=jobs

Building using Buildpacks and deploying container to Cloud Run service [drbfo-api] in project [demucs-lab] region [us-central1]
✓ Building and deploying... Done.                                                                                                                                                                                                                   
  ✓ Uploading sources...                                                                                                                                                                                                                            
  ✓ Building Container... Logs are available at [https://console.cloud.google.com/cloud-build/builds;region=us-central1/28daf88f-b25d-46ed-8342-c96bd5fc4a93?project=227780936315].                                                                 
  ✓ Creating Revision...                                                                                                                                                                                                                            
  ✓ Routing traffic...                                                                                                                                                                                                                              
  ✓ Setting IAM Policy...                                                                                                                                                                                                                           
Done.                                                                                                                                                                                                                                               
Service [drbfo-api] revision [drbfo-api-00004-d6g] has been deployed and is serving 100 percent of traffic.
Service URL: https://drbfo-api-227780936315.us-central1.run.app




varma@Mahendras-MacBook-Pro cloud-file-orchestrator % gcloud run deploy drbfo-inspect \
  --project demucs-lab \
  --region us-central1 \
  --source ./services/inspect_worker \
  --allow-unauthenticated \
  --set-env-vars \
GCP_PROJECT_ID=demucs-lab,\
UPLOAD_BUCKET=drbfo-uploads,\
PROCESSED_BUCKET=drbfo-organized,\
INGEST_TOPIC=ingest-topic,\
CLASSIFY_TOPIC=drbfo-classify,\
ACT_TOPIC=drbfo-act,\
JOBS_COLLECTION=jobs

Building using Buildpacks and deploying container to Cloud Run service [drbfo-inspect] in project [demucs-lab] region [us-central1]
✓ Building and deploying... Done.                                                                                                                                                                                                                   
  ✓ Uploading sources...                                                                                                                                                                                                                            
  ✓ Building Container... Logs are available at [https://console.cloud.google.com/cloud-build/builds;region=us-central1/e6cde5bd-a6d1-4013-bf30-7d2e1ad8fda9?project=227780936315].                                                                 
  ✓ Creating Revision...                                                                                                                                                                                                                            
  ✓ Routing traffic...                                                                                                                                                                                                                              
  ✓ Setting IAM Policy...                                                                                                                                                                                                                           
Done.                                                                                                                                                                                                                                               
Service [drbfo-inspect] revision [drbfo-inspect-00002-cdw] has been deployed and is serving 100 percent of traffic.
Service URL: https://drbfo-inspect-227780936315.us-central1.run.app







varma@Mahendras-MacBook-Pro cloud-file-orchestrator % gcloud run deploy drbfo-classify \
  --project demucs-lab \
  --region us-central1 \
  --source ./services/classify_worker \
  --allow-unauthenticated \
  --set-env-vars \
GCP_PROJECT_ID=demucs-lab,\
UPLOAD_BUCKET=drbfo-uploads,\
PROCESSED_BUCKET=drbfo-organized,\
INGEST_TOPIC=ingest-topic,\
CLASSIFY_TOPIC=drbfo-classify,\
ACT_TOPIC=drbfo-act,\
JOBS_COLLECTION=jobs

Building using Buildpacks and deploying container to Cloud Run service [drbfo-classify] in project [demucs-lab] region [us-central1]
✓ Building and deploying new service... Done.                                                                                                                                                                                                       
  ✓ Uploading sources...                                                                                                                                                                                                                            
  ✓ Building Container... Logs are available at [https://console.cloud.google.com/cloud-build/builds;region=us-central1/fe520acc-7bd4-4f7e-bdda-a9fd79aa6cc4?project=227780936315].                                                                 
  ✓ Creating Revision...                                                                                                                                                                                                                            
  ✓ Routing traffic...                                                                                                                                                                                                                              
  ✓ Setting IAM Policy...                                                                                                                                                                                                                           
Done.                                                                                                                                                                                                                                               
Service [drbfo-classify] revision [drbfo-classify-00001-bvz] has been deployed and is serving 100 percent of traffic.
Service URL: https://drbfo-classify-227780936315.us-central1.run.app







varma@Mahendras-MacBook-Pro cloud-file-orchestrator % gcloud run deploy drbfo-act \
  --project demucs-lab \
  --region us-central1 \
  --source ./services/act_worker \
  --allow-unauthenticated \
  --set-env-vars \
GCP_PROJECT_ID=demucs-lab,\
UPLOAD_BUCKET=drbfo-uploads,\
PROCESSED_BUCKET=drbfo-organized,\
INGEST_TOPIC=ingest-topic,\
CLASSIFY_TOPIC=drbfo-classify,\
ACT_TOPIC=drbfo-act,\
JOBS_COLLECTION=jobs

Building using Buildpacks and deploying container to Cloud Run service [drbfo-act] in project [demucs-lab] region [us-central1]
✓ Building and deploying new service... Done.                                                                                                                                                                                                       
  ✓ Uploading sources...                                                                                                                                                                                                                            
  ✓ Building Container... Logs are available at [https://console.cloud.google.com/cloud-build/builds;region=us-central1/9701ee45-a39c-49cd-9539-459bf606c990?project=227780936315].                                                                 
  ✓ Creating Revision...                                                                                                                                                                                                                            
  ✓ Routing traffic...                                                                                                                                                                                                                              
  ✓ Setting IAM Policy...                                                                                                                                                                                                                           
Done.                                                                                                                                                                                                                                               
Service [drbfo-act] revision [drbfo-act-00001-t2q] has been deployed and is serving 100 percent of traffic.
Service URL: https://drbfo-act-227780936315.us-central1.run.app
varma@Mahendras-MacBook-Pro cloud-file-orchestrator % 




gcloud pubsub subscriptions create act-sub \
  --topic=drbfo-act \
  --push-endpoint="https://<ACT_URL>/pubsub" \
  --push-auth-service-account="$(gcloud config get-value core/account)" \
  --project=demucs-lab