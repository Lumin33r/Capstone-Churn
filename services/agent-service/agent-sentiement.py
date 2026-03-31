from dotenv import load_dotenv
import boto3, uuid, os

load_dotenv()

AGENT_SENTIMENT_NAME: str | None = os.getenv(key="AGENT_SENTIMENT_NAME")

bedrock = boto3.client('bedrock', region='us-east-1')
bedrock_agent = boto3.client("bedrock-agent-runtime")


# Helper Method to get the Agent Alias ID
def _get_agent_and_alias() -> tuple[str, str]:
    agents = bedrock.list_agents()["agentSummaries"]
    
    if not agents:
        raise StopIteration("No agents found")
    
    # Find agent by name
    agent = next(a for a in agents if a["agentName"] == AGENT_SENTIMENT_NAME)
    agent_id = agent["agentId"]
    
    # Get alias
    aliases = bedrock.list_agent_aliases(agentId=agent_id)["agentAliasSummaries"]
    alias_id = aliases[0]["agentAliasId"]  # pick first alias
    
    return agent_id, alias_id

_, AGENT_SENTIMENT_ALIAS = _get_agent_and_alias()

response = bedrock_agent.invoke_agent(
    agentId=AGENT_SENTIMENT_NAME,
    agentAliasId=AGENT_SENTIMENT_ALIAS,
    sessionId=str(object=uuid.uuid4),
    inputText="All do you feel to treat me like you do?"
)