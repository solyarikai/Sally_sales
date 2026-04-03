"""
Knowledge Base API - Refactored with Multi-Tenant Support
All endpoints filter data by company_id for proper data isolation.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from typing import List, Optional
import csv
import io
import json

from app.db import get_session
from app.models import Company
from app.models.knowledge_base import (
    Document, DocumentFolder, DocumentType as ModelDocumentType,
    CompanyProfile, Product, Segment, SegmentColumn, DEFAULT_SEGMENT_COLUMNS,
    Competitor, CaseStudy, VoiceTone, BookingLink, Blocklist
)
from app.schemas.knowledge_base import (
    DocumentResponse, DocumentUpdate, DocumentFolderCreate, DocumentFolderResponse,
    CompanyProfileResponse, CompanyProfileUpdate,
    ProductCreate, ProductUpdate, ProductResponse,
    SegmentCreate, SegmentUpdate, SegmentResponse,
    SegmentColumnCreate, SegmentColumnUpdate, SegmentColumnResponse,
    CompetitorCreate, CompetitorUpdate, CompetitorResponse,
    CaseStudyCreate, CaseStudyUpdate, CaseStudyResponse,
    VoiceToneCreate, VoiceToneUpdate, VoiceToneResponse,
    BookingLinkCreate, BookingLinkUpdate, BookingLinkResponse,
    BlocklistCreate, BlocklistResponse,
    CSVImportResult, AIImportRequest, AIImportResponse,
    KnowledgeBaseExport
)
from app.services.ai_import import parse_free_text, parse_multiple_entities
from app.services.document_processor import process_document, generate_company_summary
from app.services.kb_context import get_available_tags, resolve_tags
from app.api.companies import get_required_company

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


# ============ Document Folders ============

@router.get("/folders", response_model=List[DocumentFolderResponse])
async def get_folders(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(DocumentFolder)
        .where(DocumentFolder.company_id == company.id)
        .order_by(DocumentFolder.name)
    )
    return result.scalars().all()


@router.post("/folders", response_model=DocumentFolderResponse)
async def create_folder(
    data: DocumentFolderCreate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    folder = DocumentFolder(**data.model_dump(), company_id=company.id)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(DocumentFolder).where(
            and_(DocumentFolder.id == folder_id, DocumentFolder.company_id == company.id)
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Move documents to root (within same company)
    await db.execute(
        Document.__table__.update()
        .where(and_(Document.folder_id == folder_id, Document.company_id == company.id))
        .values(folder_id=None)
    )
    await db.delete(folder)
    await db.commit()
    return {"success": True}


# ============ Documents ============

@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    document_type: str = Form("other"),
    folder_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    """Upload and process a document to markdown"""
    content = await file.read()
    
    # Verify folder belongs to company if provided
    if folder_id:
        folder_result = await db.execute(
            select(DocumentFolder).where(
                and_(DocumentFolder.id == folder_id, DocumentFolder.company_id == company.id)
            )
        )
        if not folder_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Folder not found")
    
    doc = Document(
        name=name or file.filename,
        original_filename=file.filename,
        document_type=ModelDocumentType(document_type),
        folder_id=folder_id,
        company_id=company.id,
        status="processing"
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    
    # Process document to markdown
    try:
        result = await process_document(content, file.filename, file.content_type)
        doc.raw_text = result.get("raw_text", "")
        doc.content_md = result.get("markdown", "")
        doc.status = "processed"
    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)
    
    await db.commit()
    await db.refresh(doc)
    return doc


@router.get("/documents", response_model=List[DocumentResponse])
async def get_documents(
    folder_id: Optional[int] = None,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    query = select(Document).where(Document.company_id == company.id).order_by(Document.created_at.desc())
    if folder_id is not None:
        query = query.where(Document.folder_id == folder_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Document).where(
            and_(Document.id == document_id, Document.company_id == company.id)
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.patch("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    data: DocumentUpdate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Document).where(
            and_(Document.id == document_id, Document.company_id == company.id)
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(doc, key, value)
    
    await db.commit()
    await db.refresh(doc)
    return doc


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Document).where(
            and_(Document.id == document_id, Document.company_id == company.id)
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    await db.delete(doc)
    await db.commit()
    return {"success": True}


@router.post("/documents/regenerate-summary")
async def regenerate_summary(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    """Regenerate company summary from all documents"""
    # Get all processed documents for this company
    result = await db.execute(
        select(Document).where(
            and_(Document.status == "processed", Document.company_id == company.id)
        )
    )
    documents = result.scalars().all()
    
    if not documents:
        return {"summary": "", "document_count": 0}
    
    # Generate summary
    summary = await generate_company_summary([doc.content_md for doc in documents if doc.content_md])
    
    # Update company profile for this company
    profile_result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.company_id == company.id)
    )
    profile = profile_result.scalar_one_or_none()
    
    if profile:
        profile.summary = summary
    else:
        profile = CompanyProfile(summary=summary, company_id=company.id)
        db.add(profile)
    
    await db.commit()
    
    return {"summary": summary, "document_count": len(documents)}


# ============ Company Profile ============

@router.get("/company", response_model=Optional[CompanyProfileResponse])
async def get_company_profile(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.company_id == company.id)
    )
    return result.scalar_one_or_none()


@router.put("/company", response_model=CompanyProfileResponse)
async def save_company_profile(
    data: CompanyProfileUpdate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.company_id == company.id)
    )
    profile = result.scalar_one_or_none()
    
    if profile:
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(profile, key, value)
    else:
        profile = CompanyProfile(**data.model_dump(), company_id=company.id)
        db.add(profile)
    
    await db.commit()
    await db.refresh(profile)
    return profile


# ============ Products ============

@router.get("/products", response_model=List[ProductResponse])
async def get_products(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Product)
        .where(Product.company_id == company.id)
        .order_by(Product.sort_order, Product.name)
    )
    return result.scalars().all()


@router.post("/products", response_model=ProductResponse)
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    product = Product(**data.model_dump(), company_id=company.id)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Product).where(
            and_(Product.id == product_id, Product.company_id == company.id)
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Product).where(
            and_(Product.id == product_id, Product.company_id == company.id)
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    await db.delete(product)
    await db.commit()
    return {"success": True}


# ============ Segment Columns ============

@router.get("/segment-columns", response_model=List[SegmentColumnResponse])
async def get_segment_columns(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(SegmentColumn)
        .where(SegmentColumn.company_id == company.id)
        .order_by(SegmentColumn.sort_order)
    )
    columns = result.scalars().all()
    
    # Initialize default columns for this company if none exist
    if not columns:
        for col_data in DEFAULT_SEGMENT_COLUMNS:
            col = SegmentColumn(**col_data, company_id=company.id)
            db.add(col)
        await db.commit()
        
        result = await db.execute(
            select(SegmentColumn)
            .where(SegmentColumn.company_id == company.id)
            .order_by(SegmentColumn.sort_order)
        )
        columns = result.scalars().all()
    
    return columns


@router.post("/segment-columns", response_model=SegmentColumnResponse)
async def create_segment_column(
    data: SegmentColumnCreate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    # Get max sort_order for this company
    result = await db.execute(
        select(SegmentColumn)
        .where(SegmentColumn.company_id == company.id)
        .order_by(SegmentColumn.sort_order.desc())
        .limit(1)
    )
    last_col = result.scalar_one_or_none()
    
    col = SegmentColumn(
        **data.model_dump(),
        company_id=company.id,
        is_system=False,
        sort_order=last_col.sort_order + 1 if last_col else 0
    )
    db.add(col)
    await db.commit()
    await db.refresh(col)
    return col


@router.patch("/segment-columns/{column_id}", response_model=SegmentColumnResponse)
async def update_segment_column(
    column_id: int,
    data: SegmentColumnUpdate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(SegmentColumn).where(
            and_(SegmentColumn.id == column_id, SegmentColumn.company_id == company.id)
        )
    )
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Column not found")
    
    # Can't change name of system columns
    if col.is_system and "name" in data.model_dump(exclude_unset=True):
        raise HTTPException(status_code=400, detail="Cannot rename system columns")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(col, key, value)
    
    await db.commit()
    await db.refresh(col)
    return col


@router.delete("/segment-columns/{column_id}")
async def delete_segment_column(
    column_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(SegmentColumn).where(
            and_(SegmentColumn.id == column_id, SegmentColumn.company_id == company.id)
        )
    )
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Column not found")
    
    if col.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system columns")
    
    await db.delete(col)
    await db.commit()
    return {"success": True}


# ============ Segments ============

@router.get("/segments", response_model=List[SegmentResponse])
async def get_segments(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Segment)
        .where(Segment.company_id == company.id)
        .order_by(Segment.sort_order, Segment.name)
    )
    return result.scalars().all()


@router.post("/segments", response_model=SegmentResponse)
async def create_segment(
    data: SegmentCreate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    # Ensure name is in data
    segment_data = data.model_dump()
    if "name" not in segment_data.get("data", {}):
        segment_data["data"]["name"] = segment_data["name"]
    
    segment = Segment(**segment_data, company_id=company.id)
    db.add(segment)
    await db.commit()
    await db.refresh(segment)
    return segment


@router.patch("/segments/{segment_id}", response_model=SegmentResponse)
async def update_segment(
    segment_id: int,
    data: SegmentUpdate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Segment).where(
            and_(Segment.id == segment_id, Segment.company_id == company.id)
        )
    )
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    update_data = data.model_dump(exclude_unset=True)
    
    # If updating data, merge with existing
    if "data" in update_data:
        existing_data = segment.data or {}
        existing_data.update(update_data["data"])
        segment.data = existing_data
        
        # Update name if in data
        if "name" in update_data["data"]:
            segment.name = update_data["data"]["name"]
        del update_data["data"]
    
    for key, value in update_data.items():
        setattr(segment, key, value)
    
    await db.commit()
    await db.refresh(segment)
    return segment


@router.delete("/segments/{segment_id}")
async def delete_segment(
    segment_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Segment).where(
            and_(Segment.id == segment_id, Segment.company_id == company.id)
        )
    )
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    await db.delete(segment)
    await db.commit()
    return {"success": True}


@router.post("/segments/import-csv", response_model=CSVImportResult)
async def import_segments_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    """Import segments from CSV/Excel"""
    content = await file.read()
    
    try:
        # Try to decode as CSV
        text = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        
        imported = 0
        errors = []
        
        for i, row in enumerate(reader):
            try:
                name = row.get('name') or row.get('Segment Name') or row.get('segment')
                if not name:
                    errors.append(f"Row {i+1}: Missing name")
                    continue
                
                # Convert row to segment data
                data = {}
                for key, value in row.items():
                    if value:
                        # Handle list fields
                        if ',' in value and key.lower() in ['target_countries', 'target_job_titles', 'example_companies', 'problems_we_solve', 'our_offer', 'differentiators']:
                            data[key.lower().replace(' ', '_')] = [v.strip() for v in value.split(',')]
                        else:
                            data[key.lower().replace(' ', '_')] = value
                
                segment = Segment(name=name, data=data, company_id=company.id)
                db.add(segment)
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {i+1}: {str(e)}")
        
        await db.commit()
        return CSVImportResult(success=True, imported_count=imported, errors=errors)
        
    except Exception as e:
        return CSVImportResult(success=False, imported_count=0, errors=[str(e)])


# ============ Competitors ============

@router.get("/competitors", response_model=List[CompetitorResponse])
async def get_competitors(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Competitor)
        .where(Competitor.company_id == company.id)
        .order_by(Competitor.name)
    )
    return result.scalars().all()


@router.post("/competitors", response_model=CompetitorResponse)
async def create_competitor(
    data: CompetitorCreate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    competitor = Competitor(**data.model_dump(), company_id=company.id)
    db.add(competitor)
    await db.commit()
    await db.refresh(competitor)
    return competitor


@router.patch("/competitors/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(
    competitor_id: int,
    data: CompetitorUpdate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Competitor).where(
            and_(Competitor.id == competitor_id, Competitor.company_id == company.id)
        )
    )
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(competitor, key, value)
    
    await db.commit()
    await db.refresh(competitor)
    return competitor


@router.delete("/competitors/{competitor_id}")
async def delete_competitor(
    competitor_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Competitor).where(
            and_(Competitor.id == competitor_id, Competitor.company_id == company.id)
        )
    )
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    await db.delete(competitor)
    await db.commit()
    return {"success": True}


@router.post("/competitors/import-csv", response_model=CSVImportResult)
async def import_competitors_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    """Import competitors from CSV"""
    content = await file.read()
    
    try:
        text = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        
        imported = 0
        errors = []
        
        for i, row in enumerate(reader):
            try:
                name = row.get('name') or row.get('Name') or row.get('competitor')
                if not name:
                    errors.append(f"Row {i+1}: Missing name")
                    continue
                
                competitor = Competitor(
                    name=name,
                    website=row.get('website') or row.get('Website'),
                    description=row.get('description') or row.get('Description'),
                    their_strengths=[s.strip() for s in (row.get('strengths') or '').split(',') if s.strip()],
                    their_weaknesses=[s.strip() for s in (row.get('weaknesses') or '').split(',') if s.strip()],
                    our_advantages=[s.strip() for s in (row.get('our_advantages') or '').split(',') if s.strip()],
                    their_positioning=row.get('positioning'),
                    price_comparison=row.get('price_comparison'),
                    notes=row.get('notes'),
                    company_id=company.id
                )
                db.add(competitor)
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {i+1}: {str(e)}")
        
        await db.commit()
        return CSVImportResult(success=True, imported_count=imported, errors=errors)
        
    except Exception as e:
        return CSVImportResult(success=False, imported_count=0, errors=[str(e)])


# ============ Case Studies ============

@router.get("/case-studies", response_model=List[CaseStudyResponse])
async def get_case_studies(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(CaseStudy)
        .where(CaseStudy.company_id == company.id)
        .order_by(CaseStudy.client_name)
    )
    return result.scalars().all()


@router.post("/case-studies", response_model=CaseStudyResponse)
async def create_case_study(
    data: CaseStudyCreate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    case = CaseStudy(**data.model_dump(), company_id=company.id)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


@router.patch("/case-studies/{case_id}", response_model=CaseStudyResponse)
async def update_case_study(
    case_id: int,
    data: CaseStudyUpdate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(CaseStudy).where(
            and_(CaseStudy.id == case_id, CaseStudy.company_id == company.id)
        )
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case study not found")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(case, key, value)
    
    await db.commit()
    await db.refresh(case)
    return case


@router.delete("/case-studies/{case_id}")
async def delete_case_study(
    case_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(CaseStudy).where(
            and_(CaseStudy.id == case_id, CaseStudy.company_id == company.id)
        )
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case study not found")
    
    await db.delete(case)
    await db.commit()
    return {"success": True}


# ============ Voice Tones ============

@router.get("/voice-tones", response_model=List[VoiceToneResponse])
async def get_voice_tones(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(VoiceTone)
        .where(VoiceTone.company_id == company.id)
        .order_by(VoiceTone.name)
    )
    return result.scalars().all()


@router.post("/voice-tones", response_model=VoiceToneResponse)
async def create_voice_tone(
    data: VoiceToneCreate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    tone = VoiceTone(**data.model_dump(), company_id=company.id)
    db.add(tone)
    await db.commit()
    await db.refresh(tone)
    return tone


@router.patch("/voice-tones/{tone_id}", response_model=VoiceToneResponse)
async def update_voice_tone(
    tone_id: int,
    data: VoiceToneUpdate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(VoiceTone).where(
            and_(VoiceTone.id == tone_id, VoiceTone.company_id == company.id)
        )
    )
    tone = result.scalar_one_or_none()
    if not tone:
        raise HTTPException(status_code=404, detail="Voice tone not found")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(tone, key, value)
    
    await db.commit()
    await db.refresh(tone)
    return tone


@router.delete("/voice-tones/{tone_id}")
async def delete_voice_tone(
    tone_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(VoiceTone).where(
            and_(VoiceTone.id == tone_id, VoiceTone.company_id == company.id)
        )
    )
    tone = result.scalar_one_or_none()
    if not tone:
        raise HTTPException(status_code=404, detail="Voice tone not found")
    
    await db.delete(tone)
    await db.commit()
    return {"success": True}


# ============ Booking Links ============

@router.get("/booking-links", response_model=List[BookingLinkResponse])
async def get_booking_links(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(BookingLink)
        .where(BookingLink.company_id == company.id)
        .order_by(BookingLink.name)
    )
    return result.scalars().all()


@router.post("/booking-links", response_model=BookingLinkResponse)
async def create_booking_link(
    data: BookingLinkCreate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    link = BookingLink(**data.model_dump(), company_id=company.id)
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


@router.patch("/booking-links/{link_id}", response_model=BookingLinkResponse)
async def update_booking_link(
    link_id: int,
    data: BookingLinkUpdate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(BookingLink).where(
            and_(BookingLink.id == link_id, BookingLink.company_id == company.id)
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Booking link not found")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(link, key, value)
    
    await db.commit()
    await db.refresh(link)
    return link


@router.delete("/booking-links/{link_id}")
async def delete_booking_link(
    link_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(BookingLink).where(
            and_(BookingLink.id == link_id, BookingLink.company_id == company.id)
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Booking link not found")
    
    await db.delete(link)
    await db.commit()
    return {"success": True}


# ============ Blocklist ============

@router.get("/blocklist", response_model=List[BlocklistResponse])
async def get_blocklist(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Blocklist)
        .where(Blocklist.company_id == company.id)
        .order_by(Blocklist.domain, Blocklist.email)
    )
    return result.scalars().all()


@router.post("/blocklist", response_model=BlocklistResponse)
async def add_to_blocklist(
    data: BlocklistCreate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    if not data.domain and not data.email:
        raise HTTPException(status_code=400, detail="Must provide domain or email")
    
    entry = Blocklist(**data.model_dump(), company_id=company.id)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/blocklist/{entry_id}")
async def remove_from_blocklist(
    entry_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    result = await db.execute(
        select(Blocklist).where(
            and_(Blocklist.id == entry_id, Blocklist.company_id == company.id)
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    await db.delete(entry)
    await db.commit()
    return {"success": True}


@router.post("/blocklist/import-csv", response_model=CSVImportResult)
async def import_blocklist_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    """Import blocklist from CSV"""
    content = await file.read()
    
    try:
        text = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        
        imported = 0
        errors = []
        
        for i, row in enumerate(reader):
            try:
                domain = row.get('domain') or row.get('Domain')
                email = row.get('email') or row.get('Email')
                
                if not domain and not email:
                    errors.append(f"Row {i+1}: Missing domain or email")
                    continue
                
                entry = Blocklist(
                    domain=domain,
                    email=email,
                    company_name=row.get('company_name') or row.get('Company'),
                    reason=row.get('reason') or row.get('Reason'),
                    company_id=company.id
                )
                db.add(entry)
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {i+1}: {str(e)}")
        
        await db.commit()
        return CSVImportResult(success=True, imported_count=imported, errors=errors)
        
    except Exception as e:
        return CSVImportResult(success=False, imported_count=0, errors=[str(e)])


# ============ AI Import ============

@router.post("/ai-import", response_model=AIImportResponse)
async def ai_import(
    request: AIImportRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    """Parse free-form text into structured data using AI"""
    try:
        if request.parse_multiple:
            result = await parse_multiple_entities(request.text, request.entity_type)
        else:
            result = await parse_free_text(request.text, request.entity_type)
        
        if not result.get("success"):
            return AIImportResponse(
                success=False,
                entity_type=request.entity_type,
                error=result.get("error", "Unknown error"),
                tokens_used=result.get("tokens_used", 0)
            )
        
        data = result.get("data", {})
        saved_ids = []
        
        if request.save_to_db:
            saved_ids = await _save_entities(db, request.entity_type, data, request.parse_multiple, company.id)
        
        return AIImportResponse(
            success=True,
            entity_type=request.entity_type,
            data=data,
            saved_ids=saved_ids if saved_ids else None,
            tokens_used=result.get("tokens_used", 0)
        )
        
    except Exception as e:
        return AIImportResponse(
            success=False,
            entity_type=request.entity_type,
            error=str(e),
            tokens_used=0
        )


async def _save_entities(db: AsyncSession, entity_type: str, data: dict, is_multiple: bool, company_id: int) -> List[int]:
    """Save parsed entities to database"""
    saved_ids = []
    
    if is_multiple:
        items = data.get(f"{entity_type}s", [])
    else:
        items = [data]
    
    for item in items:
        entity_id = await _save_single_entity(db, entity_type, item, company_id)
        if entity_id:
            saved_ids.append(entity_id)
    
    await db.commit()
    return saved_ids


async def _save_single_entity(db: AsyncSession, entity_type: str, data: dict, company_id: int) -> Optional[int]:
    """Save a single entity"""
    model_map = {
        "competitor": Competitor,
        "case_study": CaseStudy,
        "voice_tone": VoiceTone,
        "booking_link": BookingLink,
        "product": Product,
    }
    
    if entity_type == "segment":
        name = data.pop("name", "Unnamed Segment")
        segment = Segment(name=name, data=data, company_id=company_id)
        db.add(segment)
        await db.flush()
        return segment.id
    
    model = model_map.get(entity_type)
    if not model:
        return None
    
    entity = model(**data, company_id=company_id)
    db.add(entity)
    await db.flush()
    return entity.id


# ============ Tags & Context ============

@router.get("/tags")
async def list_available_tags(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    """Get all available @tags for autocomplete"""
    tags = await get_available_tags(db, company.id)
    return {"tags": tags}


@router.post("/resolve-tags")
async def resolve_prompt_tags(
    prompt: str,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    """Resolve @tags in a prompt to actual content"""
    result = await resolve_tags(prompt, db, company.id)
    return result


# ============ Export ============

@router.get("/export", response_model=KnowledgeBaseExport)
async def export_knowledge_base(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    """Export entire knowledge base for this company"""
    company_result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.company_id == company.id)
    )
    products_result = await db.execute(
        select(Product).where(Product.company_id == company.id)
    )
    segments_result = await db.execute(
        select(Segment).where(Segment.company_id == company.id)
    )
    columns_result = await db.execute(
        select(SegmentColumn).where(SegmentColumn.company_id == company.id)
    )
    competitors_result = await db.execute(
        select(Competitor).where(Competitor.company_id == company.id)
    )
    cases_result = await db.execute(
        select(CaseStudy).where(CaseStudy.company_id == company.id)
    )
    tones_result = await db.execute(
        select(VoiceTone).where(VoiceTone.company_id == company.id)
    )
    links_result = await db.execute(
        select(BookingLink).where(BookingLink.company_id == company.id)
    )
    blocklist_result = await db.execute(
        select(Blocklist).where(Blocklist.company_id == company.id)
    )
    docs_result = await db.execute(
        select(Document).where(Document.company_id == company.id)
    )
    
    return KnowledgeBaseExport(
        company=company_result.scalar_one_or_none(),
        products=products_result.scalars().all(),
        segments=segments_result.scalars().all(),
        segment_columns=columns_result.scalars().all(),
        competitors=competitors_result.scalars().all(),
        case_studies=cases_result.scalars().all(),
        voice_tones=tones_result.scalars().all(),
        booking_links=links_result.scalars().all(),
        blocklist=blocklist_result.scalars().all(),
        documents=docs_result.scalars().all()
    )
