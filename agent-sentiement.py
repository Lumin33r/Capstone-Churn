import boto3

bedrock = boto3.client('bedrock', region='us-east-1')

bedrock_agent = boto3.client("bedrock-agent-runtime")

response = bedrock_agent.invoke_agent(
    agentId="YOUR_AGENT_ID",
    agentAliasId="YOUR_ALIAS_ID",
    sessionId="user-session-123",
    inputText="What were our Q3 revenue numbers?"
)