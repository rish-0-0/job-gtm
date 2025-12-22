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
            logger.debug(f"[Ollama] Built prompt for {posting_url}, length: {len(prompt)} chars")

            # Call Ollama API
            logger.debug(f"[Ollama] Calling Ollama API for {posting_url}")
            response = await self._call_ollama(prompt)
            logger.debug(f"[Ollama] Received response for {posting_url}")

            # Parse response
            enriched_data = self._parse_enrichment_response(response)

            # Check for errors in response
            if "error" in enriched_data:
                logger.warning(f"[Ollama] Enrichment returned error for {posting_url}: {enriched_data.get('error')}")
            else:
                logger.info(f"[Ollama] Successfully enriched {posting_url}")

            # Add processing metadata
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            enriched_data["_metadata"] = {
                "processing_duration_ms": duration_ms,
                "model": self.model,
                "timestamp": end_time.isoformat()
            }

            logger.info(f"[Ollama] Total enrichment time for {posting_url}: {duration_ms}ms")

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
        prompt = f"""You are a job listing analysis expert. Analyze the following job listing and provide structured enrichment data.

Job Listing:
Company: {job_data.get('company_title', 'N/A')}
Role: {job_data.get('job_role', 'N/A')}
Location: {job_data.get('job_location', 'N/A')}
Salary: {job_data.get('salary_range', 'N/A')}
Description: {job_data.get('job_description', 'N/A')[:1000]}...
Employment Type: {job_data.get('employment_type', 'N/A')}
Posted: {job_data.get('date_posted', 'N/A')}
About Company: {job_data.get('about_company', 'N/A')[:500]}

Please provide the following analysis in JSON format:

{{
  "currency_normalization": {{
    "detected_currency": "USD|EUR|GBP|INR|etc",
    "min_salary_usd": <number or null>,
    "max_salary_usd": <number or null>,
    "conversion_rate": <number>,
    "confidence": <0.0-1.0>
  }},
  "seniority_level": {{
    "normalized": "Entry|Junior|Mid|Senior|Lead|Principal|Staff|Executive",
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
  }},
  "work_arrangement": {{
    "normalized": "On-site|Remote|Hybrid",
    "confidence": <0.0-1.0>,
    "details": "<any specific details>"
  }},
  "scam_detection": {{
    "score": <0-100>,
    "indicators": ["list", "of", "red", "flags"],
    "is_likely_scam": <true|false>,
    "reasoning": "<explanation>"
  }},
  "skills_extraction": {{
    "skills": [
      {{"skill": "React", "normalized": "ReactJS", "category": "Frontend", "experience": "3+ years"}},
      {{"skill": "Node", "normalized": "Node.js", "category": "Backend", "experience": "2+ years"}}
    ]
  }},
  "tech_stack": {{
    "technologies": ["React", "Node.js", "PostgreSQL"],
    "frameworks": ["Next.js", "Express"],
    "tools": ["Docker", "Git"]
  }},
  "location_normalization": {{
    "city": "<city>",
    "state": "<state>",
    "country": "<country>",
    "timezone": "<timezone>",
    "is_remote": <true|false>
  }},
  "company_insights": {{
    "industry": "<industry>",
    "company_size": "<size estimate>",
    "funding_stage": "<if mentioned>",
    "notable_info": "<any interesting facts>"
  }},
  "benefits": {{
    "has_stock_options": <true|false>,
    "stock_details": "<equity details if mentioned>",
    "other_benefits": ["benefit1", "benefit2"]
  }},
  "role_classification": {{
    "primary_role": "Software Engineer|Data Scientist|etc",
    "role_category": "Engineering|Product|etc",
    "is_management": <true|false>
  }}
}}

IMPORTANT:
- Return ONLY valid JSON, no additional text or markdown
- Use null for missing/unknown values
- Be conservative with confidence scores
- Scam indicators: unrealistic salary, vague company info, suspicious contact methods, too-good-to-be-true promises, grammar errors
- Normalize similar technologies (ReactJS=React, NodeJS=Node.js, Postgres=PostgreSQL, JS=JavaScript, TS=TypeScript)
- For currencies: Use current approximate exchange rates (INR≈0.012 USD, EUR≈1.08 USD, GBP≈1.27 USD)
- Tech stack normalization is critical - group similar items together
"""
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
                "temperature": 0.3,  # Lower temperature for more consistent JSON output
                "num_predict": 2048,  # Max tokens to generate
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

                    # Log response statistics
                    response_text = result.get('response', '')
                    logger.debug(f"[Ollama API] Response length: {len(response_text)} chars")
                    if 'total_duration' in result:
                        logger.debug(f"[Ollama API] Total duration: {result['total_duration']/1e9:.2f}s")

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
