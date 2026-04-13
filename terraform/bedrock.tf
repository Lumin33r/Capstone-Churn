
# ── Bedrock foundational model     ───────────────────────

data "aws_bedrock_foundation_model" "agent" {
  model_id = var.agent_model.id
}


resource "aws_bedrockagent_agent" "bedrock_agent" {
  agent_name              = "${var.environment}-${var.agent_name}"
  agent_resource_role_arn = aws_iam_role.bedrock_role.arn
  description             = "Agent: ${var.agent_model.display} | Env: ${var.environment}"
  foundation_model        = data.aws_bedrock_foundation_model.agent.model_id
  instruction             = var.agent_instruction
  idle_session_ttl_in_seconds = var.idle_session_ttl
  prepare_agent           = true

  tags = {
    Team        = var.team_name
    Environment = var.environment
    Model       = var.agent_model.display
  }
}

resource "aws_bedrockagent_agent_alias" "bedrock_endpoint" {
  agent_alias_name = "${var.environment}-live"
  agent_id         = aws_bedrockagent_agent.bedrock_agent.agent_id
  description      = "Live alias for ${var.environment}"

  tags = {
    Team        = var.team_name
    Environment = var.environment
    Model       = var.agent_model.display
  }
}