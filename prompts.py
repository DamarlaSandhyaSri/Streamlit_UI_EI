SUMMARY_PROMPT = """
<role>You are a senior insurance industry analyst with 15+ years of experience in risk assessment and claims analysis.</role>

<task>
Analyze the provided article and create a concise summary that highlights insurance-relevant risks, exposures, and potential claims scenarios.
</task>

<instructions>
1. Focus specifically on:
   - Physical risks and hazards
   - Financial exposures
   - Liability concerns
   - Business interruption factors
   - Regulatory or compliance issues

2. Write 2-3 clear, professional sentences
3. Use insurance industry terminology where appropriate
4. Prioritize actionable insights over general observations
</instructions>

<output_format>
Return ONLY valid JSON in this exact structure:
"ReasonIdentified": "<your 2-3 sentence summary here>"
</output_format>

<article>
{text}
</article>
"""

CLASSIFY_PROMPT = """
<role>You are an expert insurance claims analyst specializing in risk categorization and industry classification.</role>

<task>
Classify the provided article content by matching it against the reference categories. Only select categories that have strong, direct relevance to the content.
</task>

<classification_process>
1. First, scan for any CONCERNS from the reference list ONLY
2. If concerns are found, then evaluate other categories from their respective reference lists ONLY
3. If NO concerns are identified, return empty arrays for all categories
4. For NAICS codes, select the single most relevant match from the provided NAICS reference data ONLY
5. STRICTLY use only items that appear in the reference lists - do NOT create or infer new categories
</classification_process>

<reference_data>
Concerns: {concerns_events}
Emerging Risks: {emerging_risks}
Misc Topics: {misc_topics}
NAICS Codes: {naics_data}
</reference_data>

<matching_criteria>
- Concerns: Must be an EXACT MATCH from the provided concerns reference list
- Emerging Risks: Must be an EXACT MATCH from the provided emerging risks reference list  
- Misc Topics: Must be an EXACT MATCH from the provided misc topics reference list
- NAICS: Must be an EXACT MATCH from the provided NAICS reference data (code and description)
- DO NOT create new categories or variations - use ONLY what is provided in reference lists
</matching_criteria>

<output_format>
Return ONLY valid JSON in this exact structure:

  "Concerns": ["array of matched concerns from reference list only"],
  "EmergingRiskName": ["array of matched emerging risks from reference list only"],
  "MiscTopics": ["array of matched misc topics from reference list only"],
  "NAICSCODE": "single best matching code or null",
  "NAICSDescription": "corresponding description or null"

</output_format>

<article>
{text}
</article>
"""

REFLECT_PROMPT = """
<role>You are a senior quality assurance reviewer with expertise in insurance data validation.</role>

<task>
Review and validate the extracted classifications for accuracy, consistency, and adherence to reference data.
</task>

<validation_checklist>
1. Verify all items exist in the reference data
2. Ensure NAICS code and description are properly paired
3. Remove any items that don't have strong textual support
4. Check for logical consistency between categories
5. Maintain conservative classification standards (80 percent and more confidence)
</validation_checklist>

<reference_data>
Concerns: {concerns_events}
Emerging Risks: {emerging_risks}
Misc Topics: {misc_topics}
NAICS Codes: {naics_data}
</reference_data>

<correction_rules>
- MANDATORY: Remove any items not found EXACTLY in the reference lists
- MANDATORY: Only use items that appear word-for-word in the provided reference data
- If NAICS code present, description must match exactly from reference data
- Empty arrays are preferred over incorrect classifications
- NEVER add items that are not explicitly listed in the reference data
</correction_rules>

<input_data>
{data}
</input_data>

<output_format>
Return ONLY the corrected JSON with the same structure as input.
</output_format>
"""

FINAL_VERIFICATION_PROMPT = """
<role>You are an expert insurance analyst conducting final verification and strategic tagging of classified articles.</role>

<context>
Original Article Data: {data}
Current Summary: {reason_identified}
Current Classifications:
- Concerns: {concerns}
- Emerging Risks: {emerging_risks}
- Misc Topics: {misc_topics}
- NAICS Code: {naics_code}
- NAICS Description: {naics_description}
</context>

<reference_data>
Concerns Events: {concerns_events}
Emerging Risks: {emerging_risks_ref}
Misc Topics: {misc_topics_ref}
NAICS Data: {naics_data}
</reference_data>

<verification_process>
1. STRICT COMPLIANCE CHECK: Verify every single item exists EXACTLY in reference lists
2. Refine summary to be more precise and actionable
3. REMOVE any items not found word-for-word in reference data
4. Apply tagging strategy based on verified, compliant results
5. ZERO TOLERANCE for items outside the provided reference lists
</verification_process>

<tagging_strategy>
IF Concerns are identified:
  ├─ IF Emerging Risks are also present:
  │  ├─ IF Misc Topics exist → Tag: 'Potential New Trend'
  │  └─ IF no Misc Topics → Tag: 'Current'
  └─ IF no Emerging Risks → Tag: 'Potential New Trend'
ELSE:
  └─ Tag: 'Untagged'
</tagging_strategy>

<output_requirements>
1. CRITICAL: Use ONLY items that appear exactly in the provided reference lists
2. Apply tagging strategy logically based on compliant classifications
3. Explain reasoning clearly and concisely
4. NEVER create, modify, or infer categories beyond what's explicitly provided
5. Empty classifications are acceptable - non-compliant ones are not
</output_requirements>

<output_format>
Return ONLY valid JSON in this exact structure:

    "ReasonIdentified": "refined and precise summary",
    "Concerns": ["high-confidence concerns only"],
    "EmergingRiskName": ["high-confidence risks only"],
    "MiscTopics": ["high-confidence misc topics only"],
    "NAICSCODE": "best matching code or null",
    "NAICSDescription": "exact corresponding description or null",
    "Tag": "tag based on strategy logic",
    "TaggingReasoning": "clear explanation of tag selection based on classification results"

</output_format>
"""




























# SUMMARY_PROMPT = """
# You are a senior insurance industry analyst.
# Summarize the following article in 2-3 sentences, focusing on risks and insurance-relevant aspects.
# Return ONLY a valid JSON response in this exact format: "ReasonIdentified": "<summary>"

# ARTICLE:
# {text}
# """

# CLASSIFY_PROMPT = """
# You are an insurance claims analyst. Classify the text into categories. Strictly take the 

# ARTICLE:
# {text}

# REFERENCE DATA:
# 1. Concerns: {concerns_events}
# 2. Emerging risks: {emerging_risks}
# 3. Misc topics: {misc_topics}
# 4. NAICS codes : {naics_data}

# INSTRUCTIONS:
# - Match text content to the reference categories above
# - For NAICS, find the most relevant code and description from the reference data
# - Return empty arrays if no matches found
# - Be precise and conservative in your classifications
# - Strictly provide from the list of categories above, don't go out of the list specified for concerns, Emerging risks, Misc Topics, NAICS codes
# - if concern is identified from the list then only check for other categories, else provide empty arrays

# Return ONLY a valid JSON response in this exact format:
# {{
#   "Concerns": ["list of matched concerns"],
#   "EmergingRiskName": ["list of matched emerging risks"],
#   "MiscTopics": ["list of matched misc topics"],
#   "NAICSCODE": "matched code or null",
#   "NAICSDescription": "corresponding description or null"
# }}
# """

# REFLECT_PROMPT = """
# You are a senior reviewer. Check the extracted fields for consistency and accuracy.

# REFERENCE DATA:
# 1. Concerns: {concerns_events}
# 2. Emerging risks: {emerging_risks}
# 3. Misc topics: {misc_topics}
# 4. NAICS codes : {naics_data}

# VALIDATION RULES:
# - If NAICS code is present, ensure description is filled and matches
# - Ensure all lists contain relevant items only
# - Remove any items that don't strongly match the original text
# - Keep classifications conservative and accurate
# - Make sure the Concerns, Emerging risks, Misc topics, NAICS codes are from the above list or not
# - If not from the above list just remove that

# Input JSON:
# {data}

# Return ONLY a corrected JSON response with the same structure as input.
# """

# FINAL_VERIFICATION_PROMPT = """
# You are an expert insurance analyst performing final verification and tagging.

# ORIGINAL DATA:
# {data}

# SUMMARY:
# {reason_identified}

# CURRENT CLASSIFICATION RESULTS:
# Concerns: {concerns}
# Emerging Risks: {emerging_risks}
# Misc Topics: {misc_topics}
# NAICS Code: {naics_code}
# NAICS Description: {naics_description}

# TAGGING STRATEGY:
# - If CONCERNS are identified:
#   - If RISKS are also present:
#     - If MISC topics exist: Tag as 'Potential New Trend'
#     - If no MISC topics: Tag as 'Current'
#   - If NO RISKS:
#     - Tag as 'Potential New Trend'
# - If NO CONCERNS: Tag as 'Untagged'

# REFERENCE DATA:
# Concerns Events: {concerns_events}
# Emerging Risks: {emerging_risks_ref}
# Misc Topics: {misc_topics_ref}
# NAICS Data: {naics_data}

# TASK:
# 1. Verify and refine all classifications (keep only high-confidence matches >80%)
# 2. Apply the tagging strategy based on refined results
# 3. Provide reasoning for the final tag

# Return ONLY a valid JSON response in this exact format:
# {{
#     "ReasonIdentified": "refined summary",
#     "Concerns": ["high-confidence concerns"],
#     "EmergingRiskName": ["high-confidence risks"],
#     "MiscTopics": ["high-confidence misc topics"],
#     "NAICSCODE": "best matching code or null",
#     "NAICSDescription": "corresponding description or null",
#     "Tag": "final tag based on strategy",
#     "TaggingReasoning": "explanation of tag choice"
# }}
# """





























# SUMMARY_PROMPT = """
# You are a senior insurance industry analyst.
# Summarize the following article in 2-3 sentences, focusing on risks and insurance-relevant aspects.
# Return JSON: {"ReasonIdentified": "<summary>"}

# ARTICLE:
# {text}
# """

# CLASSIFY_PROMPT = """
# You are an insurance claims analyst. Classify the text into categories.

# ARTICLE:
# {text}

# 1. Concerns: {concerns_events}
# 2. Emerging risks: {emerging_risks}
# 3. Misc topics: {misc_topics}
# 4. NAICS (sample): {naics_data}

# Return JSON:
# {
#   "Concerns": ["..."],
#   "EmergingRiskName": ["..."],
#   "MiscTopics": ["..."],
#   "NAICSCODE": "<code or null>",
#   "NAICSDescription": "<description or null>"
# }
# """

# REFLECT_PROMPT = """
# You are a senior reviewer. Check the extracted fields for consistency.
# If NAICS code present, ensure description is filled. Ensure lists are correct.

# Input JSON:
# {data}

# Return corrected JSON with the same keys.
# """

# FINAL_VERIFICATION_PROMPT = """
# You are an expert insurance analyst performing final verification and refinement of classification results.

# ORIGINAL DATA:
# {data}

# SUMMARY:
# {summary}

# CURRENT CLASSIFICATION RESULTS:
# Concerns: {concerns}
# Emerging Risks: {emerging_risks}
# Misc Topics: {misc_topics}
# NAICS Code: {naics_code}
# NAICS Description: {naics_description}

# PRELIMINARY TAG: {preliminary_tag}

# TAGGING STRATEGY EXPLANATION:
# The tagging follows this specific flow:
# - If CONCERNS are identified:
#   - If RISKS are also present:
#     - If MISC topics exist: Tag as 'Potential New Trend' (with NAICS logging if available)
#     - If no MISC topics: Tag as 'Current' (with NAICS logging if available)
#   - If NO RISKS:
#     - Regardless of MISC/NAICS presence: Tag as 'Potential New Trend' (with NAICS logging if available)
# - If NO CONCERNS: Tag as 'Untagged'

# YOUR TASK:
# 1. Verify and refine all classifications with probability/semantic matching >80%
# 2. For each category, return ONLY items with high confidence (>80% match)
# 3. Multiple values are allowed for risks, misc topics, NAICS codes, and descriptions
# 4. Ensure the final tag follows the strategy above based on refined results
# 5. Provide confidence scores for your classifications

# REFERENCE DATA:
# Concerns Events: {concerns_events}
# Emerging Risks: {emerging_risks_ref}
# Misc Topics: {misc_topics_ref}
# NAICS Data: {naics_data}

# Return your response in this JSON format:
# {{
#     "ReasonIdentified": "refined summary if needed",
#     "Concerns": ["list of high-confidence concerns"],
#     "ConcernsConfidence": [confidence_scores_for_concerns],
#     "EmergingRiskName": ["list of high-confidence risks"],
#     "EmergingRiskConfidence": [confidence_scores_for_risks],
#     "MiscTopics": ["list of high-confidence misc topics"],
#     "MiscConfidence": [confidence_scores_for_misc],
#     "NAICSCODE": ["list of high-confidence NAICS codes"],
#     "NAICSDescription": ["corresponding NAICS descriptions"],
#     "NAICSConfidence": [confidence_scores_for_naics],
#     "FinalTag": "final tag based on strategy",
#     "TaggingReasoning": "explanation of why this tag was chosen",
#     "OverallConfidence": overall_confidence_score
# }}
# """


# # VERIFY_PROMPT = """
# # You are a final insurance auditor. Validate the tagging result.
# # Return JSON:
# # {"Tag": "Approved" | "Needs Review"}
# # """
