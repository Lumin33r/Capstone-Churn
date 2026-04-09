# Guardrail resource to manage harmful content 
resource "aws_bedrock_guardrail" "sentiment_analysis" {
  name        = "sentiment-analysis-guardrail"
  description = "Guardrail for sentiment analysis: block toxic, hateful, violent, abusive, self-harm, and PII content."

  blocked_input_messaging  = "Your request contains content that violates safety policies."
  blocked_outputs_messaging = "The model output was blocked due to safety policies."

  
  # Content Moderation Filters
  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }

    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }

    filters_config {
      type            = "VIOLENCE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }

    filters_config {
      type            = "SEXUAL"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }

    # Additional recommended filters
    filters_config {
      type            = "INSULTS"
      input_strength  = "HIGH"
      output_strength = "HIGH"    
    }

    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "HIGH"    
    }
  }

  
  # Sensitive Information (PII)
  sensitive_information_policy_config {
    pii_entities_config {
      type   = "EMAIL"
      action = "BLOCK"
    }

    pii_entities_config {
      type   = "PHONE"
      action = "BLOCK"
    }

    pii_entities_config {
      type   = "ADDRESS"
      action = "BLOCK"
    }

    # Additional PII categories you likely want
    pii_entities_config {
      type   = "NAME"
      action = "BLOCK"
    }

    pii_entities_config {
      type   = "US_BANK_ACCOUNT_NUMBER"
      action = "BLOCK"
    }

    pii_entities_config {
      type   = "INTERNATIONAL_BANK_ACCOUNT_NUMBER"
      action = "BLOCK"
    }

    pii_entities_config {
      type   = "US_SOCIAL_SECURITY_NUMBER"
      action = "BLOCK"
    }

    pii_entities_config {
      type   = "CREDIT_DEBIT_CARD_NUMBER"
      action = "BLOCK"
    }


     pii_entities_config {
       type   = "US_PASSPORT_NUMBER"
       action = "BLOCK"
     }

    pii_entities_config {
      type   = "IP_ADDRESS"
      action = "BLOCK"
    }
  }

  
  # Topic Restrictions
  topic_policy_config {
    topics_config {
      name       = "Self-harm"
      definition = "Content encouraging, describing, or facilitating self-harm or suicide."
      type       = "DENY"
    }

    topics_config {
      name       = "Violence"
      definition = "Content describing or encouraging violence toward individuals or groups."
      type       = "DENY"
    }

    topics_config {
      name       = "Illicit Behavior"
      definition = "Content encouraging illegal activity, fraud, or financial scams."
      type       = "DENY"
    }

    topics_config {
      name       = "Sensitive Customer Data"
      definition = "Requests for personal customer data such as names, phone numbers, addresses, or account information."
      type       = "DENY"
    }
  }
}
