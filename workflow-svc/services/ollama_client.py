"""
Ollama API client for job listing enrichment
"""
import json
import logging
import os
import re
from typing import Dict, Any, Optional, Union
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def strip_html_tags(text: str) -> str:
    """Remove HTML/XML tags and clean up the text"""
    if not text:
        return text

    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # Remove script and style elements entirely
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Replace common block elements with newlines
    text = re.sub(r'<(?:br|p|div|h[1-6]|li|tr)[^>]*/?>', '\n', text, flags=re.IGNORECASE)

    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Decode common HTML entities
    html_entities = {
        '&nbsp;': ' ',
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#39;': "'",
        '&apos;': "'",
        '&ndash;': '-',
        '&mdash;': '-',
        '&bull;': '•',
        '&copy;': '©',
        '&reg;': '®',
        '&trade;': '™',
    }
    for entity, char in html_entities.items():
        text = text.replace(entity, char)

    # Remove numeric HTML entities
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'&#x[0-9a-fA-F]+;', '', text)

    # Clean up whitespace
    text = re.sub(r'\n\s*\n+', '\n\n', text)  # Multiple newlines to double newline
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single space
    text = '\n'.join(line.strip() for line in text.split('\n'))  # Strip each line

    return text.strip()


class OllamaClient:
    """
    Client for interacting with Ollama API to enrich job listings
    """

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = base_url or os.getenv("OLLAMA_URL", "http://ollama:11434")
        self.model = model or "llama3.2:3b"
        self.timeout = httpx.Timeout(
            connect=30.0,    # 30s to establish connection
            read=300.0,      # 5 minutes to read response (LLM can be slow)
            write=30.0,      # 30s to send request
            pool=30.0        # 30s to acquire connection from pool
        )
        self.max_retries = 2

    async def enrich_job_listing(self, job_data: dict) -> dict:
        """
        Send job data to Ollama for enrichment

        Args:
            job_data: Dictionary containing job listing information

        Returns:
            Dictionary with enriched job data
        """
        try:
            start_time = datetime.now(timezone.utc)
            posting_url = job_data.get('posting_url', 'unknown')

            logger.info(f"[Ollama] Starting enrichment for job: {posting_url}")

            # Build enrichment prompt
            prompt = self._build_enrichment_prompt(job_data)
            logger.info(f"[Ollama] Built prompt for {posting_url}, length: {len(prompt)} chars")

            # Log what data we're working with
            job_desc = job_data.get('job_description_full') or job_data.get('full_page_text') or job_data.get('job_description')
            logger.info(f"[Ollama] Job description length: {len(job_desc) if job_desc else 0} chars")

            # Call Ollama API
            logger.debug(f"[Ollama] Calling Ollama API for {posting_url}")
            response = await self._call_ollama(prompt)
            logger.debug(f"[Ollama] Received response for {posting_url}")

            # Parse response
            enriched_data = self._parse_enrichment_response(response)

            # Extract token counts from response
            prompt_tokens = response.get('prompt_eval_count', 0)
            response_tokens = response.get('eval_count', 0)

            # Check for errors in response
            if "error" in enriched_data:
                logger.warning(f"[Ollama] Enrichment returned error for {posting_url}: {enriched_data.get('error')}")
            else:
                logger.info(f"[Ollama] Successfully enriched {posting_url}")

            # Add processing metadata including token usage
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            enriched_data["_metadata"] = {
                "processing_duration_ms": duration_ms,
                "model": self.model,
                "timestamp": end_time.isoformat(),
                "prompt_tokens": prompt_tokens,
                "response_tokens": response_tokens,
                "total_tokens": prompt_tokens + response_tokens
            }

            logger.info(f"[Ollama] Total enrichment time for {posting_url}: {duration_ms}ms, tokens: {prompt_tokens}+{response_tokens}={prompt_tokens+response_tokens}")

            return enriched_data

        except Exception as e:
            logger.error(f"[Ollama] Enrichment failed: {str(e)}", exc_info=True)
            raise

    def _build_enrichment_prompt(self, job_data: dict) -> str:
        """
        Build comprehensive prompt for job enrichment

        Args:
            job_data: Job listing data

        Returns:
            Formatted prompt string
        """
        # Get the full job description - prefer detailed version from golden table
        job_description = (
            job_data.get('job_description_full') or
            job_data.get('full_page_text') or
            job_data.get('job_description') or
            'N/A'
        )
        # Clean HTML from job description
        job_description = strip_html_tags(job_description)
        # Truncate if too long but keep more context
        if len(job_description) > 3000:
            job_description = job_description[:3000] + "..."

        about_company = job_data.get('about_company') or job_data.get('about_company_raw') or 'N/A'
        # Clean HTML from about company
        about_company = strip_html_tags(about_company)
        if len(about_company) > 1000:
            about_company = about_company[:1000] + "..."

        # Clean other text fields
        company_title = strip_html_tags(job_data.get('company_title') or 'N/A')
        job_role = strip_html_tags(job_data.get('job_role') or 'N/A')
        job_location = strip_html_tags(job_data.get('job_location') or job_data.get('job_location_raw') or 'N/A')
        salary_range = strip_html_tags(job_data.get('salary_range') or job_data.get('salary_range_raw') or 'N/A')

        prompt = f"""You are a job listing analysis expert. Your task is to FULLY populate ALL fields by analyzing the job listing and making intelligent inferences.

CRITICAL RULES:
1. Return ONLY valid JSON - no markdown, no code blocks, no explanations
2. NEVER use "N/A" if you can make a reasonable inference - ALWAYS TRY TO INFER
3. NEVER include HTML tags in output - plain text only
4. You MUST fill every field - use context clues, common patterns, and logical deduction

=== JOB LISTING ===
Company: {company_title}
Job Title: {job_role}
Location: {job_location}
Salary: {salary_range}
Employment Type: {strip_html_tags(job_data.get('employment_type') or job_data.get('employment_type_raw') or 'N/A')}
Experience: {strip_html_tags(job_data.get('required_experience') or 'N/A')}

About Company:
{about_company}

Job Description:
{job_description}

=== INFERENCE GUIDELINES ===

LOCATION: Determine the country when possible. Use these rules:
- City names → look up country (e.g., "Bangalore" = India, "Austin" = USA, "London" = UK)
- State abbreviations → country (e.g., "CA", "TX", "NY" = USA; "ON", "BC" = Canada)
- If only city given, infer state/country from common knowledge
- Company HQ location can hint at job location
- For remote jobs with no specific location, leave city/state/country empty but set is_remote=true

SENIORITY: You MUST determine seniority level. Use these rules:
- Job title keywords: "Senior", "Sr.", "Lead", "Principal", "Staff", "Junior", "Jr.", "Entry", "Associate"
- Years of experience: 0-2 = Entry/Junior, 2-5 = Mid, 5-8 = Senior, 8+ = Lead/Principal
- If no years stated but responsibilities are complex = Mid or Senior
- Management titles = Lead or Executive
- Default for ambiguous roles = Mid

EMPLOYMENT TYPE: You MUST classify. Use these rules:
- Look for: "full-time", "part-time", "contract", "freelance", "internship", "temporary"
- Most jobs without specification = Full-time
- "Contract" or "C2C" = Contract
- Student/intern language = Internship

WORK ARRANGEMENT: You MUST classify. Use these rules:
- Keywords: "remote", "work from home", "WFH", "distributed" = Remote
- Keywords: "hybrid", "flexible", "2-3 days" = Hybrid
- Physical address without remote mention = On-site
- No mention at all = infer On-site (most common default)

INDUSTRY: Infer from company name, description, or job context
COMPANY SIZE: Infer from funding stage, team size mentions, or company description

Return this EXACT JSON structure with ALL fields populated:

{{
  "currency_normalization": {{
    "detected_currency": "USD|EUR|GBP|INR|CAD|AUD|SGD",
    "min_salary_usd": 0,
    "max_salary_usd": 0,
    "conversion_rate": 1.0,
    "confidence": 0.0
  }},
  "seniority_level": {{
    "normalized": "Entry|Junior|Mid|Senior|Lead|Principal|Staff|Executive",
    "confidence": 0.8,
    "reasoning": "Brief explanation"
  }},
  "employment_type": {{
    "normalized": "Full-time|Part-time|Contract|Internship|Temporary|Freelance",
    "confidence": 0.9,
    "reasoning": "Brief explanation"
  }},
  "work_arrangement": {{
    "normalized": "On-site|Remote|Hybrid",
    "confidence": 0.8,
    "details": "Brief explanation"
  }},
  "scam_detection": {{
    "score": 0,
    "indicators": [],
    "is_likely_scam": false,
    "reasoning": "Brief explanation"
  }},
  "skills_extraction": {{
    "skills": [
      {{"skill": "raw skill", "normalized": "standardized", "category": "Backend|Frontend|Database|DevOps|Cloud|Mobile|AI/ML|Data|Security|Management|Soft Skills|Other", "experience": "years or N/A"}}
    ]
  }},
  "tech_stack": {{
    "technologies": [],
    "frameworks": [],
    "tools": [],
    "databases": [],
    "cloud": []
  }},
  "location_normalization": {{
    "city": "City name",
    "state": "State/Province",
    "country": "Country name - REQUIRED, ALWAYS INFER",
    "timezone": "Timezone",
    "is_remote": false,
    "location_type": "Single Location|Multiple Locations|Global"
  }},
  "company_insights": {{
    "industry": "Technology|Finance|Healthcare|E-commerce|Education|Manufacturing|Consulting|Retail|Media|Other",
    "company_size": "Startup (1-50)|Small (51-200)|Medium (201-1000)|Large (1001-5000)|Enterprise (5000+)",
    "funding_stage": "Seed|Series A|Series B|Series C+|Public|Bootstrapped",
    "notable_info": "Key company facts"
  }},
  "benefits": {{
    "has_stock_options": false,
    "stock_details": "",
    "has_health_insurance": false,
    "has_retirement_plan": false,
    "has_flexible_hours": false,
    "has_learning_budget": false,
    "pto_days": 0,
    "other_benefits": []
  }},
  "role_classification": {{
    "primary_role": "Software Engineer|Frontend Developer|Backend Developer|Full Stack Developer|DevOps Engineer|Data Scientist|Data Engineer|ML Engineer|Product Manager|Engineering Manager|QA Engineer|Security Engineer|Mobile Developer|Cloud Engineer|Other",
    "role_category": "Engineering|Product|Design|Data|Management|Operations|Security|Other",
    "is_management": false,
    "team_size": 0,
    "department": "Engineering|Product|Data|Infrastructure|Security|Other"
  }},
  "job_quality_score": {{
    "overall_score": 5,
    "description_quality": 5,
    "salary_transparency": 1,
    "requirements_clarity": 5
  }}
}}

CURRENCY RATES: INR=0.012, EUR=1.08, GBP=1.27, CAD=0.74, AUD=0.65, SGD=0.74

Return ONLY the JSON object."""
        return prompt

    async def _call_ollama(self, prompt: str) -> dict:
        """
        Call Ollama API with retry logic

        Args:
            prompt: The prompt to send to Ollama

        Returns:
            API response dictionary
        """
        import asyncio

        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,  # Lower temperature for more consistent JSON output
                "num_predict": 4096,  # Max tokens to generate (increased for detailed response)
            }
        }

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"[Ollama API] Calling {url} with model {self.model} (attempt {attempt}/{self.max_retries})")
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    result = response.json()

                    # Log response statistics including token usage
                    prompt_tokens = result.get('prompt_eval_count', 0)
                    response_tokens = result.get('eval_count', 0)
                    total_duration_s = result.get('total_duration', 0) / 1e9

                    logger.info(
                        f"[Ollama API] Completed: {prompt_tokens} prompt tokens, "
                        f"{response_tokens} response tokens, {total_duration_s:.1f}s"
                    )

                    return result

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(f"[Ollama API] Timeout on attempt {attempt}/{self.max_retries}: {str(e)}")
                if attempt < self.max_retries:
                    await asyncio.sleep(2)  # Wait before retry
                    continue
                logger.error(f"[Ollama API] All retries exhausted - timeout")
                raise Exception(f"Ollama API timeout after {self.max_retries} attempts")

            except httpx.HTTPError as e:
                last_error = e
                logger.warning(f"[Ollama API] HTTP error on attempt {attempt}/{self.max_retries}: {str(e)}")
                if attempt < self.max_retries:
                    await asyncio.sleep(2)
                    continue
                logger.error(f"[Ollama API] All retries exhausted - HTTP error: {str(e)}")
                raise Exception(f"Ollama API error: {str(e)}")

            except Exception as e:
                last_error = e
                logger.error(f"[Ollama API] Call failed on attempt {attempt}: {str(e)}", exc_info=True)
                if attempt < self.max_retries:
                    await asyncio.sleep(2)
                    continue
                raise

        raise Exception(f"Ollama API failed after {self.max_retries} attempts: {str(last_error)}")

    def _clean_enriched_data(self, data: Any) -> Any:
        """
        Recursively clean HTML tags from all string values in the enriched data
        """
        if isinstance(data, dict):
            return {k: self._clean_enriched_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._clean_enriched_data(item) for item in data]
        elif isinstance(data, str):
            # Remove any HTML/XML tags from string values
            cleaned = re.sub(r'<[^>]+>', '', data)
            # Also clean up any escaped HTML entities that might remain
            cleaned = cleaned.replace('&lt;', '<').replace('&gt;', '>')
            cleaned = cleaned.replace('&amp;', '&').replace('&quot;', '"')
            # Remove the angle brackets we just unescaped if they look like tags
            cleaned = re.sub(r'<[^>]+>', '', cleaned)
            return cleaned.strip()
        else:
            return data

    def _parse_enrichment_response(self, response: dict) -> dict:
        """
        Parse Ollama response into structured format

        Args:
            response: Raw Ollama API response

        Returns:
            Parsed enrichment data dictionary
        """
        try:
            # Extract the generated text from response
            response_text = response.get("response", "")

            if not response_text:
                raise ValueError("Empty response from Ollama")

            # Try to extract JSON from the response
            # Sometimes the model wraps JSON in markdown code blocks
            response_text = response_text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                # Remove first line (```json or ```)
                lines = lines[1:]
                # Remove last line (```)
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = "\n".join(lines).strip()

            # Parse JSON
            try:
                enriched_data = json.loads(response_text)
                logger.debug(f"[Ollama Parser] Successfully parsed JSON response")
            except json.JSONDecodeError as e:
                logger.error(f"[Ollama Parser] Failed to parse JSON: {str(e)}")
                logger.error(f"[Ollama Parser] Response text (first 500 chars): {response_text[:500]}")
                # Return a minimal structure with error info
                return {
                    "error": "Failed to parse Ollama response",
                    "raw_response": response_text[:500]
                }

            # Clean any HTML tags from all string values in the response
            enriched_data = self._clean_enriched_data(enriched_data)

            # Validate that we have the expected structure
            expected_keys = [
                "currency_normalization",
                "seniority_level",
                "employment_type",
                "work_arrangement",
                "scam_detection",
                "skills_extraction",
                "tech_stack",
                "location_normalization",
                "company_insights",
                "benefits",
                "role_classification"
            ]

            missing_keys = [key for key in expected_keys if key not in enriched_data]
            if missing_keys:
                logger.warning(f"[Ollama Parser] Response missing keys: {missing_keys}")
            else:
                logger.debug(f"[Ollama Parser] All expected keys present in response")

            return enriched_data

        except Exception as e:
            logger.error(f"[Ollama Parser] Failed to parse response: {str(e)}", exc_info=True)
            return {
                "error": str(e),
                "raw_response": str(response)[:500]
            }

    async def health_check(self) -> bool:
        """
        Check if Ollama service is healthy

        Returns:
            True if healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/api/tags"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Ollama health check failed: {str(e)}")
            return False
