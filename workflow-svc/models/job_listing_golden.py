"""
SQLAlchemy model for enriched/golden job listings
"""
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from database import Base


class JobListingGolden(Base):
    """
    Golden/enriched job listings table with AI-enhanced data
    """
    __tablename__ = "job_listings_golden"

    # Primary key and relationships
    id = Column(Integer, primary_key=True, index=True)
    source_job_id = Column(Integer, ForeignKey("job_listings.id"), index=True)
    posting_url = Column(Text, nullable=False, unique=True, index=True)

    # Core fields
    company_title = Column(String(255), index=True)
    job_role = Column(String(255))
    job_location_raw = Column(String(255))
    job_location_normalized = Column(String(255))
    employment_type_raw = Column(String(100))
    employment_type_normalized = Column(String(100))

    # Salary normalization
    salary_range_raw = Column(String(255))
    min_salary_raw = Column(Numeric(10, 2))
    max_salary_raw = Column(Numeric(10, 2))
    currency_raw = Column(String(10))
    min_salary_usd = Column(Numeric(10, 2))
    max_salary_usd = Column(Numeric(10, 2))
    currency_conversion_rate = Column(Numeric(10, 6))
    currency_conversion_date = Column(DateTime(timezone=True))

    # Experience and seniority fields
    required_experience = Column(String(255))
    seniority_level_raw = Column(String(100))
    seniority_level_normalized = Column(String(50), index=True)
    seniority_confidence_score = Column(Numeric(3, 2))

    # Work arrangement
    work_arrangement_raw = Column(String(100))
    work_arrangement_normalized = Column(String(50))

    # Fraud detection
    scam_score = Column(Integer)
    scam_indicators = Column(JSONB)

    # Skills and tech stack
    skills_extracted = Column(JSONB)
    tech_stack_normalized = Column(JSONB)

    # Location normalization
    location_city = Column(String(100))
    location_state = Column(String(100))
    location_country = Column(String(100))
    location_timezone = Column(String(50))
    is_remote = Column(Boolean)

    # Company enrichment
    about_company_raw = Column(Text)
    company_research = Column(Text)
    company_industry = Column(String(100))
    company_size = Column(String(100))

    # Hiring team
    hiring_team_raw = Column(Text)
    hiring_team_analysis = Column(Text)

    # Benefits
    has_stock_options = Column(Boolean)
    stock_options_details = Column(Text)
    other_benefits = Column(JSONB)

    # Full job details (from detail scrape - Phase 1)
    # These fields are populated by the detail scraper before AI enrichment
    job_description_full = Column(Text)  # Main job description from detail page
    full_page_text = Column(Text)  # Raw page text for AI to process
    job_requirements = Column(JSONB)
    job_benefits = Column(JSONB)

    # Role classification
    primary_role = Column(String(100))
    role_category = Column(String(100))
    is_management = Column(Boolean)

    # Additional metadata from raw job_listing
    date_posted = Column(String(100))
    scraper_source = Column(String(100), index=True)
    scraped_at = Column(DateTime(timezone=True))

    # Detail scraping metadata (Phase 1: scrape job URLs for full details)
    # Status flow: None -> pending -> completed/failed
    # Only rows with detail_scrape_status='completed' can proceed to enrichment
    detail_scraped_at = Column(DateTime(timezone=True))
    detail_scrape_status = Column(String(50), index=True)  # pending, completed, failed
    detail_scrape_duration_ms = Column(Integer)
    detail_scrape_errors = Column(JSONB)

    # Processing metadata (Phase 2: AI enrichment)
    # IMPORTANT: Enrichment can ONLY run on rows where detail_scrape_status='completed'
    enriched_at = Column(DateTime(timezone=True))
    ollama_model_version = Column(String(50))
    processing_duration_ms = Column(Integer)
    ai_prompt_tokens = Column(Integer)
    ai_response_tokens = Column(Integer)
    enrichment_status = Column(String(50), index=True)  # pending, completed, failed
    enrichment_errors = Column(JSONB)
    enrichment_version = Column(Integer, nullable=False, server_default="1")

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<JobListingGolden(id={self.id}, company='{self.company_title}', role='{self.job_role}')>"
