"""
Ollama API client for job listing enrichment
"""
import json
import logging
import os
from typing import Dict, Any, Optional
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


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
        # Truncate if too long but keep more context
        if len(job_description) > 3000:
            job_description = job_description[:3000] + "..."

        about_company = job_data.get('about_company') or job_data.get('about_company_raw') or 'N/A'
        if len(about_company) > 1000:
            about_company = about_company[:1000] + "..."

        prompt = f"""You are a job listing analysis expert. Analyze the following job listing THOROUGHLY and extract ALL available information. You MUST provide a value for EVERY field - use "N/A" for strings or 0 for numbers if information is not available.

=== JOB LISTING DATA ===
Company: {job_data.get('company_title') or 'N/A'}
Job Title/Role: {job_data.get('job_role') or 'N/A'}
Location (Raw): {job_data.get('job_location') or job_data.get('job_location_raw') or 'N/A'}
Salary Range: {job_data.get('salary_range') or job_data.get('salary_range_raw') or 'N/A'}
Min Salary: {job_data.get('min_salary') or job_data.get('min_salary_raw') or 'N/A'}
Max Salary: {job_data.get('max_salary') or job_data.get('max_salary_raw') or 'N/A'}
Employment Type: {job_data.get('employment_type') or job_data.get('employment_type_raw') or 'N/A'}
Experience Required: {job_data.get('required_experience') or 'N/A'}
Seniority Level (Raw): {job_data.get('seniority_level') or job_data.get('seniority_level_raw') or 'N/A'}
Date Posted: {job_data.get('date_posted') or 'N/A'}

About Company:
{about_company}

Full Job Description:
{job_description}

=== ANALYSIS INSTRUCTIONS ===
Analyze the job listing above and provide COMPLETE structured data. DO NOT leave fields empty or null.

CRITICAL RULES:
1. EVERY string field MUST have a value - use "N/A" if information is not available
2. EVERY number field MUST have a value - use 0 if not available
3. EVERY boolean field MUST be true or false - make your best inference
4. EVERY array field MUST have at least one item - use ["N/A"] if nothing found
5. Extract ALL skills, technologies, and requirements mentioned in the description
6. Infer seniority from job title, requirements, and experience needed
7. Infer work arrangement from location, description, and any remote/hybrid mentions
8. Look for salary clues even if not explicitly stated (e.g., "competitive", market rates)

Return this EXACT JSON structure with ALL fields populated:

{{
  "currency_normalization": {{
    "detected_currency": "<USD|EUR|GBP|INR|CAD|AUD|SGD|N/A>",
    "min_salary_usd": <number or 0 if unknown>,
    "max_salary_usd": <number or 0 if unknown>,
    "conversion_rate": <number or 1.0>,
    "confidence": <0.0-1.0>
  }},
  "seniority_level": {{
    "normalized": "<Entry|Junior|Mid|Senior|Lead|Principal|Staff|Executive|N/A>",
    "confidence": <0.0-1.0>,
    "reasoning": "<explain how you determined seniority - REQUIRED>"
  }},
  "work_arrangement": {{
    "normalized": "<On-site|Remote|Hybrid|N/A>",
    "confidence": <0.0-1.0>,
    "details": "<explain work arrangement details - REQUIRED>"
  }},
  "scam_detection": {{
    "score": <0-100, 0=legitimate, 100=definite scam>,
    "indicators": ["<list any red flags, or 'None detected'>"],
    "is_likely_scam": <true|false>,
    "reasoning": "<explain your scam assessment - REQUIRED>"
  }},
  "skills_extraction": {{
    "skills": [
      {{"skill": "<raw skill>", "normalized": "<standardized name>", "category": "<Frontend|Backend|Database|DevOps|Cloud|Mobile|AI/ML|Data|Security|Management|Soft Skills|Other>", "experience": "<years or N/A>"}}
    ]
  }},
  "tech_stack": {{
    "technologies": ["<list all technologies, frameworks, languages mentioned>"],
    "frameworks": ["<specific frameworks>"],
    "tools": ["<tools, platforms, services>"],
    "databases": ["<any databases mentioned>"],
    "cloud": ["<cloud platforms: AWS, GCP, Azure, etc.>"]
  }},
  "location_normalization": {{
    "city": "<city name or N/A>",
    "state": "<state/province or N/A>",
    "country": "<country name or N/A>",
    "timezone": "<timezone like UTC+5:30, PST, EST or N/A>",
    "is_remote": <true|false>,
    "location_type": "<Single Location|Multiple Locations|Global|N/A>"
  }},
  "company_insights": {{
    "industry": "<Technology|Finance|Healthcare|E-commerce|Education|Manufacturing|Consulting|Other>",
    "company_size": "<Startup (1-50)|Small (51-200)|Medium (201-1000)|Large (1001-5000)|Enterprise (5000+)|N/A>",
    "funding_stage": "<Seed|Series A|Series B|Series C+|Public|Bootstrapped|N/A>",
    "notable_info": "<any interesting company facts, culture, mission - REQUIRED>"
  }},
  "benefits": {{
    "has_stock_options": <true|false>,
    "stock_details": "<equity/RSU details or N/A>",
    "has_health_insurance": <true|false>,
    "has_retirement_plan": <true|false>,
    "has_flexible_hours": <true|false>,
    "has_learning_budget": <true|false>,
    "pto_days": <number or 0>,
    "other_benefits": ["<list all other benefits mentioned>"]
  }},
  "role_classification": {{
    "primary_role": "<Software Engineer|Frontend Developer|Backend Developer|Full Stack Developer|DevOps Engineer|Data Scientist|Data Engineer|ML Engineer|Product Manager|Engineering Manager|QA Engineer|Security Engineer|Mobile Developer|Cloud Engineer|Other>",
    "role_category": "<Engineering|Product|Design|Data|Management|Operations|Security|Other>",
    "is_management": <true|false>,
    "team_size": "<number of reports if management, else 0>",
    "department": "<Engineering|Product|Data|Infrastructure|Security|Other|N/A>"
  }},
  "job_quality_score": {{
    "overall_score": <1-10>,
    "description_quality": <1-10>,
    "salary_transparency": <1-10>,
    "requirements_clarity": <1-10>
  }}
}}

CURRENCY CONVERSION RATES (approximate):
- INR to USD: 0.012
- EUR to USD: 1.08
- GBP to USD: 1.27
- CAD to USD: 0.74
- AUD to USD: 0.65
- SGD to USD: 0.74

TECHNOLOGY NORMALIZATION:
- ReactJS, React.js → React
- NodeJS, Node → Node.js
- Postgres, PostgresSQL → PostgreSQL
- JS → JavaScript
- TS → TypeScript
- K8s → Kubernetes
- AWS, Amazon Web Services → AWS
- GCP, Google Cloud → Google Cloud Platform

Return ONLY the JSON object, no markdown code blocks, no explanations before or after."""
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

            # Validate that we have the expected structure
            expected_keys = [
                "currency_normalization",
                "seniority_level",
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
