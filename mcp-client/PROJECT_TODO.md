# Overall Project Goal
* We want to create a 24/7 devops agent which will detect and remediate alerts given our architecture of Kubernetes, Google Cloud, Victoria metrics, Victoria logs, Grafana and Bitbucket pipelines for CI. We also want the bot to be able to answer questions based on questions and also provide daily reports. See previous chat session https://claude.ai/chat/93d7fdc1-6d08-4a7b-8105-324b4eff626c for the section Core Architecture for 24/7 Monitoring. The difference is we dont want to use claude, we want to use a local self hosted model for cost purposes. We do not want to use n8n for now. 

# Sample Use Cases 
1. Every minute check for re-runnable failed pipelines and re-run it. There are a certain set of pipeline failures which if we simply re-ran it, it would pass like network blips to upstream resources. 
2. Continuously check for common pipeline failures and see if it correlates to a pull request or commit. 
3. Give me a daily summary of the state of pipelines, including successes, failures, common step failures, average time of pipelines, average tiem per step. 
4. Give me a summary of the kubernetes cluster including failing pods, throttled pods, any issues in kube events
5. Track disk usage on any kubeernetes workloads which have PVCs. Determine if we need to scale
6. In real time, track pipeline builds and determine if we need to scale cloud VMs up or down
7. Give me a daily report of my specific GCP projects, including if we scaled VMs up/down, daily cost breakdown, Artifact registry size, network traffic, etc. 

# Requirements
1. The project should be maintainable by a human. We should not have complex unreadable code. It should be understandable and readable with good comments.
2. We should have clear separation of duties for each aspect of this project, following normal best practices. 
3. There needs to be a way to ask the bot questions in addition to having an autonomous agent which is a 24/7 member of the devops team.
4. If there are pre-built mcp servers by the maintaining organization, we should use it like https://github.com/grafana/mcp-grafana. 
5. Infrastructure for this agent should be locally hosted so cost isnt an issue of running something 24/7. We have plenty of CPU compute in my production environment. We will eventually host it in kubernetes but for now, running everything in python or docker compose is fine. We just shouldnt rely on a GPU. 
6. In the future if we wanted to connect another client to an MCP server, we should be able to. 

# Feature Requests
1. The agent should keep a memory so it's an actual conversation instead of reiterating everything every time. 
2. The agent should in addition to having a chat interface, it should have an agent mode which runs constnatly and is constantly looking for certain 
3. The client as it stands seems not production ready. Seems more like a good example project but we need it to be ready for production. For example, the iterating 10 times, seems like we could do better there. 