"""
Tests for Prospects Service.
"""

import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.prospects_service import (
    prospects_service,
    normalize_email,
    normalize_linkedin_url,
    calculate_name_similarity
)
from app.models import Company, Prospect


class TestEmailNormalization:
    """Test email normalization."""
    
    def test_normalize_email_lowercase(self):
        """Test email is lowercased."""
        assert normalize_email("John@Example.COM") == "john@example.com"
    
    def test_normalize_email_trim_spaces(self):
        """Test spaces are trimmed."""
        assert normalize_email("  john@example.com  ") == "john@example.com"
    
    def test_normalize_email_empty(self):
        """Test empty email returns None."""
        assert normalize_email("") is None
        assert normalize_email(None) is None


class TestLinkedInNormalization:
    """Test LinkedIn URL normalization."""
    
    def test_normalize_linkedin_standard(self):
        """Test standard LinkedIn URL normalization."""
        url = "https://www.linkedin.com/in/johndoe"
        assert normalize_linkedin_url(url) == "linkedin.com/in/johndoe"
    
    def test_normalize_linkedin_with_params(self):
        """Test LinkedIn URL with query params."""
        url = "https://linkedin.com/in/johndoe?param=value"
        assert normalize_linkedin_url(url) == "linkedin.com/in/johndoe"
    
    def test_normalize_linkedin_trailing_slash(self):
        """Test LinkedIn URL with trailing slash."""
        url = "https://linkedin.com/in/johndoe/"
        assert normalize_linkedin_url(url) == "linkedin.com/in/johndoe"
    
    def test_normalize_linkedin_empty(self):
        """Test empty URL returns None."""
        assert normalize_linkedin_url("") is None
        assert normalize_linkedin_url(None) is None


class TestNameSimilarity:
    """Test name similarity calculation."""
    
    def test_identical_names(self):
        """Test identical names return 1.0."""
        assert calculate_name_similarity("John Doe", "John Doe") == 1.0
    
    def test_case_insensitive(self):
        """Test comparison is case insensitive."""
        assert calculate_name_similarity("john doe", "JOHN DOE") == 1.0
    
    def test_similar_names(self):
        """Test similar names return high score."""
        similarity = calculate_name_similarity("John Doe", "Jon Doe")
        assert similarity > 0.8
    
    def test_different_names(self):
        """Test different names return low score."""
        similarity = calculate_name_similarity("John Doe", "Jane Smith")
        assert similarity < 0.5
    
    def test_empty_names(self):
        """Test empty names return 0.0."""
        assert calculate_name_similarity("", "John") == 0.0
        assert calculate_name_similarity("John", "") == 0.0


class TestProspectsService:
    """Test ProspectsService class."""
    
    @pytest.mark.asyncio
    async def test_find_duplicate_by_email(
        self,
        db_session: AsyncSession,
        test_company: Company,
        test_prospect: Prospect
    ):
        """Test finding duplicate by email."""
        # Search for existing prospect by email
        duplicate = await prospects_service.find_duplicate(
            db_session,
            company_id=test_company.id,
            email="prospect@example.com"
        )
        
        assert duplicate is not None
        assert duplicate.id == test_prospect.id
    
    @pytest.mark.asyncio
    async def test_find_duplicate_case_insensitive(
        self,
        db_session: AsyncSession,
        test_company: Company,
        test_prospect: Prospect
    ):
        """Test finding duplicate with different case."""
        duplicate = await prospects_service.find_duplicate(
            db_session,
            company_id=test_company.id,
            email="PROSPECT@EXAMPLE.COM"
        )
        
        assert duplicate is not None
        assert duplicate.id == test_prospect.id
    
    @pytest.mark.asyncio
    async def test_find_duplicate_not_found(
        self,
        db_session: AsyncSession,
        test_company: Company
    ):
        """Test no duplicate found returns None."""
        duplicate = await prospects_service.find_duplicate(
            db_session,
            company_id=test_company.id,
            email="nonexistent@example.com"
        )
        
        assert duplicate is None
    
    @pytest.mark.asyncio
    async def test_create_prospect(
        self,
        db_session: AsyncSession,
        test_company: Company
    ):
        """Test creating a new prospect."""
        prospect_data = {
            "email": "new@example.com",
            "first_name": "New",
            "last_name": "Prospect",
            "company_name": "New Corp"
        }
        source_info = {"source": "test", "added_at": datetime.utcnow().isoformat()}
        
        prospect = prospects_service.create_prospect(
            db_session,
            company_id=test_company.id,
            prospect_data=prospect_data,
            source_info=source_info
        )
        
        await db_session.flush()
        
        assert prospect.id is not None
        assert prospect.email == "new@example.com"
        assert prospect.first_name == "New"
        assert len(prospect.sources) == 1
    
    @pytest.mark.asyncio
    async def test_merge_prospect_data(
        self,
        db_session: AsyncSession,
        test_prospect: Prospect
    ):
        """Test merging new data into existing prospect."""
        new_data = {
            "phone": "555-1234",
            "custom_fields": {"department": "Sales"}
        }
        source_info = {"source": "merge_test"}
        
        prospects_service.merge_prospect_data(test_prospect, new_data, source_info)
        
        # Phone should be added (was empty)
        assert test_prospect.phone == "555-1234"
        # Custom field should be added
        assert test_prospect.custom_fields.get("department") == "Sales"
        # Should have new source
        assert len(test_prospect.sources) == 2
    
    @pytest.mark.asyncio
    async def test_get_prospects_pagination(
        self,
        db_session: AsyncSession,
        test_company: Company
    ):
        """Test getting prospects with pagination."""
        # Create multiple prospects
        for i in range(5):
            prospect = Prospect(
                company_id=test_company.id,
                email=f"test{i}@example.com",
                sources=[]
            )
            db_session.add(prospect)
        await db_session.flush()
        
        prospects, total = await prospects_service.get_prospects(
            db_session,
            company_id=test_company.id,
            page=1,
            page_size=3
        )
        
        assert len(prospects) == 3
        assert total == 5
    
    @pytest.mark.asyncio
    async def test_update_tags(
        self,
        db_session: AsyncSession,
        test_company: Company,
        test_prospect: Prospect
    ):
        """Test updating prospect tags."""
        result = await prospects_service.update_tags(
            db_session,
            prospect_id=test_prospect.id,
            tags=["new_tag", "another_tag"],
            company_id=test_company.id
        )
        
        assert result is not None
        assert "new_tag" in result.tags
        assert "another_tag" in result.tags
    
    @pytest.mark.asyncio
    async def test_update_status(
        self,
        db_session: AsyncSession,
        test_company: Company,
        test_prospect: Prospect
    ):
        """Test updating prospect status."""
        result = await prospects_service.update_status(
            db_session,
            prospect_id=test_prospect.id,
            status="contacted",
            company_id=test_company.id
        )
        
        assert result is not None
        assert result.status == "contacted"
        assert result.status_updated_at is not None
    
    @pytest.mark.asyncio
    async def test_delete_prospect(
        self,
        db_session: AsyncSession,
        test_company: Company,
        test_prospect: Prospect
    ):
        """Test soft deleting a prospect."""
        success = await prospects_service.delete_prospect(
            db_session,
            prospect_id=test_prospect.id,
            company_id=test_company.id
        )
        
        assert success is True
        
        # Prospect should no longer be accessible
        result = await prospects_service.get_prospect(
            db_session,
            prospect_id=test_prospect.id,
            company_id=test_company.id
        )
        assert result is None
