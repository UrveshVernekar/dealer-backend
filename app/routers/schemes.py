from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.models.scheme import Scheme
from app.schemas.scheme import SchemeCreate, SchemeResponse, SchemeUpdate
from app.routers.auth import get_current_user, get_admin_user

router = APIRouter(prefix="/schemes", tags=["Dealer Schemes"])

@router.get("/", response_model=list[SchemeResponse])
def get_schemes(
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Scheme)
    if active_only:
        query = query.filter(Scheme.is_active == True)
    return query.order_by(Scheme.scheme_code.asc()).all()

@router.get("/{scheme_id}", response_model=SchemeResponse)
def get_scheme(
    scheme_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    scheme = db.query(Scheme).filter(Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheme with ID {scheme_id} not found"
        )
    return scheme

@router.post("/", response_model=SchemeResponse, status_code=status.HTTP_201_CREATED)
def create_scheme(
    scheme_data: SchemeCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    # Check if scheme code already exists
    existing = db.query(Scheme).filter(Scheme.scheme_code == scheme_data.scheme_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scheme with code {scheme_data.scheme_code} already exists"
        )
    
    new_scheme = Scheme(
        scheme_code=scheme_data.scheme_code,
        name=scheme_data.name,
        description=scheme_data.description,
        discount_percentage=scheme_data.discount_percentage,
        incentive_amount=scheme_data.incentive_amount,
        is_active=scheme_data.is_active
    )
    db.add(new_scheme)
    db.commit()
    db.refresh(new_scheme)
    return new_scheme

@router.put("/{scheme_id}", response_model=SchemeResponse)
def update_scheme(
    scheme_id: int,
    scheme_data: SchemeUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    scheme = db.query(Scheme).filter(Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheme with ID {scheme_id} not found"
        )
    
    # If scheme code is updated, make sure it is not taken
    if scheme_data.scheme_code and scheme_data.scheme_code != scheme.scheme_code:
        existing = db.query(Scheme).filter(Scheme.scheme_code == scheme_data.scheme_code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scheme with code {scheme_data.scheme_code} already exists"
            )
        scheme.scheme_code = scheme_data.scheme_code
        
    if scheme_data.name is not None:
        scheme.name = scheme_data.name
    if scheme_data.description is not None:
        scheme.description = scheme_data.description
    if scheme_data.discount_percentage is not None:
        scheme.discount_percentage = scheme_data.discount_percentage
    if scheme_data.incentive_amount is not None:
        scheme.incentive_amount = scheme_data.incentive_amount
    if scheme_data.is_active is not None:
        scheme.is_active = scheme_data.is_active
        
    db.commit()
    db.refresh(scheme)
    return scheme

@router.delete("/{scheme_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scheme(
    scheme_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    scheme = db.query(Scheme).filter(Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheme with ID {scheme_id} not found"
        )
    db.delete(scheme)
    db.commit()
    return None
