"""Pydantic models for request/response validation."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ArmorPiece(BaseModel):
    """Armor piece data structure."""
    armor_set: str
    armor_type: str
    current_level: int = 1
    max_level: int = 16
    # Stat fields - all optional since pieces may have different stats
    base: Optional[int] = 0
    fire: Optional[int] = 0
    electric: Optional[int] = 0
    poison: Optional[int] = 0
    hero_hp: Optional[int] = 0
    hero_dmg: Optional[int] = 0
    hero_rate: Optional[int] = 0
    hero_speed: Optional[int] = 0
    offense: Optional[int] = 0
    defense: Optional[int] = 0
    tower_hp: Optional[int] = 0
    tower_dmg: Optional[int] = 0
    tower_rate: Optional[int] = 0
    tower_range: Optional[int] = 0
    # Additional metadata fields (optional)
    id: Optional[str] = None
    row: Optional[int] = None
    column: Optional[int] = None
    page: Optional[int] = None
    is_blueprint: Optional[bool] = None

    class Config:
        extra = "allow"  # Allow additional fields from JSON


class Constraints(BaseModel):
    """Hard constraints (minimums) for stats."""
    min: Dict[str, int] = Field(default_factory=dict)


class RecommendationRequest(BaseModel):
    """Request model for recommendations endpoint."""
    weights: Dict[str, float] = Field(default_factory=dict)
    constraints: Constraints = Field(default_factory=Constraints)
    limit: int = Field(default=10, ge=1, le=100)
    data_file: Optional[str] = None

    @field_validator('weights')
    @classmethod
    def validate_weights(cls, v: Dict[str, float]) -> Dict[str, float]:
        """Ensure weights are positive."""
        for stat, weight in v.items():
            if weight < 0:
                raise ValueError(f"Weight for '{stat}' must be non-negative, got {weight}")
        return v


class RecommendationPiece(BaseModel):
    """Armor piece in recommendation response."""
    armor_set: str
    armor_type: str
    current_level: int
    max_level: int
    stats: Dict[str, int]
    # Location in data (filename is primary locator; row/col are within that armor type)
    filename: Optional[str] = None
    subdir: Optional[str] = None
    page: Optional[int] = None
    row: Optional[int] = None
    col: Optional[int] = None


class Recommendation(BaseModel):
    """Single recommendation result."""
    set_id: str
    pieces: List[RecommendationPiece]
    current_stats: Dict[str, int]
    upgraded_stats: Dict[str, int]
    effective_stats: Dict[str, int]
    wasted_points: Dict[str, int]
    score: float
    score_breakdown: Optional[Dict[str, float]] = None
    potential_score: float = 0.0
    flexibility_score: float = 0.0


class RecommendationResponse(BaseModel):
    """Response model for recommendations endpoint."""
    recommendations: List[Recommendation]
    incremental_changes: Optional[List[Dict]] = None
