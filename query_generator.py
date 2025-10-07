import json
import re
from bedrock_client import BedrockClient, BedrockConfig
from logger import get_logger
from concern_risk_misc_naics import concerns_events, emerging_risks, misc_topics, naics_data

logger = get_logger(__name__)

# DynamoDB table schema
TABLE_SCHEMA = """
Table Name: CrawledData

Primary Key: 
- Partition Key: URL (String) - The unique URL of the crawled article
- Sort Key: DateTime (String) - ISO 8601 timestamp when the article was processed

Attributes:
- Title (String): Title of the article
- Source (String): Source website/publication of the article
- URL (String): The web address of the article
- Data (String): Full text content of the article
- Description (String): Brief description or excerpt from the article
- ReasonIdentified (String): AI-generated summary focusing on insurance-relevant risks and exposures
- Concerns (String): Semicolon-separated list of identified concern events (e.g., "injuries;property damage;lawsuits")
- EmergingRiskName (String): Semicolon-separated list of emerging risk categories (e.g., "Climate Change;PFAS;Ransomware")
- MiscTopics (String): Semicolon-separated list of miscellaneous insurance topics (e.g., "home ownership;personal auto")
- NAICSCODE (String): Industry classification code (e.g., "327910")
- NAICSDescription (String): Description of the NAICS code industry (e.g., "Abrasive Product Manufacturing")
- Tag (String): Classification tag - one of: "Current", "Potential New Trend", "Untagged", "Processing Error"

Available Values for Classification Fields:
- Concerns: {concerns}
- Emerging Risks: {emerging_risks}
- Misc Topics: {misc_topics}
- NAICS Codes: {naics_data}
"""

QUERY_GENERATION_PROMPT = """
<role>You are an expert at converting natural language queries into DynamoDB filter expressions and query parameters.</role>

<table_schema>
{schema}
</table_schema>

<task>
Convert the following user query into a structured JSON response that can be used to query DynamoDB.
</task>

<user_query>
{query}
</user_query>

<instructions>
1. Analyze the user's intent and identify which fields they're querying
2. Determine if this is a simple scan with filters or if specific keys are mentioned
3. For concerns, emerging risks, or misc topics - match against the available values provided in the schema
4. Generate appropriate filter expressions using DynamoDB syntax:
   - Use "attribute_exists(field)" to check if field exists
   - Use "contains(field, value)" for substring matching
   - DynamoDB does NOT support functions like lower() or upper()
   - For case-insensitive intent, assume data is pre-normalized (e.g., stored lowercase) or leave filtering to application layer
   - Use "field = value" for exact matching
   - Use "begins_with(field, value)" for prefix matching
   - Use "field IN (value1, value2)" for multiple value matching
   - Use "AND", "OR" for combining conditions
5. For date ranges, convert to ISO format and use comparison operators
6. ALWAYS set projection_attributes to null - we ALWAYS want ALL columns returned

</instructions>

<output_format>
Return ONLY valid JSON in this exact structure:

    "query_type": "scan" or "query",
    "partition_key": ("name": "URL", "value": "specific_url") or null,
    "filter_expression": "DynamoDB filter expression string" or null,
    "expression_attribute_names": ("#tag": "Tag", "#concerns": "Concerns") or null,
    "expression_attribute_values": (":tag_val": "Current", ":concern_val": "injuries") or null,
    "projection_attributes": null,
    "limit": 200,
    "explanation": "Brief explanation of what the query does"

IMPORTANT: projection_attributes MUST ALWAYS be null - we always return ALL columns from the database.
</output_format>

<examples>
User Query: "Show me all articles tagged as Current"
Response:

    "query_type": "scan",
    "partition_key": null,
    "filter_expression": "#tag = :tag_val",
    "expression_attribute_names": "#tag": "Tag",
    "expression_attribute_values": ":tag_val": "Current",
    "projection_attributes": null,
    "limit": 200,
    "explanation": "Scanning for all records where Tag equals 'Current'"

User Query: "Find articles about climate change with PFAS concerns"
Response:

    "query_type": "scan",
    "partition_key": null,
    "filter_expression": "contains(#emerg, :emerg_val1) AND contains(#emerg, :emerg_val2)",
    "expression_attribute_names": "#emerg": "EmergingRiskName",
    "expression_attribute_values": ":emerg_val1": "Climate Change", ":emerg_val2": "PFAS",
    "projection_attributes": null,
    "limit": 200,
    "explanation": "Finding articles with both Climate Change and PFAS in emerging risks"

User Query: "Show articles about lawsuits or property damage"
Response:

    "query_type": "scan",
    "partition_key": null,
    "filter_expression": "contains(#concerns, :concern1) OR contains(#concerns, :concern2)",
    "expression_attribute_names": "#concerns": "Concerns",
    "expression_attribute_values": ":concern1": "lawsuits", ":concern2": "property damage",
    "projection_attributes": null,
    "limit": 200,
    "explanation": "Finding articles containing lawsuits or property damage concerns"


User Query: "Show all articles"
Response:

    "query_type": "scan",
    "partition_key": null,
    "filter_expression": null,
    "expression_attribute_names": null,
    "expression_attribute_values": null,
    "projection_attributes": null,
    "limit": 200,
    "explanation": "Retrieving all articles from the database"

</examples>

<critical_rules>
- For Concerns, Emerging Risks, and Misc Topics: ALWAYS use values from the available lists in the schema
- Use "contains()" for fields that store semicolon-separated values
- Field names starting with uppercase letters need attribute name placeholders (#fieldname)
- Always include "limit" to prevent overwhelming results
- Set query_type to "query" ONLY if partition key (URL) is specifically mentioned
- For untagged records: filter_expression should check for Tag being "Untagged" OR attribute_not_exists(Tag). 
  (Empty string values must be handled in the application layer, not in DynamoDB.)
- CRITICAL: projection_attributes MUST ALWAYS be null - never restrict columns, always return ALL attributes
- expression_attribute_names should be null if no filter_expression uses them
- expression_attribute_values should be null if no filter_expression uses them
</critical_rules>

"""


class QueryGenerator:
    def __init__(self):
        self.bedrock = BedrockClient(BedrockConfig())
        self.model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
        
    def _prepare_schema(self) -> str:
        """Prepare schema with available values for classification fields."""
        return TABLE_SCHEMA.format(
            concerns=", ".join(concerns_events[:20]) + "...",  # Show sample
            emerging_risks=", ".join(emerging_risks[:20]) + "...",
            misc_topics=", ".join(misc_topics),
            naics_data=", ".join([f"{item['code']} - {item['description']}" for item in naics_data])
        )
    
    def generate_query(self, user_query: str) -> dict:
        """Generate DynamoDB query parameters from natural language query."""
        try:
            schema = self._prepare_schema()
            prompt = QUERY_GENERATION_PROMPT.format(
                schema=schema,
                query=user_query
            )
            
            response_text = self.bedrock.invoke_model(
                model_id=self.model_id,
                prompt=prompt,
                max_tokens=2000,
                temperature=0.0
            )

            print("response----------------",response_text)
            
            # Extract JSON from response
            query_params = self._extract_json(response_text)

            print("Query parameters:-----------", query_params)
            
            if not query_params:
                logger.error(f"Failed to generate query for: {user_query}")
                return self._get_default_query()
            
            logger.info(f"Generated query: {query_params.get('explanation', 'No explanation')}")
            return query_params
            
        except Exception as e:
            logger.error(f"Error generating query: {e}")
            return self._get_default_query()
    
    def _extract_json(self, response_text: str) -> dict:
        """Extract JSON from LLM response."""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            try:
                # Try to extract JSON from markdown
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                
                # Try to find any JSON-like structure
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
                
                return {}
            except Exception as e:
                logger.error(f"Failed to parse JSON: {e}")
                return {}
    
    def _get_default_query(self) -> dict:
        """Return a default query that shows all records."""
        return {
            "query_type": "scan",
            "partition_key": None,
            "filter_expression": None,
            "expression_attribute_names": None,
            "expression_attribute_values": None,
            "projection_attributes": None,
            "limit": 50,
            "explanation": "Showing all records (default query)"
        }
    
    def validate_query(self, query_params: dict) -> tuple[bool, str]:
        """Validate the generated query parameters."""
        required_fields = ["query_type", "limit"]
        
        for field in required_fields:
            if field not in query_params:
                return False, f"Missing required field: {field}"
        
        if query_params["query_type"] not in ["scan", "query"]:
            return False, "query_type must be 'scan' or 'query'"
        
        if query_params["query_type"] == "query" and not query_params.get("partition_key"):
            return False, "query type requires partition_key"
        
        return True, "Valid query"