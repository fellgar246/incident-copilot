# Architecture

```mermaid
flowchart TD
  alarm[CloudWatch alarm] --> bus[EventBridge]
  bus --> queue[SQS]
  queue --> worker[Incident worker Lambda]
  worker --> table[(DynamoDB)]
  dash[Next.js on S3 and CloudFront] --> api[API Gateway]
  api --> lambda[FastAPI Lambda]
  lambda --> table
  lambda --> bus
  lambda --> runtime[AgentCore Runtime]
  runtime --> gateway[AgentCore Gateway]
  gateway --> logs[CloudWatch logs and metrics]
  gateway --> deploys[Deployments table]
  gateway --> kb[Knowledge corpus in S3]
  lambda --> approval[Human approval]
  approval --> remediate[Remediation tool]
  remediate --> table
```

The dashboard is the product surface. Reading an incident does not require the AWS Console.

The same loop, as a sequence:

```text
Detect → Queue → Investigate → Retrieve → Reason → Propose
              → Approve → Act → Observe → Evaluate → Measure cost
```
