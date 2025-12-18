from sqlalchemy import Column, Integer, String, Text, DateTime, Numeric, UniqueConstraint
from sqlalchemy.sql import func
from database import Base

class JobListing(Base):
    """
    Model for storing scraped job listings
    """
    __tablename__ = "job_listings"
    __table_args__ = (
        UniqueConstraint('company_title', 'job_role', 'job_location', 'employment_type',
                        name='uq_job_listing_details'),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Job details
    company_title = Column(String(255), nullable=False, index=True)
    job_role = Column(String(255), nullable=False, index=True)
    job_location = Column(String(255), index=True)
    employment_type = Column(String(100))

    # Salary information
    salary_range = Column(String(255))
    min_salary = Column(Numeric(10, 2))
    max_salary = Column(Numeric(10, 2))

    # Job requirements
    required_experience = Column(String(255))
    seniority_level = Column(String(100))

    # Job description
    job_description = Column(Text)

    # Additional information
    date_posted = Column(String(100))
    posting_url = Column(Text, unique=True, index=True)
    hiring_team = Column(Text)
    about_company = Column(Text)

    # Metadata
    scraper_source = Column(String(100), nullable=False, index=True)  # dice, simplyhired, etc.
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<JobListing(id={self.id}, company={self.company_title}, role={self.job_role})>"
